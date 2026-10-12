"""Run isolated PDS implementation with input identity and single-instance guard."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import subprocess
import time

root=Path(__file__).resolve().parent
project=root/'integrated/project'
pds=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
guard=subprocess.run(['powershell','-NoProfile','-Command',
    "@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,check=True)
if guard.stdout.strip()!='0':
    raise RuntimeError('An existing PDS process is active: '+guard.stdout)
if not pds.is_file() or not (project/'project.pds').is_file():
    raise RuntimeError('PDS executable or generated project missing')
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
archive=project/('build_backup_'+stamp)
for name in ('compile','synthesize','device_map','place_route','report_timing','generate_netlist','generate_bitstream'):
    folder=project/name
    if folder.exists():
        archive.mkdir(exist_ok=True)
        folder.rename(archive/name)
inputs=[project/'project.pds',*(root/'integrated/source').rglob('*.v')]
identity={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
command=[str(pds),'-project',str(project/'project.pds'),'-run','pnr','-work_dir',str(project)]
start=time.time()
receipt={'command':command,'started_at':start,'inputs':identity,'status':'running'}
(root/'pds_build_manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('Starting isolated PDS place/route; normal viewer continues on existing image.',flush=True)
with (root/'pds_pnr.log').open('wb') as log:
    result=subprocess.run(command,cwd=project,stdout=log,stderr=subprocess.STDOUT)
receipt.update(status='finished',return_code=result.returncode,wall_seconds=time.time()-start)
(root/'pds_build_manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('PDS return_code=',result.returncode,'wall_seconds=',receipt['wall_seconds'],flush=True)
raise SystemExit(result.returncode)
