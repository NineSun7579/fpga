from pathlib import Path
import hashlib
import json
import subprocess
import time
import sys

root = Path(__file__).resolve().parent
candidate = 'integrated_six_background' if '--background' in sys.argv else 'integrated_six_batch' if '--batch' in sys.argv else 'integrated_six'
prefix = 'six_background' if '--background' in sys.argv else 'six_batch' if '--batch' in sys.argv else 'six'
project = root / candidate / 'project'
pds = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
guard = subprocess.run(['powershell', '-NoProfile', '-Command',
    '@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count'],
    capture_output=True, text=True, check=True)
if guard.stdout.strip() != '0':
    raise RuntimeError('PDS already active')
build = json.loads((root / (prefix + '_pds_manifest.json')).read_text())
if build.get('status') != 'finished' or build.get('return_code') != 0:
    raise RuntimeError('Six-camera place/route has not passed')
for relative, expected in build['inputs'].items():
    if Path(relative).name == 'project.pds':
        expected = build.get('postbuild_project_sha256', expected)
    if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
        raise RuntimeError('Build input changed: ' + relative)
timing = project / 'place_route/top_timing_summary_after_hold_fix.txt'
if 'All Constraints Met' not in timing.read_text():
    raise RuntimeError('Six-camera timing has not passed')
command = [str(pds), '-project', str(project / 'project.pds'),
    '-run', 'gen_bit_stream', '-work_dir', str(project)]
receipt = {'command': command, 'status': 'running',
    'timing_sha256': hashlib.sha256(timing.read_bytes()).hexdigest(),
    'scope': 'generate only; no programming; SPI unchanged'}
manifest = root / (prefix + '_bitstream_manifest.json')
manifest.write_text(json.dumps(receipt, indent=2))
started = time.time()
with (root / (prefix + '_bitstream.log')).open('wb') as log:
    result = subprocess.run(command, cwd=project, stdout=log, stderr=subprocess.STDOUT)
image = project / 'generate_bitstream/top.sbit'
receipt.update(status='finished', return_code=result.returncode,
    wall_seconds=time.time() - started)
receipt['pre_generation_timing_sha256']=receipt['timing_sha256']
receipt['timing_sha256']=hashlib.sha256(timing.read_bytes()).hexdigest() if timing.exists() else None
receipt['timing_passed']=timing.exists() and 'Design Summary : All Constraints Met.' in timing.read_text()
receipt['source_inputs_unchanged']=all(hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected
    for relative,expected in build['inputs'].items() if Path(relative).name!='project.pds')
if result.returncode == 0 and image.is_file():
    receipt.update(image=str(image), size_bytes=image.stat().st_size,
        sha256=hashlib.sha256(image.read_bytes()).hexdigest())
manifest.write_text(json.dumps(receipt, indent=2))
if result.returncode != 0 or not image.is_file() or not receipt['timing_passed'] or not receipt['source_inputs_unchanged']:
    raise RuntimeError('Six-camera bitstream generation failed; inspect six_bitstream.log')
print(json.dumps(receipt, indent=2))
