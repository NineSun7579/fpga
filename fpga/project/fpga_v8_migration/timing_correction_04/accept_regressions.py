"""Bind reviewed TC04 test evidence to all six whole-build candidates."""
import json
from pathlib import Path
from run_whole import HERE, MODULES, sha


def main():
    hashes = {}

    def load(name):
        path = HERE / name
        hashes[str(path)] = sha(path)
        return json.loads(path.read_bytes())

    def verify(mapping, root=None):
        for name, digest in mapping.items():
            path = Path(name) if root is None else root / name
            assert sha(path) == digest, str(path)
            hashes[str(path)] = digest

    camera = load('camera_artifacts/results.json')
    assert camera['passed'] and len(camera['runs']) == 12
    assert camera['predictor_invariant_checked_every_comparison']
    assert all(r['natural_count_carries'] and r['natural_drop_carries'] for r in camera['runs'])
    verify(camera['file_sha256'])
    lease = load('receipts/lease/results.json')
    assert lease['pass_all'] and lease['protected_unchanged'] and len(lease['results']) == 9
    assert len(lease['public_outputs']) == 36
    assert all('LEASE_TC04_DIFF_PASS' in text for text in lease['results'].values())
    verify(lease['test_sha256'], HERE / 'tests')
    stream = load('receipts/stream_capture/results.json')
    stream_audit = load('receipts/stream_capture/final_audit.json')
    assert stream['passed'] and stream['four_channel_oracle_passed'] and stream_audit['passed']
    assert stream_audit['four_channel_phases'] == 10
    assert stream_audit['results_sha256'] == hashes[str(HERE / 'receipts/stream_capture/results.json')]
    verify(stream['file_sha256'])
    cam6 = load('receipts/cam6/results.json')
    cam6_audit = load('receipts/cam6/final_audit.json')
    assert cam6['passed'] and cam6_audit['passed']
    assert cam6_audit['results_sha256'] == hashes[str(HERE / 'receipts/cam6/results.json')]
    assert cam6_audit['all_parent_instances_byte_verified']
    assert cam6_audit['actual_fifo_and_w_modules_loaded']
    verify(cam6['file_sha256'])
    dma = load('receipts/dma/results.json')
    dma_audit = load('receipts/dma/final_audit.json')
    assert dma['status'] == 'PASS' and dma_audit['status'] == 'PASS'
    assert dma['original_cases'] == 160 and len(dma['simulations']) == 10
    assert dma['unchanged_non_watchdog_tokens'] and dma['all_public_outputs_including_invalid_payloads']
    verify(load('receipts/dma/artifact_sha256.json'))
    # Retain and hash every final test log as well as each machine receipt.
    for folder in ['camera_artifacts', 'receipts/lease', 'receipts/stream_capture', 'receipts/cam6', 'receipts/dma']:
        for path in (HERE / folder).rglob('*.log'):
            if 'work' not in path.parts and 'work_registers' not in path.parts:
                data = path.read_bytes()
                assert b'** Fatal:' not in data and b'** Error:' not in data, str(path)
                hashes[str(path)] = sha(path)
    candidates = {new: sha(HERE / 'rtl' / (new + '.v')) for new, oldpath in MODULES.values()}
    assert candidates['fpga_v8_capture_lease_tc04'] == lease['candidate_sha256']
    assert candidates['ov5640_ddr_tc04'] == cam6_audit['candidate_sha256']
    assert candidates['axi_dma_write_tc04'] == dma['candidate_sha256']
    for new in candidates:
        path = HERE / 'rtl' / (new + '.v')
        assert hashes.get(str(path), candidates[new]) == candidates[new]
        hashes[str(path)] = candidates[new]
    result = {'passed': True, 'modules': sorted(candidates), 'candidate_sha256': candidates,
              'file_sha256': hashes, 'routed_timing_verified': False, 'programming_performed': False}
    (HERE / 'regression_acceptance.json').write_text(json.dumps(result, indent=2))
    print('PASS reviewed six TC04 candidates and regression evidence hashes', flush=True)


if __name__ == '__main__':
    main()
