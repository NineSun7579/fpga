"""Recheck actual final generation products after PDS prerequisite reruns."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path(__file__).resolve().parent
project=root/'integrated_six_batch/project'
guard=subprocess.run(['powershell','-NoProfile','-Command',
    '@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count'],capture_output=True,text=True,check=True)
if guard.stdout.strip()!='0': raise RuntimeError('PDS still active')
manifest=root/'six_batch_bitstream_manifest.json'
receipt=json.loads(manifest.read_text())
if receipt.get('status')!='finished' or receipt.get('return_code')!=0:
    raise RuntimeError('Generation has not finished successfully')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
image=project/'generate_bitstream/top.sbit'
timing=project/'place_route/top_timing_summary_after_hold_fix.txt'
if receipt.get('sha256')!=digest(image): raise RuntimeError('Generated image changed')
if 'Design Summary : All Constraints Met.' not in timing.read_text():
    raise RuntimeError('Actual generated implementation fails timing')
build=json.loads((root/'six_batch_pds_manifest.json').read_text())
if not all(digest(root/relative)==expected for relative,expected in build['inputs'].items()
           if Path(relative).name!='project.pds'):
    raise RuntimeError('Source inputs changed during generation')
receipt.setdefault('pre_generation_timing_sha256',receipt['timing_sha256'])
receipt.update(timing_sha256=digest(timing),timing_passed=True,source_inputs_unchanged=True,
               postgeneration_project_sha256=digest(project/'project.pds'))
manifest.write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
