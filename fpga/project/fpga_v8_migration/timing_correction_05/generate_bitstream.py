"""V7 local generation after actual TC05 + inherited gates; never flashes."""
from pathlib import Path
import json
from run_whole import HERE, M, WORK, sha
from accept_regressions import verify_regressions as verify_tc05
from reuse import load


def verify_regressions():
    verify_tc05(WORK)
    # TC03 adapter and historical motion receipts remain fully checked; only
    # the obsolete deployed-TC03-detector equality is replaced by TC05 binding.
    return load('generate_bitstream.py')['verify_regressions']()


def main():
    acceptance = verify_tc05(WORK)
    frozen = json.loads((WORK / 'tc05_regression_acceptance.json').read_bytes())
    assert acceptance == frozen, 'TC05 accepted receipt changed since build'
    verify_regressions()
    load('generate_bitstream.py', record=True)['main']()
    manifest_path = WORK / 'delivery_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    result_path = Path(acceptance['detector_result'])
    result = json.loads(result_path.read_bytes())
    target = WORK / 'regression_receipts/tc05_detector'
    target.mkdir()
    # Preserve the original simulator receipts byte-for-byte, including logs,
    # generated benches and before-input hashes, rather than only a PASS flag.
    for name in ['results.json', *result['artifacts']]:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((result_path.parent / name).read_bytes())
        manifest['evidence'][str(path.relative_to(WORK))] = sha(path)
    for name in ['tc05_regression_acceptance.json', 'baseline_before.json', 'v6_failing_paths.json',
                 'reuse_export_whole.py.json', 'reuse_generate_bitstream.py.json', 'inputs_before.json', 'inputs_after.json']:
        manifest['evidence'][name] = sha(WORK / name)
    manifest['candidate_revision'] = 'V7'
    manifest['tc05_detector_result_sha256'] = sha(result_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
