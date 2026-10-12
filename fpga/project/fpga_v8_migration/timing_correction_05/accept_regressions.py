"""Read-only TC05 future-result gate; never runs simulation or PDS."""
from pathlib import Path
import json
import re
import hashlib

HERE = Path(__file__).resolve().parent
M = HERE.parent
TC04 = M / 'timing_correction_04'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_detector(work=None, result_path=None):
    if result_path is None:
        completed = sorted((HERE / 'receipts').glob('detector_*/results.json'))
        assert completed, 'TC05 real detector results.json not ready; no acceptance claimed'
        result_path = completed[-1]
    result_path = Path(result_path).resolve()
    assert result_path.parent.parent == (HERE / 'receipts').resolve()
    result = json.loads(result_path.read_bytes())
    candidate = HERE / 'rtl/block_motion_detector_tc05.v'
    assert result['status'] == 'PASS'
    assert Path(result['candidate']).resolve() == candidate.resolve()
    assert sha(candidate) == result['candidate_sha256']
    assert result['protected_hashes_unchanged'] is True
    assert result['protected_files_verified'] > 0
    assert result['pds_invoked'] is False and result['flashing_invoked'] is False
    assert result['physical_timing_verified'] is False
    inputs = result['compile_sources']
    assert inputs[str(candidate)] == sha(candidate)
    runner = HERE / 'tests/run_detector.py'
    assert inputs[str(runner)] == sha(runner)
    for name, digest in inputs.items():
        assert sha(Path(name)) == digest, name
    artifacts = result['artifacts']
    expected = {'vlib.log', 'compile.log', 'paired.log', 'stress.log', 'four.log',
                'integration_640_480_1.log', 'integration_640_480_29.log',
                'integration_64_48_202603.log', 'compile_sources.json',
                'protected_before.json', 'candidate.diff', 'v6_failing_paths.json'}
    assert expected <= set(artifacts)
    for name, digest in artifacts.items():
        path = result_path.parent / name
        assert path.resolve().is_relative_to(result_path.parent)
        assert sha(path) == digest, name
        if path.suffix == '.log':
            assert not re.search(rb'\*\* (?:Error|Fatal):', path.read_bytes()), name
    assert json.loads((result_path.parent / 'compile_sources.json').read_bytes()) == inputs
    protected = json.loads((result_path.parent / 'protected_before.json').read_bytes())
    assert len(protected) == result['protected_files_verified']
    assert all(sha(Path(p)) == h for p, h in protected.items())
    markers = {'paired.log': (b'TC05_PAIRED W=', 5, b'PASS ALL block_motion_detector self-checks'),
               'stress.log': (b'TC05_STRESS W=', 8, b'PASS TC05 STRESS ALL')}
    for name, (marker, count, passed) in markers.items():
        data = (result_path.parent / name).read_bytes()
        assert data.count(marker) == count and passed in data
        rows = re.findall(rb'checks=(\d+) writes=(\d+) resets=(\d+)', data)
        assert len(rows) == count and all(all(int(n) > 0 for n in row) for row in rows)
    for name in ['integration_640_480_1.log', 'integration_640_480_29.log', 'integration_64_48_202603.log']:
        assert b'MOTION_TC04_PASS' in (result_path.parent / name).read_bytes()
    four = (result_path.parent / 'four.log').read_bytes()
    assert b'PASS tb_four_motion: four default 640x480 adapters' in four
    phases = re.findall(rb'PASS four-motion phase (\d+):', four)
    assert [int(n) for n in phases] == list(range(1, 11))
    cycles = re.search(rb'PASS tb_four_motion:[^\r\n]*cycles=(\d+)', four)
    assert cycles and int(cycles[1]) > 0 and b'Errors: 0, Warnings: 0' in four
    if work is not None:
        assert sha(work / 'rtl/block_motion_detector_tc05.v') == result['candidate_sha256']
    return result_path, result


def verify_regressions(work=None):
    reviewed = json.loads((TC04 / 'regression_acceptance.json').read_bytes())
    expected = {'ov5640_cdc_tc04', 'fpga_v8_capture_lease_tc04', 'motion_stream_adapter_tc04',
                'fpga_v8_capture_ov5640_ddr_tc04', 'ov5640_ddr_tc04', 'axi_dma_write_tc04'}
    assert reviewed['passed'] and set(reviewed['modules']) == expected
    assert set(reviewed['candidate_sha256']) == expected
    assert all(sha(Path(p)) == h for p, h in reviewed['file_sha256'].items())
    for name, digest in reviewed['candidate_sha256'].items():
        assert sha(TC04 / 'rtl' / (name + '.v')) == digest
        if work is not None:
            assert sha(work / 'rtl' / (name + '.v')) == digest
    path, detector = verify_detector(work)
    return {'passed': True, 'tc04_acceptance_sha256': sha(TC04 / 'regression_acceptance.json'),
            'tc04_candidate_sha256': reviewed['candidate_sha256'],
            'detector_result': str(path), 'detector_result_sha256': sha(path),
            'candidate_sha256': detector['candidate_sha256'],
            'programming_performed': False, 'physical_timing_verified': False}


if __name__ == '__main__':
    print(json.dumps(verify_regressions(), indent=2))
