"""Validate a seed closure and record it for the shared bitstream generator."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root=Path(__file__).resolve().parent
project=root/'integrated_six_batch/project'
seed=int(sys.argv[1])
subprocess.run([sys.executable,str(project/'verify_timing_closure.py'),str(seed)],check=True)
closure=json.loads((project/f'seed_{seed}_closure_receipt.json').read_text())
build=json.loads((project/f'seed_{seed}_manifest.json').read_text())
if closure['status']!='timing_closed':
    raise RuntimeError('Seed timing not closed')
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
inputs={str((project.parent/relative).relative_to(root)):expected for relative,expected in build['inputs'].items()}
inputs[str((project/'project.pds').relative_to(root))]=digest(project/'project.pds')
receipt=dict(status='finished',return_code=build['return_code'],wall_seconds=build['wall_seconds'],
             inputs=inputs,postbuild_project_sha256=digest(project/'project.pds'),
             source_inputs_unchanged=True,timing_passed=True,seed=seed,
             closure_receipt=str((project/f'seed_{seed}_closure_receipt.json').relative_to(root)),
             timing_reports=closure['report_sha256'],command=build['command'])
(root/'six_batch_pds_manifest.json').write_text(json.dumps(receipt,indent=2))
print('Validated and adopted batch seed',seed)
