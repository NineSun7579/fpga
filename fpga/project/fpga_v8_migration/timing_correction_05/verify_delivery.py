"""Independent V7 raw ten-group STA, physical and original-receipt audit."""
from pathlib import Path
import json
from run_whole import HERE, M, WORK, BASE, sha, baseline_inventory
from accept_regressions import verify_regressions
from reuse import load


def main():
    accepted = verify_regressions(WORK)
    assert accepted == json.loads((WORK / 'tc05_regression_acceptance.json').read_bytes())
    manifest = json.loads((WORK / 'delivery_manifest.json').read_bytes())
    assert manifest['candidate_revision'] == 'V7'
    assert manifest['programming_performed'] is False and manifest['board_verified'] is False
    required = {'tc05_regression_acceptance.json', 'baseline_before.json', 'v6_failing_paths.json',
                'reuse_export_whole.py.json', 'reuse_generate_bitstream.py.json', 'inputs_before.json', 'inputs_after.json',
                'regression_receipts/tc05_detector/results.json'}
    assert required <= {p.replace('\\', '/') for p in manifest['evidence']}
    result_path = Path(accepted['detector_result'])
    result = json.loads(result_path.read_bytes())
    assert sha(result_path) == manifest['tc05_detector_result_sha256'] == accepted['detector_result_sha256']
    for name in ['results.json', *result['artifacts']]:
        relative = 'regression_receipts/tc05_detector/' + name
        assert relative in {p.replace('\\', '/') for p in manifest['evidence']}
        assert (WORK / relative).read_bytes() == (result_path.parent / name).read_bytes()
    assert baseline_inventory() == json.loads((WORK / 'baseline_before.json').read_bytes())
    assert (WORK / 'v6_failing_paths.json').read_bytes() == (BASE / 'evidence/all_reported_failing_paths.json').read_bytes()
    originals = {
        'tc04_acceptance.json': M / 'timing_correction_04/regression_acceptance.json',
        'transport.json': M / 'timing_correction_02/artifacts/results.json',
        'fifo_binding.json': M / 'timing_correction_02/binding.json',
        'guarded_fifo.json': M / 'timing_correction_02/guarded_artifacts/results.json',
        'reset_guard.json': M / 'reset_fault_guard_02/artifacts/results.json',
    }
    for name, original in originals.items():
        assert (WORK / 'regression_receipts' / name).read_bytes() == original.read_bytes(), name
    # The inherited verifier reparses all ten nonempty raw STA groups, checks
    # physical pin rows, HSST, 32 DRM/614400 bits, hashes and inherited receipts.
    load('verify_delivery.py')['main']()
    print('PASS V7 original TC05/inherited receipts, raw STA and frozen V6 evidence', flush=True)


if __name__ == '__main__':
    main()
