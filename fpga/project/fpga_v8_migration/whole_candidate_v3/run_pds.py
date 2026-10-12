"""Future parent-only sequential PDS runner. This script has not been invoked."""
from pathlib import Path
import sys, json, re, hashlib, subprocess
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent
RUN=HERE/'compile_01'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def write(name,obj):
    (RUN/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')

def verify():
    pins=json.loads((HERE/'artifacts/candidate_source_sha256.json').read_bytes())
    assert all(sha(HERE/p)==h for p,h in pins.items()),'Candidate source drift'
    return pins

def prepare():
    verify()
    assert RUN.is_dir() and not any(RUN.iterdir()),'compile_01 must be fresh and empty; no deletion/overwrite'
    project=(HERE/'project.pds').read_bytes()
    project=project.replace(b'"inputs/',b'"../inputs/').replace(b'"rtl/',b'"../rtl/')
    for rel in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"',project):
        p=(RUN/rel.decode()).resolve(); assert p.is_relative_to(HERE) and p.is_file()
    (RUN/'project.pds').write_bytes(project)
    write('prepared.json',{'top_module':'fpga_v8_cooperative_top_v2_rfg01','project_sha256':sha(RUN/'project.pds'),'sources_local_to_v3':True,'core_clock_mhz':131.25,'constraints_unchanged':True})

def run(stage):
    assert stage in ['compile','synthesize','pnr']
    assert (RUN/'prepared.json').is_file(),'Parent must prepare first'
    previous={'synthesize':'compile','pnr':'synthesize'}.get(stage)
    if previous: assert json.loads((RUN/f'{previous}_result.json').read_bytes())['pass']
    assert not (RUN/f'{stage}_shell.log').exists() and not (RUN/f'{stage}_started.json').exists(),'No overwrite/retry in same folder'
    pins=verify()
    # One explicit single-instance check immediately before this future stage.
    processes=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,check=True).stdout
    (RUN/f'processes_before_{stage}.csv').write_bytes(processes)
    assert not re.search(rb'(?im)^"(?:pds|pds_shell)\.exe"',processes),'PDS already running; do not start'
    command=[str(PDS),'-project',str(RUN/'project.pds'),'-run',stage,'-work_dir',str(RUN)]
    write(f'{stage}_started.json',{'command':command,'utc':datetime.now(timezone.utc).isoformat()})
    with (RUN/f'{stage}_shell.log').open('wb') as log:
        result=subprocess.run(command,cwd=RUN,stdout=log,stderr=subprocess.STDOUT)
    verify()
    text=(RUN/f'{stage}_shell.log').read_bytes()
    marker={'compile':b'Process "Compile" done.','synthesize':b'Process "Synthesize" done.','pnr':b'Process "Place & Route" done.'}[stage]
    passed=result.returncode==0 and marker in text and not re.search(rb'(?m)^E:',text)
    write(f'{stage}_result.json',{'pass':passed,'exit_code':result.returncode,'command':command,'sources_unchanged':True,'log_sha256':sha(RUN/f'{stage}_shell.log'),'completion_marker':marker.decode(),'marker_found':marker in text,'board_ready':False})
    if not passed: raise SystemExit(1)

if __name__=='__main__':
    assert len(sys.argv)==2,'prepare|compile|synthesize|pnr; parent invokes after v2 completes'
    if sys.argv[1]=='prepare': prepare()
    else: run(sys.argv[1])
