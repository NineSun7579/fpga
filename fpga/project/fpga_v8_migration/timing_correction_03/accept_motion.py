"""Review completed motion receipts and bind them to the tested candidate."""
import json
from run_whole import HERE, sha


def main():
    runs = []
    for path in (HERE / 'motion').glob('run_*/results.json'):
        receipt = json.loads(path.read_bytes())
        if receipt['status'] == 'PASS':
            runs.append((path, receipt))
    assert len(runs) == 1, 'Require one successful reviewed motion attempt'
    path, receipt = runs[0]
    assert len(receipt['paired_counts']) == 5
    assert all(r['original_cycles'] > 0 and r['original_cycles'] == r['v4_cycles']
               for r in receipt['paired_counts'])
    hashes = {str(path): sha(path), receipt['candidate']: receipt['candidate_sha256']}
    for name, digest in receipt['artifacts'].items():
        target = path.parent / name
        assert sha(target) == digest, name
        hashes[str(target)] = digest
    four = json.loads((path.parent / 'four_regression_result.json').read_bytes())
    assert four['status'] == 'PASS' and four['candidate_sha256'] == receipt['candidate_sha256']
    assert 'PASS tb_four_motion:' in (path.parent / 'four/four_motion.log').read_text(errors='replace')
    assert 'PASS ALL block_motion_detector self-checks' in (path.parent / 'paired/motion.log').read_text(errors='replace')
    from pathlib import Path
    for name, digest in {**receipt['reused_runners'], **four['source_hashes']}.items():
        assert sha(Path(name)) == digest, name
        hashes[name] = digest
    assert sha(HERE / 'rtl/block_motion_detector_tc03.v') == receipt['candidate_sha256']
    result = {'passed': True, 'four_camera_integration_passed': True,
              'file_sha256': hashes, 'routed_timing_verified': False}
    (HERE / 'motion_acceptance.json').write_text(json.dumps(result, indent=2))
    print('PASS motion receipts, logs and tested hashes reviewed', flush=True)


if __name__ == '__main__':
    main()
