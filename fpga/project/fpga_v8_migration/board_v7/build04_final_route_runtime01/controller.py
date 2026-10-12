"""External producer: prepare, guarded copy and explicit-DB PNR only.

No compile/synth/dev_map/bit/program/remote entry point. Real signoff remains
independent and requires all gates in signoff_manifest.json on the fresh route.
"""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys,time,re
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runtime'))
from contract import load,sha,require
from gates import check
def copy_inputs():
    check();plan=load(HERE/'route_copy_plan.json');root=HERE/'execution01'
    require(not root.exists(),'Refuse existing execution root');root.mkdir()
    rows=[]
    for x in plan['files']:
        src=Path(x['source']);dst=Path(x['destination'])
        require(dst.resolve().is_relative_to(root.resolve()),'Copy destination escape')
        require(sha(src)==x['sha256'],'Copy source drift');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        require(sha(dst)==x['sha256'],'Copy byte mismatch');rows.append(x)
    (root/'copy_receipt.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='ascii')
    check();return root
def route():
    check();root=HERE/'execution01'
    require(root.is_dir(),'Run copy after gates before route')
    for x in load(root/'copy_receipt.json'):require(sha(x['source'])==sha(x['destination'])==x['sha256'],'Copied input drift')
    # Serialize with an OS lock plus actual vendor-process exclusion. Do not wait
    # silently behind another agent or start any prerequisite action.
    process=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],capture_output=True)
    require(not process.stdout.strip(),'PDS already active')
    work=root/'pnr_work';require(not work.exists(),'No overwrite/resume of real PNR');work.mkdir()
    lock=os.open(str(root/'exclusive.lock'),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        raw=(HERE/'commands/pnr_reload.tcl').read_text(encoding='ascii').split('\n',1)[1]
        script=work/'pnr.tcl';script.write_text(raw,encoding='ascii')
        before={x['destination']:sha(x['destination']) for x in load(root/'copy_receipt.json')}
        argv=['C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe','-file',str(script),'-work_dir',str(root),'-project_name','v7_sdt_top']
        started=time.time();log=work/'shell.log'
        with log.open('xb') as f:r=subprocess.run(argv,cwd=root,stdout=f,stderr=subprocess.STDOUT)
        logs=[log]+list(root.rglob('run.log'));combined=b'\n'.join(p.read_bytes() for p in logs)
        bad=re.findall(rb'(?im)^.*(?:^E:|\bERROR\b|\bFATAL\b|Timing-4006|STA-3016|ignored|unsupported|unresolved|Process "(?:Compile|Synthesize|Device Map|DevMap)"|implicit prerequisite).*$',combined)
        result={'argv':argv,'exit_code':r.returncode,'errors':[x.decode('ascii','backslashreplace') for x in bad],'logs':{str(p):sha(p) for p in logs},'inputs_unchanged':all(sha(p)==h for p,h in before.items()),'started':started,'physical_signoff':False,'bit_allowed':False}
        (work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='ascii')
        check();require(result['inputs_unchanged'] and r.returncode==0 and not bad,'Real PNR failed/changed input/prerequisite; preserve evidence')
        require(b'Process "Place & Route" done.' in combined,'Missing official PNR completion')
        adf=root/'place_route/v7_sdt_top_pnr.adf';db=root/'place_route/prr.db'
        require(all(p.is_file() and p.stat().st_size>0 and p.stat().st_mtime>=started-2 for p in [adf,db]),'No fresh routed native DB')
        import xml.etree.ElementTree as ET
        for table in ET.parse(db).getroot().iter('table'):
            if 'message' in table.get('id','').lower():
                require(not any((d.text or '').strip().lower() in ['error','fatal'] for d in table.iter('data')),'Native PNR errors')
        result.update(route_sha256=sha(adf),native_db_sha256=sha(db),fresh_route=True)
        (work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='ascii')
    finally:os.close(lock);(root/'exclusive.lock').unlink()
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','check-gates','copy','route']);a=ap.parse_args()
    if a.action=='prepare':
        import prepare;prepare.main()
    elif a.action=='check-gates':check()
    elif a.action=='copy':copy_inputs()
    else:route()
