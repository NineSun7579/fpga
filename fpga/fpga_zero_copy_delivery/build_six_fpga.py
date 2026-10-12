"""Build isolated six-camera ownership candidate; never programs hardware."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
root=Path(__file__).resolve().parent
candidate='integrated_six_background' if '--background' in sys.argv else 'integrated_six_batch' if '--batch' in sys.argv else 'integrated_six'
prefix='six_background' if '--background' in sys.argv else 'six_batch' if '--batch' in sys.argv else 'six'
project=root/candidate/'project'
pds=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
guard=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,check=True)
if guard.stdout.strip()!='0': raise RuntimeError('PDS already active')
if not pds.exists(): raise RuntimeError('PDS missing')
for name in ('compile','synthesize','device_map','place_route','report_timing','generate_netlist','generate_bitstream'):
    folder=project/name
    if folder.exists():
        backup=project/('build_backup_'+str(time.time_ns()))
        backup.mkdir(exist_ok=True); folder.rename(backup/name)
inputs=[project/'project.pds',*(p for p in (root/candidate/'source').rglob('*') if p.is_file())]
receipt={'inputs':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'status':'running'}
(root/(prefix+'_pds_manifest.json')).write_text(json.dumps(receipt,indent=2))
command=[str(pds),'-project',str(project/'project.pds'),'-run','pnr','-work_dir',str(project)]
start=time.time()
with (root/(prefix+'_pds.log')).open('wb') as log: result=subprocess.run(command,cwd=project,stdout=log,stderr=subprocess.STDOUT)
receipt.update(status='finished',return_code=result.returncode,wall_seconds=time.time()-start)
receipt['postbuild_project_sha256']=hashlib.sha256((project/'project.pds').read_bytes()).hexdigest()
receipt['source_inputs_unchanged']=all(hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected for relative,expected in receipt['inputs'].items() if Path(relative).name!='project.pds')
timing=project/'place_route/top_timing_summary_after_hold_fix.txt'
receipt['timing_passed']=timing.is_file() and 'Design Summary : All Constraints Met.' in timing.read_text()
(root/(prefix+'_pds_manifest.json')).write_text(json.dumps(receipt,indent=2))
if not receipt['source_inputs_unchanged']: raise RuntimeError('Source input changed during PDS build')
if result.returncode==0 and not receipt['timing_passed']: raise RuntimeError('PDS completed but timing constraints failed')
raise SystemExit(result.returncode)
