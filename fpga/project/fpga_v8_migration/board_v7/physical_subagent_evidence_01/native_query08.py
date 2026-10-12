"""Run one isolated PDS probe only when all implementation/TA processes are idle."""
from pathlib import Path
import subprocess, json, hashlib, sys, datetime
BASE = Path(__file__).resolve().parent
PDS = 'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def idle():
    r = subprocess.run(['powershell','-NoProfile','-Command',"Get-Process | Where-Object {$_.ProcessName -match '^(pds|pds_shell|ta|de)$'} | Select-Object Id,ProcessName | ConvertTo-Json"], capture_output=True, check=True)
    assert not r.stdout.strip(), r.stdout
def run(label, text, databases=()):
    idle()
    out = BASE/'fixed_06'/label
    out.mkdir(exist_ok=False)
    script = out/'probe.tcl'
    script.write_text(text, encoding='ascii')
    before = {str(p):digest(p) for p in databases}
    cmd = [PDS,'-file',str(script),'-work_dir',str(out),'-project_name',label]
    (out/'launch.json').write_text(json.dumps({'command':cmd,'inputs':before,'time':datetime.datetime.now().isoformat()},indent=2))
    with (out/'shell.log').open('xb') as f:
        result = subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT)
    raw = (out/'shell.log').read_bytes()
    log = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8', errors='replace')
    (out/'shell.txt').write_text(log,encoding='utf8')
    after = {str(p):digest(p) for p in databases}
    (out/'result.json').write_text(json.dumps({'exit_code':result.returncode,'unchanged':before==after,'errors':[s[:500] for s in log.splitlines() if s.startswith('E:') or 'Timing-4003' in s]},indent=2))
    assert before==after
    print(log[-22000:],flush=True)
    return out,result.returncode
if __name__=='__main__':
    text=Path(sys.argv[2]).read_text(encoding='ascii')
    run(sys.argv[1],text,[Path(x) for x in sys.argv[3:]])
