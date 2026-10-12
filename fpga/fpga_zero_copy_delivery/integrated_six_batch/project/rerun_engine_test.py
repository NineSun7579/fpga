"""Rerun existing engine regression in an isolated project-local work library."""
from pathlib import Path
import hashlib
import json
import subprocess

project = Path(__file__).resolve().parent
original = project.parent.parent / 'sim_six_batch'
target = project / 'timing_validation_sim'
target.mkdir(exist_ok=True)
for name in ('six_batch_tb.sv', 'vendor_endpoint_stubs.v', 'run.do', 'run_baseline.do'):
    (target / name).write_bytes((original / name).read_bytes())
receipts = []
for script, logfile, success in [('run.do', 'candidate.log', 'SIX_BATCH_ENGINE_PASS'),
                               ('run_baseline.do', 'baseline_negative.log', '** Fatal: register burst not single beat')]:
    command = ['C:/modeltech64_10.6e/win64/vsim.exe', '-c', '-do', script, '-l', logfile]
    result = subprocess.run(command, cwd=target, capture_output=True)
    (target / (logfile + '.stdout')).write_bytes(result.stdout + result.stderr)
    text = (target / logfile).read_text(errors='replace')
    assert success in text, text[-5000:]
    if script == 'run.do':
        assert 'Errors: 0' in text and result.returncode == 0
    receipts.append(dict(command=command, cwd=str(target), return_code=result.returncode,
                         expected_marker=success, marker_verified=True,
                         log_sha256=hashlib.sha256((target / logfile).read_bytes()).hexdigest()))
(project / 'timing_engine_test_receipt.json').write_text(json.dumps(receipts, indent=2))
print(json.dumps(receipts, indent=2))
