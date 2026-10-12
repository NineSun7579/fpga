"""Final audit of a completed TC05 run; read-only outside TC05 receipts."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parents[1]
EXPECTED_SHA = 'bbf431ff5268e6c9342a0154961bb2fe02637539925529151955544282ee2139'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_bytes())


def log(p):
    data = p.read_bytes()
    text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode(errors='replace')
    assert not re.search(r'\*\* (?:Error|Fatal):', text), str(p)
    return text


def main():
    run = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else sorted(
        (HERE / 'receipts').glob('detector_*/compile_sources.json'))[-1].parent
    report = HERE / 'receipts/acceptance.json'
    candidate = HERE / 'rtl/block_motion_detector_tc05.v'
    try:
        result_file = run / 'results.json'
        assert result_file.is_file(), 'Completed runner results.json missing; inspect run logs/transcript'
        result = load(result_file)
        assert result['status'] == 'PASS'
        assert result['candidate_sha256'] == sha(candidate) == EXPECTED_SHA
        assert result['pds_invoked'] is False and result['flashing_invoked'] is False
        before = load(run / 'protected_before.json')
        changes = [p for p,h in before.items() if not Path(p).is_file() or sha(Path(p)) != h]
        assert not changes, 'Protected inputs changed: ' + repr(changes)
        compiled = load(run / 'compile_sources.json')
        changes = [p for p,h in compiled.items() if not Path(p).is_file() or sha(Path(p)) != h]
        assert not changes, 'Compiled sources/checker/runner changed: ' + repr(changes)
        assert result['compile_sources'] == compiled
        assert result['protected_files_verified'] == len(before)
        for name,h in result['artifacts'].items():
            assert sha(run / name) == h, 'Receipt artifact changed: ' + name
        assert 'Errors: 0, Warnings: 0' in log(run / 'compile.log')
        paired = log(run / 'paired.log')
        assert 'PASS ALL block_motion_detector self-checks' in paired
        pattern = r'TC05_PAIRED W=(\d+) H=(\d+) STEP=(\d+) checks=(\d+) writes=(\d+) resets=(\d+)'
        pairs = [dict(zip(('width','height','step','checks','writes','reset_checks'),map(int,m)))
                 for m in re.findall(pattern, paired)]
        assert len(pairs) == 5
        assert sorted((m['width'],m['height'],m['step']) for m in pairs) == sorted(
            [(21,13,4),(5,3,1),(1,1,1),(640,480,4),(640,480,4)])
        assert all(m['checks'] > 0 and m['writes'] > 0 and m['reset_checks'] > 0 for m in pairs)
        full_pairs = [m for m in pairs if m['width'] == 640]
        assert all(m['checks'] > 5000000 and m['writes'] >= 300000 for m in full_pairs)
        stress = log(run / 'stress.log')
        assert 'PASS TC05 STRESS ALL' in stress
        stresses = [dict(zip(('width','height','step','checks','writes','reset_checks'),map(int,m)))
                    for m in re.findall(pattern.replace('TC05_PAIRED','TC05_STRESS'), stress)]
        assert len(stresses) == 8 and all(m['checks'] > 24000 and m['writes'] > 0 and m['reset_checks'] >= 44 for m in stresses)
        assert sorted((m['width'],m['height'],m['step']) for m in stresses) == sorted(
            [(5,3,1),(1,1,1),(7,5,3),(1,7,2),(9,1,2),(3,2,5),(16,8,4),(17,11,3)])
        integrations = []
        for w,h,seed in [(640,480,1),(640,480,29),(64,48,202603)]:
            p = run / f'integration_{w}_{h}_{seed}.log'
            text = log(p)
            match = re.search(r'MOTION_TC04_PASS ([^\r\n]+)', text)
            assert match, str(p)
            counts = {k:int(v) for k,v in re.findall(r'(\w+)=(\d+)', match[1])}
            assert counts['records'] >= 6 and counts['fires'] >= 6*w*h
            assert all(counts[k] > 0 for k in ('overflows','shorts','boundaries'))
            integrations.append({'width':w,'height':h,'seed':seed,**counts,'log_sha256':sha(p)})
        four = log(run / 'four.log')
        marker = re.search(r'PASS tb_four_motion: ([^\r\n]+)', four)
        assert marker and 'four default 640x480 adapters' in marker[1]
        assert 'end+2 core/end+3 capture' in marker[1] and 'four frozen snapshots' in marker[1]
        four_cycles = int(re.search(r'cycles=(\d+)', marker[1])[1])
        assert four_cycles > 3000000
        structure_file = HERE / 'receipts/structure.json'
        structure = load(structure_file)
        assert structure['status'] == 'PASS' and structure['candidate_sha256'] == EXPECTED_SHA
        assert structure['baseline_history_drm36k'] == 32 and structure['tc05_mapped_resource_count_measured'] is False
        fault_file = HERE / 'receipts/monitor_fault_20261006_121215_129631/results.json'
        fault = load(fault_file)
        assert fault['status'] == 'PASS'
        fault_log = fault_file.parent / 'fault.log'
        assert b'TC05 lookahead invariant' in fault_log.read_bytes() and b'Time: 47 ns' in fault_log.read_bytes()
        fault_inputs_ok = all(sha(Path(p)) == h for p,h in fault['inputs'].items())
        assert fault_inputs_ok
        acceptance = {'status':'PASS', 'audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'candidate':str(candidate),'candidate_sha256':EXPECTED_SHA,
            'completed_results':str(result_file),'completed_results_sha256':sha(result_file),
            'run_directory':str(run),'paired_geometries':pairs,
            'paired_baselines':'original frozen RTL, TC01, TC03; all 11 public outputs each cycle including reset',
            'history_checks':'same-edge enable/address/luma, read-first history_q, written byte; full retained array at markers/reset',
            'stress_geometries':stresses,'tc04_adapter_integration':integrations,
            'four_integration':{'width':640,'height':480,'channels':4,'cycles':four_cycles,
                'checked_publications':[10,10,9,10], 'timing':'end+2 core/end+3 capture',
                'atomic_records_and_frozen_snapshots':True,'unused_slots_4_5_zero':True,
                'log_sha256':sha(run / 'four.log')},
            'negative_control':{'results':str(fault_file),'results_sha256':sha(fault_file),'fault_detected_ns':47},
            'structure':{'receipt':str(structure_file),'sha256':sha(structure_file)},
            'protected_files_verified':len(before),'protected_hashes_unchanged':True,
            'compiled_source_hashes_unchanged':True,'receipt_artifact_hashes_unchanged':True,
            'pds_invoked':False,'flashing_invoked':False,'physical_timing_verified':False,
            'history_drm_intent':32,'tc05_mapped_drm_measured':False,
            'design_rationale':str(HERE / 'receipts/design_rationale.md'),
            'integration_instruction':'Register block_motion_detector_tc05.v and bind intended motion detectors to unique module block_motion_detector_tc05. No new module dependencies. Exclude generated test-only adapters/benches.',
            'remaining_risk':'Main must synthesize/route and verify 32 history DRM plus setup/hold including the new eligibility-D path. No timing exceptions or clock reduction.'}
        report.write_bytes((json.dumps(acceptance,indent=2)+'\n').encode('ascii'))
        print(json.dumps({'status':'PASS','acceptance':str(report),'acceptance_sha256':sha(report),
                          'results':str(result_file),'results_sha256':sha(result_file),
                          'candidate_sha256':EXPECTED_SHA,'protected_files_verified':len(before)},indent=2), flush=True)
    except Exception as exc:
        failure = {'status':'FAIL','run_directory':str(run),'reason':str(exc),
                   'candidate_sha256':sha(candidate),'pds_invoked':False,
                   'logs_present':[p.name for p in run.glob('*.log')]}
        p = HERE / 'receipts/acceptance_failure.json'
        p.write_bytes((json.dumps(failure,indent=2)+'\n').encode('ascii'))
        print(json.dumps(failure,indent=2), flush=True)
        raise


if __name__ == '__main__':
    main()
