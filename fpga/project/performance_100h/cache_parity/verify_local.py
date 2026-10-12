"""Audit local source/scene pins and exact insertion; never import board tools."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(source):
    return {p.relative_to(source).as_posix(): sha(p.read_bytes())
            for p in sorted(source.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal-tools', action='store_true',
                        help='Pin prepared tools once, after local runner adaptations')
    args = parser.parse_args()
    path = HERE / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    tools = {name: sha((HERE / name).read_bytes()) for name in
             ['prepare.py', 'run_later.py', 'compare.py', 'verify_local.py']}
    if args.seal_tools:
        if 'prepared_tool_sha256' in manifest:
            raise ValueError('Already sealed; refusing to replace tool pins')
        manifest['prepared_tool_sha256'] = tools
        path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if tools != manifest['prepared_tool_sha256']:
        raise ValueError('Prepared tool pins differ')
    for kind, harness in manifest['harnesses'].items():
        files = inventory(HERE / harness['source'])
        if files != harness['source_sha256']:
            raise ValueError('Source pins differ: ' + kind)
        if sha(json.dumps(files, sort_keys=True).encode()) != harness['snapshot_sha256']:
            raise ValueError('Snapshot pin differs: ' + kind)
    candidate = manifest['harnesses']['candidate']
    main = (HERE / 'candidate/src/main.cpp').read_bytes()
    start = b'    // Private parity harness: dispatch before camera/controller construction.'
    anchor = b'    const int rotateTest = args.indexOf("--rotate-selftest");'
    block = main[main.index(start):main.index(anchor)]
    if sha(block) != manifest['parity_branch_sha256']:
        raise ValueError('Parity branch differs from frozen candidate')
    original_files = dict(candidate['source_sha256'])
    original_files['main.cpp'] = sha(main.replace(block, b'', 1))
    if original_files != candidate['original_source_sha256']:
        raise ValueError('Changes beyond exact parity branch insertion')
    if original_files['main.cpp'] != manifest['candidate_original_main_sha256']:
        raise ValueError('Cache main pin differs')
    if sha(json.dumps(original_files, sort_keys=True).encode()) != candidate['original_snapshot_sha256']:
        raise ValueError('Original cache snapshot pin differs')
    for scene in manifest['scenes'].values():
        if sha((HERE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Scene pin differs')
    for name in ['prepare.py', 'run_later.py', 'compare.py', 'verify_local.py']:
        compile((HERE / name).read_bytes(), str(HERE / name), 'exec')
    report = dict(status='local_static_verified', board_actions=False,
        manifest_sha256=sha(path.read_bytes()),
        exact_frozen_branch_insertion=True, cache_worker_bytes_unchanged=True,
        harness_source_and_scene_pins_verified=True, python_syntax_verified=True,
        baseline_snapshot_sha256=manifest['harnesses']['baseline']['snapshot_sha256'],
        candidate_snapshot_sha256=candidate['snapshot_sha256'])
    (HERE / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
