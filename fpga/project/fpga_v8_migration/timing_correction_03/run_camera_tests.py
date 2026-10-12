"""Isolated ModelSim differential regression; never invokes PDS or edits inputs."""
from pathlib import Path
import hashlib
import difflib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
V4 = HERE.parent / 'whole_candidate_v4_route_01'
OUT = HERE / 'camera_artifacts'
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
PRIMITIVES = Path(os.environ.get('PANGO_SIM_LIB', r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))
SOURCE = V4 / 'inputs/source/ov5640/ov5640/ov5640_cdc.v'
CANDIDATE = HERE / 'rtl/ov5640_cdc_tc03.v'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(args, label):
    result = subprocess.run([str(x) for x in args], cwd=OUT, capture_output=True, timeout=120)
    data = result.stdout + result.stderr
    (OUT / (label + '.log')).write_bytes(data)
    if result.returncode or any(x in data for x in (b'** Error', b'** Fatal', b'Fatal:')):
        raise RuntimeError(data.decode(errors='replace'))
    return data

def main():
    OUT.mkdir(exist_ok=True)
    result_path = OUT / 'results.json'
    if result_path.exists():
        result_path.unlink()
    ip = V4 / 'inputs/ipcore/ov5640_cdc_fifo'
    files = [SOURCE, CANDIDATE, HERE / 'tb_camera_tc03.sv', Path(__file__).resolve(), ip / 'ov5640_cdc_fifo.v']
    files += sorted((ip / 'rtl').glob('*.v'))
    files += [PRIMITIVES / 'GTP_DRM18K_E1.v', PRIMITIVES / 'GTP_GRS.v']
    # Byte-level search/decode: source contains GBK comments.
    assert b'module ov5640_cdc #' in SOURCE.read_bytes()
    SOURCE.read_bytes().decode('gbk')
    before = {str(p): sha(p) for p in files}
    protected = list((V4 / 'inputs').rglob('*'))
    protected += list((HERE.parents[2] / 'source').rglob('*'))
    protected += list((HERE.parents[2] / 'ipcore').rglob('*'))
    guard = {str(p): sha(p) for p in protected if p.is_file()}
    # Unique module declaration in the candidate tree and production sources.
    declarations = []
    for base in (HERE / 'rtl', HERE.parents[2] / 'source'):
        for p in base.rglob('*.v'):
            if re.search(rb'\bmodule\s+ov5640_cdc_tc03\b', p.read_bytes()):
                declarations.append(str(p))
    assert declarations == [str(CANDIDATE)], declarations
    if not (OUT / 'work').exists():
        run([SIM / 'vlib.exe', 'work'], 'vlib')
    run([SIM / 'vlog.exe', '-sv', '+incdir+' + str(ip / 'rtl'),
         *[p for p in files if p.suffix in ('.v', '.sv')]], 'compile')
    cases = []
    for cam, video in [(5, 7), (7, 3), (3, 19)]:
        for seed in [1, 29, 202603, 987654]:
            label = f'sim_c{cam}_v{video}_s{seed}'
            data = run([SIM / 'vsim.exe', '-c', '-voptargs=+acc', '-onfinish', 'stop',
                        'work.tb_camera_tc03', f'-gCAM_HALF={cam}', f'-gVIDEO_HALF={video}',
                        f'-gSEED={seed}', '-do', 'onerror {quit -code 1}; run -all; quit -f'], label)
            match = re.search(rb'CAMERA_TC03_PASS ([^\r\n]+)', data)
            if not match:
                raise RuntimeError(data.decode(errors='replace'))
            metrics = {key.decode(): int(value) for key, value in re.findall(rb'(\w+)=(\d+)', match[1])}
            cases.append(metrics)
            print(label, metrics, flush=True)
    assert all(sha(Path(p)) == digest for p, digest in guard.items()), 'protected input changed'
    assert all(sha(Path(p)) == digest for p, digest in before.items()), 'test input changed'
    paths = json.loads((V4 / 'evidence/all_reported_failing_paths.json').read_text())
    camera_paths = [p for p in paths if 'ov5640_cdc/src_' in p['Endpoint']]
    (OUT / 'camera_failing_paths.json').write_text(json.dumps(camera_paths, indent=2))
    (OUT / 'camera_candidate.diff').write_text(''.join(difflib.unified_diff(
        SOURCE.read_bytes().decode('gbk').splitlines(keepends=True),
        CANDIDATE.read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='V4/inputs/source/ov5640/ov5640/ov5640_cdc.v',
        tofile='timing_correction_03/rtl/ov5640_cdc_tc03.v')), encoding='utf-8')
    analysis = [{'number': p['number'], 'endpoint': p['Endpoint'], 'slack_ns': p['Slack'],
                 'ceco_hops': sum('td' in line and '/CECO' in line for line in p['full_detail'].splitlines()),
                 'clock_skew_ns': float(re.search(r'Clock Skew\s*:\s*([-\d.]+)', p['full_detail'])[1])}
                for p in camera_paths]
    (OUT / 'camera_path_analysis.json').write_text(json.dumps(analysis, indent=2))
    results = {'passed': True, 'runs': cases, 'file_sha256': before,
               'total_comparisons': sum(p['comparisons'] for p in cases),
               'total_boundary_cases': sum(p['boundaries'] for p in cases),
               'protected_files_verified': len(guard), 'public_outputs_compared': 8,
               'fifo_model': 'actual frozen V4 IP + PANGO GTP_DRM18K_E1 simulation primitive',
               'boundary_state_deposits': True, 'directed_full_force': True,
               'routed_timing_verified': False, 'pds_invoked': False}
    result_path.write_text(json.dumps(results, indent=2))
    (OUT / 'protected_sha256.json').write_text(json.dumps(guard, indent=2))
    print('PASS: 12 camera differential runs; SHA256', sha(CANDIDATE))

if __name__ == '__main__':
    main()
