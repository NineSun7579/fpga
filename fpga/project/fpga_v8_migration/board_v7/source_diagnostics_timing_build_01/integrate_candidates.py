"""Read-only candidate audits; mutate only this isolated build."""
import base64
import csv
import difflib
import re
from pathlib import Path
from preflight import HERE, BOARD, BASE, FROZEN, FROZEN_SHA, load, save, sha, require, frozen_guard, verify

CAM = BOARD / 'camera_read_decode_timing_candidate'
CTL = BOARD / 'capture_control_decode_timing_candidate'
CAM_TARGET = 'inputs/source/ov5640/ov5640_reg.v'
CTL_TARGET = 'rtl/fpga_v8_capture_control_axil_arm_v2.v'
CAM_SHA = '984d8bcbaa41cab792f48b3a3cfc910655508e23c173c68a9091c8a3491d1313'
CTL_SHA = 'e0b7da5c103b376cf576c1e6d6065dacc76bda20dfd13f63f596173a838ea83e'

def inventory(root, file):
    receipt = {}
    for name, expected in load(root / file).items():
        require(sha(root / name) == expected, 'Candidate delivery drift: ' + name)
        receipt[str(root / name)] = expected
    receipt[str(root / file)] = sha(root / file)
    return receipt

def clean_log(path):
    raw = path.read_bytes()
    require(not re.search(rb'(?im)^\s*(?:#\s*)?(?:\*\*\s*)?(?:Error:|Fatal:|E:)', raw), 'Log errors: ' + str(path))
    require(re.search(rb'Errors:\s*0\b', raw), 'No explicit zero errors: ' + str(path))
    return raw

def audit():
    frozen = frozen_guard()
    cam_hashes = inventory(CAM, 'evidence/artifact_hashes.json')
    binding = load(CAM / 'evidence/input_hashes.json')
    require(Path(binding['source']) == BASE / CAM_TARGET, 'Camera actual input binding mismatch')
    require(binding['source_sha256'] == frozen[CAM_TARGET] == sha(BASE / CAM_TARGET), 'Camera frozen source mismatch')
    require(binding['candidate_sha256'] == CAM_SHA == sha(CAM / 'rtl/ov5640_reg.v'), 'Camera candidate identity')
    require(Path(binding['exact09_input_manifest']['path']) == FROZEN
            and binding['exact09_input_manifest']['sha256'] == FROZEN_SHA, 'Camera exact09 binding mismatch')
    for row in binding['input_hash_manifests']:
        require(sha(Path(row['path'])) == row['sha256'], 'Camera historical input manifest drift')
    original = (BASE / CAM_TARGET).read_bytes()
    candidate = (CAM / 'rtl/ov5640_reg.v').read_bytes()
    require(original == (CAM / 'original/ov5640_reg.v').read_bytes(), 'Camera golden differs')
    patch = load(CAM / 'evidence/byte_patch.json')
    rebuilt = original
    for edit in reversed(patch['edits']):
        pos = edit['offset']; old = base64.b64decode(edit['delete_b64']); new = base64.b64decode(edit['insert_b64'])
        require(rebuilt[pos:pos+len(old)] == old, 'Camera byte patch deletion mismatch')
        rebuilt = rebuilt[:pos] + new + rebuilt[pos+len(old):]
    require(rebuilt == candidate, 'Camera byte patch reconstruction failed')
    require((CAM / 'sim/ov5640_reg_reference.v').read_bytes() == original.replace(b'module ov5640_reg #(', b'module ov5640_reg_reference #(', 1), 'Camera reference mismatch')
    require((CAM / 'sim/ov5640_reg_candidate.v').read_bytes() == candidate.replace(b'module ov5640_reg #(', b'module ov5640_reg_candidate #(', 1), 'Camera simulation DUT mismatch')
    log = clean_log(CAM / 'evidence/modelsim_cycle_miter.log')
    require(b'PASS ALL 6 actual-module cycle miters' in log, 'Camera miter incomplete')
    summary = load(CAM / 'evidence/verification_summary.json')
    require(summary['status'] == 'PASS' and summary['trace_all_outputs_mismatch'] == 0
            and summary['cycles_total'] == 130140 and len(summary['pairs']) == 6, 'Camera summary failed')
    for pair in summary['pairs']:
        trace = CAM / ('sim/trace_' + str(pair['pair']) + '.csv')
        require(sha(trace) == pair['trace_sha256'], 'Camera trace hash drift')
        count = 0
        with trace.open(newline='') as f:
            for row in csv.DictReader(f):
                count += 1
                require(int(row['cycle']) == count, 'Camera trace sequence')
                for a, b in [('ref_axi', 'dut_axi'), ('ref_rdata', 'dut_rdata'), ('ref_cam1', 'dut_cam1'), ('ref_all_outputs', 'dut_all_outputs')]:
                    require(row[a] == row[b], 'Camera trace mismatch')
        require(count == pair['cycles'], 'Camera trace cycles')
    ctl_hashes = inventory(CTL, 'delivery_hashes.json')
    inputs = load(CTL / 'input_hashes.json')
    require(inputs == load(CTL / 'input_hashes_after.json'), 'Control input manifests differ')
    for path, expected in inputs.items():
        require(sha(Path(path)) == expected, 'Control frozen dependency drift')
        if Path(path).is_relative_to(BASE):
            require(frozen[Path(path).relative_to(BASE).as_posix()] == expected, 'Control exact09 mismatch')
    require(inputs[str(BASE / CTL_TARGET)] == frozen[CTL_TARGET], 'Control source binding mismatch')
    require(sha(CTL / ('candidate/' + Path(CTL_TARGET).name)) == CTL_SHA, 'Control candidate identity')
    result = load(CTL / 'artifacts/results.json')
    require(result['status'] == 'PASS' and result['input_hashes_unchanged'] is True
            and len(result['signals_compared']) == 49 and len(result['runs']) == 18, 'Control result failed')
    cycles = 0
    require(len({(r['base'], r['seed']) for r in result['runs']}) == 18, 'Duplicate control test')
    for run in result['runs']:
        data = clean_log(CTL / ('artifacts/' + run['base'] + '_' + str(run['seed']) + '.log'))
        require(len(run['pass_line']) == 1 and run['pass_line'][0].encode() in data, 'Control PASS missing')
        cycles += int(re.search(r'cycles=(\d+)', run['pass_line'][0]).group(1))
    require(cycles == 861948, 'Control cycle coverage mismatch')
    clean_log(CTL / 'artifacts/compile.log')
    integration = clean_log(CTL / 'artifacts/integration/modelsim.log')
    require(result['integration']['operations'] == 499 and result['integration']['events'] == 4288
            and b'CAPTURE_ENDPOINT_PASS ops=499 cycles=26488' in integration, 'Control integration incomplete')
    for line in result['integration']['pass_line']:
        require(line.encode() in integration, 'Control integration marker missing')
    return {'status': 'PASS', 'camera_cycles': 130140, 'trace_mismatches': 0,
            'control_runs': 18, 'control_cycles': cycles, 'signals': 49,
            'integration_cycles': 26488, 'integration_operations': 499,
            'hashes': {**cam_hashes, **ctl_hashes}}

def main():
    verify()
    evidence = audit()
    manifest = load(HERE / 'manifest.json')
    require('decode_candidates_gate' not in manifest, 'Already integrated')
    save('manifest_before_decode.json', manifest)
    for target, source in [(CAM_TARGET, CAM / 'rtl/ov5640_reg.v'),
                           (CTL_TARGET, CTL / 'candidate/fpga_v8_capture_control_axil_arm_v2.v')]:
        require(target in manifest['registered_sources'], 'Target not registered: ' + target)
        old = (HERE / target).read_bytes(); new = source.read_bytes()
        require(old == (BASE / target).read_bytes(), 'Local old target mismatch')
        diff = ''.join(difflib.unified_diff(old.decode('latin1').splitlines(True), new.decode('latin1').splitlines(True), fromfile='route02/' + target, tofile='isolated/' + target))
        (HERE / (Path(target).stem + '.diff')).write_bytes(diff.encode('latin1'))
        (HERE / target).write_bytes(new)
        manifest['local_hashes'][target] = sha(HERE / target)
        manifest['changes'].append({'path': target, 'before': sha(BASE / target), 'after': sha(source), 'edit': 'audited byte-exact candidate, same module/registration/parent'})
    manifest['decode_candidates_gate'] = evidence
    manifest['pending'] = [p for p in manifest['pending'] if not p.startswith(('camera_read_decode:', 'capture_control_decode:'))]
    manifest['mode'] = 'CANDIDATES_INTEGRATED_PHYSICAL_NOT_SIGNED'
    save('manifest.json', manifest)
    save('candidate_integration_audit.json', evidence)
    verify()

if __name__ == '__main__':
    main()
