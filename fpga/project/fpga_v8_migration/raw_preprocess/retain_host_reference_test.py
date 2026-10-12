"""Retain exact command, stdout and immutable input identities for the C++ test."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
paths = ['raw_input_reference.h', 'raw_input_reference_test.cpp', 'run_host_reference_test.cmd',
         'artifacts/full_ready/source.hex', 'artifacts/full_ready/pixels.hex',
         'artifacts/full_ready/actual_words.txt']
before = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}
command = ['cmd', '/c', 'run_host_reference_test.cmd']
result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
folder = root/'host_reference_artifacts'
folder.mkdir(exist_ok=True)
(folder/'stdout.txt').write_text(result.stdout, encoding='utf-8')
(folder/'stderr.txt').write_text(result.stderr, encoding='utf-8')
after = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}
expected = 'RAW_INPUT_REFERENCE_PASS fixture_rgb_bytes=2457600 actual_rtl_bytes=2457600 frames=2 exhaustive_codes=65536 invalid_inputs=4'
passed = result.returncode == 0 and expected in result.stdout and before == after
report = {'status': 'pass' if passed else 'fail', 'command': command,
          'return_code': result.returncode, 'source_fixture_hashes': before,
          'inputs_unchanged': before == after, 'actual_rtl_rgb_bytes': 2457600,
          'frames': 2, 'exhaustive_rgb565_codes': 65536, 'invalid_input_rejections': 4,
          'scope': 'Software prepare agrees with independently generated fixture and retained actual isolated RTL trace',
          'limits': ['Simulation-generated RAW, not physical camera payloads',
                     'Does not establish physical DMA/capture leases or board FPS']}
(folder/'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(result.stdout, end='')
if not passed:
    raise SystemExit(1)
