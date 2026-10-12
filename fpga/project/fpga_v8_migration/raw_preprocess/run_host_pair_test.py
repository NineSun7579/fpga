"""Compare C++ input preparation with actual retained capture/core/DDR copies."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
evidence = root/'host_pair_artifacts'
evidence.mkdir(exist_ok=False)
fixture = root.parent/'capture_core_contract/artifacts/full_640x480'
metadata_path = fixture/'checker.json'
metadata = json.loads(metadata_path.read_text())
pinned = {str(metadata_path): hashlib.sha256(metadata_path.read_bytes()).hexdigest()}
for frame in metadata['frames']:
    if frame['status'] != 'exact_paired_input_pass':
        raise ValueError('expected only complete retained input pairs')
    for name, expected in [(frame['raw_file'], frame['raw_sha256']),
                           (frame['prepared_file'], frame['output_sha256'])]:
        path = fixture/name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError('retained frame hash differs: ' + name)
        pinned[str(path)] = digest

build = subprocess.run(['cmd', '/c', 'build_host_pair_test.cmd'], cwd=root,
                       text=True, capture_output=True, timeout=45)
(evidence/'build_stdout.txt').write_text(build.stdout, encoding='utf-8')
(evidence/'build_stderr.txt').write_text(build.stderr, encoding='utf-8')
if build.returncode:
    raise RuntimeError('C++ owned-input pair checker compilation failed')
exe = evidence/'raw_input_pair_test.exe'
rows = []
for frame in metadata['frames']:
    command = [str(exe), str(fixture/frame['raw_file']), str(fixture/frame['prepared_file']), str(frame['sequence'])]
    result = subprocess.run(command, text=True, capture_output=True, timeout=15)
    rows.append({'sequence': frame['sequence'], 'generation': frame['generation'],
        'command': command, 'return_code': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode or f"RAW_PAIR_PASS sequence={frame['sequence']} bytes=1228800" not in result.stdout:
        raise RuntimeError('C++ preparation differs from actual capture/core fixture')

# Negative checks ensure identity and exact byte comparisons remain acceptance gates.
first, second = metadata['frames'][:2]
cases = [(fixture/first['raw_file'], fixture/second['prepared_file'], first['sequence'],
          'owned RAW/FPGA model-input bytes differ'),
         (fixture/first['raw_file'], fixture/first['prepared_file'], first['sequence']+1,
          'RAW tag/source sequence differs')]
negative = []
for raw, prepared, sequence, expected in cases:
    command = [str(exe), str(raw), str(prepared), str(sequence)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=15)
    negative.append({'command': command, 'return_code': result.returncode, 'stderr': result.stderr})
    if result.returncode != 1 or expected not in result.stderr:
        raise RuntimeError('incorrect pairing was not rejected')
for name, digest in pinned.items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('retained capture/core evidence changed')
report = {'status': 'pass', 'frames': len(rows), 'compared_rgb_bytes': len(rows)*1228800,
    'raw_bank_bytes': len(rows)*614416, 'negative_pair_rejections': len(negative),
    'source_hashes': {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ['raw_input_reference.h','raw_input_pair_test.cpp','run_host_pair_test.py','build_host_pair_test.cmd']},
    'fixture_hashes': pinned, 'retained_fixtures_unchanged': True,
    'pairs': rows, 'negative_checks': negative,
    'limits': ['Simulation capture/core/DDR copies, not physical board payloads',
               'No RKNN inference or FPGA/RK3568 FPS claim']}
(evidence/'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(f"HOST_CAPTURE_CORE_PAIRS_PASS frames={len(rows)} rgb_bytes={len(rows)*1228800} negative_rejections={len(negative)}")
