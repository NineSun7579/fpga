"""Verify pinned local inputs before future target validation. No board access."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    ready = json.loads((HERE / 'ready_for_validation.json').read_text(encoding='utf-8'))
    errors = []
    for folder, snapshot in ready['sources'].items():
        directory = HERE / folder
        actual = {path.relative_to(directory).as_posix(): sha(path)
                  for path in sorted(directory.rglob('*')) if path.is_file()}
        if actual != snapshot['files']:
            errors.append('Source inventory differs: ' + folder)
        digest = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
        if digest != snapshot['snapshot_sha256']:
            errors.append('Source snapshot digest differs: ' + folder)
    local = HERE / 'direct_ingress/local_validation'
    receipt = json.loads((local / 'receipt.json').read_text(encoding='utf-8'))
    for name, expected in receipt['files'].items():
        if not (local / name).is_file() or sha(local / name) != expected:
            errors.append('Local test evidence differs: ' + name)
    if any(step['exit_code'] for step in receipt['steps']):
        errors.append('A local validation step failed')
    # Verify actual pinned source body is what the extracted-code test compiled.
    extracted = json.loads((local / 'production_manifest.json').read_text(encoding='utf-8'))
    source_hash = sha(HERE / 'direct_ingress/src/main.cpp')
    if source_hash != extracted.get('source_sha256'):
        errors.append('Extracted-code manifest does not bind current production source')
    result = {'status': 'failed' if errors else 'local_inputs_verified', 'errors': errors,
              'goal_complete': False,
              'scope': 'Local source and retained test evidence. No target build or performance verification.',
              'board_policy': ready['board_policy'],
              'required_next_steps': ready['required_next_steps']}
    return result


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(1 if result['errors'] else 0)
