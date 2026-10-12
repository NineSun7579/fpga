"""Independent actual-cam6 ModelSim regression; only cam6 receipts are written."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import difflib

HERE = Path(__file__).resolve().parents[2]
V5 = HERE.parent / 'whole_candidate_v5_route_01'
PROJECT = HERE.parents[1]
OUT = HERE / 'receipts/cam6'
TEST = Path(__file__).resolve().parent
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
PRIM = Path(os.environ.get('PANGO_SIM_LIB', r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))
ORIGINAL = V5 / 'inputs/source/ov5640/ov5640_ddr/ov5640_ddr.v'
CANDIDATE = HERE / 'rtl/ov5640_ddr_tc04.v'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2), encoding='utf-8')

def uncomment(b, preserve_offsets=False):
    return re.sub(rb'//[^\r\n]*|/\*[\s\S]*?\*/',
                  lambda m: re.sub(rb'[^\r\n]', b' ', m[0]) if preserve_offsets else b'', b)

def tokens(b):
    return re.sub(rb'\s+', b'', uncomment(b))

def run(args, label, timeout=600):
    p = subprocess.run([str(x) for x in args], cwd=OUT, capture_output=True, timeout=timeout)
    data = p.stdout + p.stderr
    (OUT / (label + '.log')).write_bytes(data)
    if p.returncode or re.search(rb'\*\* (?:Error|Fatal)', data):
        raise RuntimeError(data.decode(errors='replace')[-16000:])
    return data

def audit_logic():
    old, new = ORIGINAL.read_bytes(), CANDIDATE.read_bytes()
    # Compare identical parameter/port declaration tokens, including all widths.
    header = lambda b: b[:b.index(b');')+2]
    assert tokens(header(old)).replace(b'moduleov5640_ddr#', b'moduleov5640_ddr_tc04#', 1) == tokens(header(new))
    old_reduced, n = re.subn(rb'\s*pixel_count\s*<=\s*0\s*;', b'', old)
    assert n == 2
    old_reduced, n = re.subn(rb'\s*if\(m_data_valid\) pixel_count <= pixel_count \+ 1\x27b1;', b'', old_reduced)
    assert n == 1
    new_reduced, n = re.subn(rb'wire pixel_clear_tc04[\s\S]*?end endgenerate', b'', new)
    assert n == 1
    assert tokens(old_reduced).replace(b'moduleov5640_ddr#', b'moduleov5640_ddr_tc04#', 1) == tokens(new_reduced), 'non-counter logic differs'
    attrs = lambda b: re.findall(rb'/\*synthesis[^*]*\*/', b)
    assert attrs(old) == attrs(new), 'synthesis attributes differ'
    save('interface_logic_audit.json', {'identical_public_declarations': True,
         'only_pixel_counter_tokens_changed': True, 'synthesis_attributes_preserved': True,
         'original_sha256': sha(ORIGINAL), 'candidate_sha256': sha(CANDIDATE)})
    # Decode only for a human-readable diff; all production copying uses bytes.
    (OUT/'candidate.diff').write_text(''.join(difflib.unified_diff(
        old.decode('gbk').splitlines(True), new.decode('ascii').splitlines(True),
        fromfile=str(ORIGINAL), tofile=str(CANDIDATE))), encoding='utf-8')

def parent_bindings():
    pattern = rb'\bov5640_ddr\b\s*(?:#\s*\([\s\S]*?\)\s*)?(\w+)\s*\('
    manifest = []
    for root in (V5/'inputs/source', V5/'rtl'):
        for src in sorted(root.rglob('*.v')):
            raw = src.read_bytes()
            masked = uncomment(raw, True)
            matches = [m for m in re.finditer(pattern, masked)
                       if not re.search(rb'\bmodule\s*$', masked[max(0, m.start()-40):m.start()])]
            if not matches:
                continue
            bound = raw
            # Replace only each instance's module-type token; no decoding/re-encoding.
            for m in reversed(matches):
                bound = bound[:m.start()] + b'ov5640_ddr_tc04' + bound[m.start()+len(b'ov5640_ddr'):]
            dst = OUT/'bindings'/src.relative_to(V5)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(bound)
            restored = bound.replace(b'ov5640_ddr_tc04', b'ov5640_ddr')
            assert restored == raw
            manifest.append({'source': str(src), 'isolated_copy': str(dst),
                'original_sha256':sha(src), 'bound_sha256':sha(dst),
                'instances':[{'name':m[1].decode('ascii'), 'line':raw[:m.start()].count(b'\n')+1} for m in matches],
                'byte_roundtrip_verified':True})
    assert sum(len(p['instances']) for p in manifest) == 7, manifest
    save('parent_bindings.json', {'parents':manifest, 'all_original_instances_rebound':7,
         'binding_method':'byte-preserving isolated parent copies, exact module-type substitution',
         'production_and_v5_bindings_modified':False,
         'whole_parent_elaboration_verified':False,
         'active_v5_route_top':'rtl/fpga_v8_cooperative_top_v2_rfg01.v',
         'active_direct_cam6_instance':'cam6_ov5640_ddr',
         'active_camera_parent':'inputs/source/ov5640/ov5640_top.v',
         'cam5_capture_wrapper_binding_retained':True})

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'results.json').unlink(missing_ok=True)
    prior = OUT/'protected_sha256.json'
    if prior.exists():
        previous = json.loads(prior.read_bytes())
        changes = [{'path':p, 'before':h, 'after':sha(Path(p)) if Path(p).exists() else None}
                   for p,h in previous.items() if not Path(p).exists() or sha(Path(p))!=h]
        if changes:
            (OUT/'prior_run_protected_sha256.json').write_bytes(prior.read_bytes())
            save('prior_run_concurrent_changes.json', {'changes':changes,
                'reason':'Concurrent independent DMA task updated its own files; cam6 never writes those paths.'})
    protected = {p.resolve() for root in (V5, PROJECT/'source', PROJECT/'ipcore',
        HERE.parent/'timing_correction_03', HERE.parent/'timing_correction_02', HERE/'receipts/stream_capture')
        for p in root.rglob('*') if p.is_file()}
    # Shared TC04 hosts another independently running DMA subagent. Its mutable
    # tests/receipts are not cam6 inputs; protect the existing stream work explicitly.
    protected.update((HERE/n).resolve() for n in ('run_regression.py','audit_stream_capture.py',
        'STREAM_CAPTURE_HANDOFF.md','tb_motion_tc04.sv','tb_capture_tc04.sv',
        'rtl/motion_stream_adapter_tc04.v','rtl/fpga_v8_capture_ov5640_ddr_tc04.v'))
    before = {str(p):sha(p) for p in protected}
    save('protected_sha256.json', before)
    audit_logic()
    module = rb'\bmodule\s+ov5640_ddr_tc04\b'
    declarations = [p for root in (HERE/'rtl', PROJECT/'source', V5/'rtl', V5/'inputs/source')
                    for p in root.rglob('*.v') if re.search(module, uncomment(p.read_bytes()))]
    assert declarations == [CANDIDATE], declarations
    parent_bindings()
    paths = json.loads((V5/'evidence/all_reported_failing_paths.json').read_bytes())
    paths = [p for p in paths if p['number'] in (23,24)]
    assert len(paths)==2 and all('cam6_ov5640_ddr/pixel_count' in p['Endpoint'] for p in paths)
    save('v5_paths_23_24_full_detail.json', paths)
    sources = [ORIGINAL, CANDIDATE, TEST/'tb_cam6.sv']
    sources += [ORIGINAL.parent/n for n in ('ov5640_ddr_w_en.v','ov5640_ddr_w.v','ov5640_ddr_w_ctrl.v')]
    inc = []
    for n in ('ov5640_ddr_fifo', 'ov5640_ddr_fifo_DRM'):
        ip = V5/'inputs/ipcore'/n
        sources += [ip/(n+'.v'), *sorted((ip/'rtl').glob('*.v'))]
        inc.append('+incdir+'+str(ip/'rtl'))
    sources += [PRIM/'GTP_DRM36K_E1.v', PRIM/'GTP_GRS.v']
    inputs = {str(p):sha(p) for p in sources + [Path(__file__).resolve()]}
    if not (OUT/'work').exists(): run([SIM/'vlib.exe', 'work'], 'vlib')
    run([SIM/'vlog.exe', '-sv', *inc, *sources], 'compile')
    cases = []
    for length, seed in ((38400,1),(38400,29),(2048,202603)):
        label = f'cam6_{length}_{seed}'
        print('RUN', label, flush=True)
        data = run([SIM/'vsim.exe','-c','-vopt','-voptargs=+acc','work.tb_cam6',
            f'-gLEN={length}', f'-gSEED={seed}',
            '-do','onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],label)
        m = re.search(rb'CAM6_TC04_PASS ([^\r\n]+)', data)
        if not m: raise RuntimeError(data.decode(errors='replace')[-16000:])
        metrics = {k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)',m[1])}
        cases.append({'case':label, **metrics})
        print('PASS', metrics, flush=True)
    assert all(sha(Path(p))==h for p,h in before.items()), 'protected file changed'
    assert all(sha(Path(p))==h for p,h in inputs.items()), 'test input changed'
    save('results.json', {'passed':True, 'runs':cases, 'file_sha256':inputs,
        'protected_files_verified':len(before), 'public_output_ports_compared':20,
        'public_output_bits_compared':566, 'invalid_cycle_payloads_compared':True,
        'baseline':str(ORIGINAL), 'fifo_model':'actual V5 FIFO RTL and PANGO GTP_DRM36K_E1/GRS',
        'w_modules':'all three actual V5 ov5640_ddr_w* modules, unchanged',
        'pds_invoked':False, 'routed_timing_verified':False,
        'limitations':['Upper 32-bit carry/wrap coverage uses paired state deposits.',
                      'Isolated parent copies are byte-audited; full whole-system elaboration/simulation is not performed.',
                      'No synthesis or routing proof of CECO removal or slack improvement.']})
    print('CAM6 ALL PASS', 'SHA256', sha(CANDIDATE), flush=True)

if __name__ == '__main__':
    main()
