"""Standalone camera-only TC04 regression. Does not call PDS or whole runners."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V5 = HERE.parent / 'whole_candidate_v5_route_01'
V4 = HERE.parent / 'whole_candidate_v4_route_01'
REFERENCE = V5 / 'rtl/ov5640_cdc_tc03.v'
CANDIDATE = HERE / 'rtl/ov5640_cdc_tc04.v'
OUT = HERE / 'camera_artifacts'
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
PRIMITIVES = Path(os.environ.get('PANGO_SIM_LIB', r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))

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
    result_path.unlink(missing_ok=True)
    ip = V4 / 'inputs/ipcore/ov5640_cdc_fifo'
    files = [REFERENCE, CANDIDATE, HERE / 'tb_camera_tc04.sv', Path(__file__).resolve(), ip / 'ov5640_cdc_fifo.v']
    files += sorted((ip / 'rtl').glob('*.v'))
    files += [PRIMITIVES / 'GTP_DRM18K_E1.v', PRIMITIVES / 'GTP_GRS.v']
    assert b'module ov5640_cdc_tc03 #' in REFERENCE.read_bytes()
    assert b'module ov5640_cdc_tc04 #' in CANDIDATE.read_bytes()
    tb = (HERE / 'tb_camera_tc04.sv').read_bytes()
    assert b'ov5640_cdc_tc03 #(.DATA_WIDTH(16)) reference_dut' in tb
    assert b'ov5640_cdc_tc04 #(.DATA_WIDTH(16)) candidate_dut' in tb
    # GBK source is always searched and hashed as bytes; never rewritten.
    declarations = []
    assert (ROOT / 'source').is_dir() and (ROOT / 'ipcore').is_dir()
    for base in (HERE / 'rtl', ROOT / 'source'):
        for p in base.rglob('*.v'):
            if re.search(rb'\bmodule\s+ov5640_cdc_tc04\b', p.read_bytes()):
                declarations.append(str(p))
    assert declarations == [str(CANDIDATE)], declarations
    before = {str(p): sha(p) for p in files}
    protected = {}
    for base in (ROOT / 'source', ROOT / 'ipcore', V5, HERE.parent / 'timing_correction_03'):
        for p in base.rglob('*'):
            if p.is_file():
                protected[str(p)] = sha(p)
    if not (OUT / 'work').exists():
        run([SIM / 'vlib.exe', 'work'], 'vlib')
    run([SIM / 'vlog.exe', '-sv', '+incdir+' + str(ip / 'rtl'),
         *[p for p in files if p.suffix in ('.v', '.sv')]], 'compile')
    cases = []
    for cam, video in [(5, 7), (7, 3), (3, 19)]:
        for seed in [1, 29, 202603, 987654]:
            label = f'sim_c{cam}_v{video}_s{seed}'
            data = run([SIM / 'vsim.exe', '-c', '-voptargs=+acc', '-onfinish', 'stop',
                        'work.tb_camera_tc04', f'-gCAM_HALF={cam}', f'-gVIDEO_HALF={video}',
                        f'-gSEED={seed}', '-do', 'onerror {quit -code 1}; run -all; quit -f'], label)
            match = re.search(rb'CAMERA_TC04_PASS ([^\r\n]+)', data)
            if not match:
                raise RuntimeError(data.decode(errors='replace'))
            metrics = {k.decode(): int(v) for k, v in re.findall(rb'(\w+)=(\d+)', match[1])}
            cases.append(metrics)
            print(label, metrics, flush=True)
    assert all(sha(Path(p)) == h for p, h in protected.items()), 'protected input changed'
    assert all(sha(Path(p)) == h for p, h in before.items()), 'regression input changed'
    paths = json.loads((V5 / 'evidence/all_reported_failing_paths.json').read_bytes())
    camera_paths = [p for p in paths if 'ov5640_cdc/src_' in p['Endpoint']]
    (OUT / 'camera_failing_paths.json').write_text(json.dumps(camera_paths, indent=2))
    results = dict(passed=True, runs=cases, file_sha256=before,
                   reference=str(REFERENCE), candidate=str(CANDIDATE),
                   total_comparisons=sum(c['comparisons'] for c in cases),
                   total_boundary_cases=sum(c['boundaries'] for c in cases),
                   protected_files_verified=len(protected), public_outputs_compared=8,
                   fifo_model='actual frozen V4 IP + PANGO GTP_DRM18K_E1',
                   predictor_invariant_checked_every_comparison=True,
                   deposits_maintain_prediction_state=True,
                   natural_carry_without_deposits_or_force=True,
                   routed_timing_verified=False, pds_invoked=False)
    result_path.write_text(json.dumps(results, indent=2))
    print('PASS: 12 completed camera differential runs; SHA256', sha(CANDIDATE))

if __name__ == '__main__':
    main()
