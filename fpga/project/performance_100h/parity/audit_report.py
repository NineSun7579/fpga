"""Independently audit a completed parity receipt and its retained raw RKNN logs."""
import argparse
import hashlib
import json
from pathlib import Path
from compare import compare

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    request = json.loads((args.report.parent / 'request.json').read_text(encoding='utf-8'))
    assert report['manifest_sha256'] == sha(HERE / 'manifest.json')
    assert report['events'][-1] == dict(state='finished', hashes_verified_before_after=True)
    assert request['model'] == next(iter(manifest['assets']))
    assert all(request['pins'][path] == digest for path, digest in manifest['assets'].items())
    results = [e for e in report['events'] if e['state'] == 'result']
    assert len(results) == 2 * len(manifest['scenes']) and all(e['rc'] == 0 for e in results)
    audit = {'report_sha256': sha(args.report), 'status': report['status'],
             'model_pins': manifest['assets'], 'scenes': {}, 'logs_sha256': {}}
    for kind, harness in manifest['harnesses'].items():
        receipt = report['builds'][kind]
        assert receipt['status'] == 'built'
        assert receipt['source_sha256'] == harness['source_sha256']
        assert receipt['snapshot_sha256'] == harness['snapshot_sha256']
        assert request['pins'][receipt['binary']] == receipt['binary_sha256']
        assert 'make -j1' in receipt['command']
    for name, scene in manifest['scenes'].items():
        assert sha(HERE / scene['path']) == scene['sha256']
        assert request['pins'][report['remote_directory'] + '/' + scene['path']] == scene['sha256']
        logs = {kind: args.report.parent / (name + '_' + kind + '.log')
                for kind in ('baseline', 'candidate')}
        comparison = compare(*(logs[k].read_text(encoding='utf-8') for k in ('baseline', 'candidate')))
        assert comparison == report['comparisons'][name]
        audit['scenes'][name] = {k: v for k, v in comparison.items() if not k.endswith('_frames')}
        for kind, path in logs.items():
            audit['logs_sha256'][path.name] = sha(path)
    assert report['status'] in ('match', 'mismatch', 'empty_only_inconclusive')
    if report['status'] == 'match':
        assert all(c['tolerance_match'] for c in audit['scenes'].values())
        assert any(c['positive_detection_evidence'] for c in audit['scenes'].values())
    audit['audit_passed'] = True
    target = args.report.parent / 'audit.json'
    target.write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
