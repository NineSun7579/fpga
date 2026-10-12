import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    diagnostic = args.source.resolve()
    provenance = json.loads((HERE / 'board_provenance_readonly.json').read_text(encoding='utf-8'))
    prefix = '/userdata/linaro/detview-calibration-work/src/'
    records = {record['path'][len(prefix):]: record for record in provenance['files']
               if record['path'].startswith(prefix)}
    project = (HERE / 'retained_detview.pro').read_bytes()
    if digest(project) != records['detview.pro']['sha256']:
        raise RuntimeError('Retained project hash differs from original snapshot')
    snapshot = Path(tempfile.mkdtemp(prefix='build_inputs_', dir=HERE))
    manifest = {}
    changed = []
    for name, record in records.items():
        if name in ('detview.pro', 'stereo_pairs.example.json'):
            continue
        if 'text' not in record:
            raise RuntimeError('Missing retained source: ' + name)
        original = record['text'].encode('utf-8')
        if digest(original) != record['sha256']:
            raise RuntimeError('Retained source hash mismatch: ' + name)
        candidate = diagnostic / name
        data = candidate.read_bytes() if candidate.exists() else original
        if digest(data) != record['sha256']:
            changed.append(name)
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest[name] = {'original_sha256': record['sha256'], 'candidate_sha256': digest(data)}
    if changed != ['main.cpp']:
        raise RuntimeError('Expected only main.cpp instrumentation; actual changes: ' + str(changed))
    for path in diagnostic.rglob('*'):
        if not path.is_file():
            continue
        name = path.relative_to(diagnostic).as_posix()
        if name in records or path.suffix not in ('.h', '.hpp', '.cpp'):
            continue
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        manifest[name] = {'candidate_sha256': digest(target.read_bytes()), 'new': True}
    (snapshot / 'detview.pro').write_bytes(project)
    sdk = next(record for record in provenance['files']
               if record['path'] == '/userdata/linaro/detview-calibration-work/sdk/rknn_api.h')
    sdk_data = sdk['text'].encode('utf-8')
    if digest(sdk_data) != sdk['sha256']:
        raise RuntimeError('RKNN header hash mismatch')
    (snapshot / 'rknn_api.h').write_bytes(sdk_data)
    manifest['detview.pro'] = {'candidate_sha256': digest(project)}
    manifest['rknn_api.h'] = {'candidate_sha256': digest(sdk_data), 'retained_sdk': True}
    status = {'status': 'source_verified', 'source': str(snapshot), 'manifest': manifest,
              'instrumented_files': changed, 'original_binary_sha256': '0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153'}
    receipt = snapshot.with_name(snapshot.name + '_receipt.json')
    receipt.write_text(json.dumps(status, indent=2), encoding='utf-8')
    print('Frozen diagnostic inputs: ' + str(snapshot), flush=True)
    command = [sys.executable, '-u', str(ROOT / 'project/performance_100h/build_host.py'), '--source', str(snapshot)]
    status['build_command'] = command
    status['status'] = 'building'
    receipt.write_text(json.dumps(status, indent=2), encoding='utf-8')
    result = subprocess.run(command)
    status['build_exit_code'] = result.returncode
    status['status'] = 'built' if result.returncode == 0 else 'build_failed'
    receipt.write_text(json.dumps(status, indent=2), encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Isolated diagnostic build failed')


if __name__ == '__main__':
    main()
