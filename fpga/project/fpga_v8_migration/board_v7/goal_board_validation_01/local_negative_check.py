"""Local negative gates only: does not import vendor or contact hardware."""
import json
from pathlib import Path
import py_compile
import subprocess
import sys

HERE = Path(__file__).resolve().parent
for name in ('new_program_candidate.py', 'new_validate_board.py'):
    py_compile.compile(str(HERE / name), doraise=True)
missing = str(HERE / 'nonexistent_delivery_manifest.json')
cases = [('--check', '--manifest', missing), ('--manifest', missing),
         ('--execute', '--manifest', missing),
         ('--check', '--manifest', str(HERE / 'validated_delivery.prepare.json'))]
results = []
for args in cases:
    proc = subprocess.run([sys.executable, str(HERE / 'new_program_candidate.py'), *args],
                          capture_output=True, text=True, check=False)
    receipt = json.loads(proc.stdout)
    assert proc.returncode == 1 and receipt['status'] == 'blocked' and not receipt['stages']
    directory = Path(receipt['retained_directory'])
    assert not (directory / 'program.tcl').exists() and not (directory / 'server.log').exists()
    results.append({'args': args, 'returncode': proc.returncode, 'status': receipt['status'],
                    'receipt': str(directory / 'receipt.json')})
proc = subprocess.run([sys.executable, str(HERE / 'new_validate_board.py'),
                       '--evidence', str(HERE / 'nonexistent_board_validation.json')],
                      capture_output=True, text=True, check=False)
assert proc.returncode == 1 and json.loads(proc.stdout)['status'] == 'blocked'
report = {'py_compile': 'PASS', 'negative_cases': results, 'runtime_missing_evidence_rejected': True,
          'gui_pds_remote_program_performed': False}
(HERE / 'local_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
