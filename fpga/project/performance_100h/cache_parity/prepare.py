"""Prepare immutable cache parity snapshots locally; no remote imports or actions."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
PERF = HERE.parent
REFERENCE = PERF / 'parity'
PIN = '1ff7a8400a7a8dd48834ed56a740579ba93efce48a8b79687bf18085efbc71b9'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(source):
    return {p.relative_to(source).as_posix(): sha(p.read_bytes())
            for p in sorted(source.rglob('*')) if p.is_file()}


def snapshot(files):
    return sha(json.dumps(files, sort_keys=True).encode())


def main():
    if (HERE / 'manifest.json').exists():
        raise ValueError('Already prepared; refusing to overwrite frozen snapshots')
    reference_bytes = (REFERENCE / 'manifest.json').read_bytes()
    reference = json.loads(reference_bytes)
    original = PERF / 'output_cache/src'
    if sha((original / 'main.cpp').read_bytes()) != PIN:
        raise ValueError('Cache main.cpp differs from frozen 1ff7 source')
    frozen = REFERENCE / 'candidate/src/main.cpp'
    if sha(frozen.read_bytes()) != reference['harnesses']['candidate']['source_sha256']['main.cpp']:
        raise ValueError('Frozen candidate harness differs from manifest')
    anchor = b'    const int rotateTest = args.indexOf("--rotate-selftest");'
    start = b'    // Private parity harness: dispatch before camera/controller construction.'
    frozen_bytes = frozen.read_bytes()
    block = frozen_bytes[frozen_bytes.index(start):frozen_bytes.index(anchor)]
    original_files = inventory(original)
    baseline_files = inventory(REFERENCE / 'baseline/src')
    if baseline_files != reference['harnesses']['baseline']['source_sha256']:
        raise ValueError('Frozen baseline harness differs from manifest')
    for scene in reference['scenes'].values():
        if sha((REFERENCE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Prepared reference scene changed')
    for kind, source in [('candidate', original), ('baseline', REFERENCE / 'baseline/src')]:
        dest = HERE / kind / 'src'
        shutil.copytree(source, dest)
        if kind == 'candidate':
            data = (dest / 'main.cpp').read_bytes()
            if data.count(anchor) != 1 or start in data:
                raise ValueError('Unexpected parity insertion anchor')
            (dest / 'main.cpp').write_bytes(data.replace(anchor, block + anchor))
    manifest = {k: reference[k] for k in ['schema', 'sdk_include',
        'completions_per_scene_per_harness', 'coordinate_space', 'assets', 'scenes']}
    manifest.update(status='prepared_only', board_actions=False,
        candidate_original_main_sha256=PIN,
        candidate_original_build=snapshot(original_files),
        reference_manifest_sha256=sha(reference_bytes),
        parity_branch_sha256=sha(block), process_reloads_per_scene_per_harness=3,
        native_output_formats_changed=False, harnesses={})
    manifest['harnesses']['baseline'] = dict(reference['harnesses']['baseline'])
    manifest['harnesses']['baseline']['source'] = 'baseline/src'
    candidate_files = inventory(HERE / 'candidate/src')
    manifest['harnesses']['candidate'] = dict(source='candidate/src',
        original_source_sha256=original_files, source_sha256=candidate_files,
        original_snapshot_sha256=snapshot(original_files), snapshot_sha256=snapshot(candidate_files),
        input_path='raw RGB888 640x480')
    for scene in manifest['scenes'].values():
        shutil.copyfile(REFERENCE / scene['path'], HERE / scene['path'])
    shutil.copyfile(REFERENCE / 'compare.py', HERE / 'compare.py')
    manifest['tool_reference_sha256'] = {
        name: sha((REFERENCE / name).read_bytes()) for name in ['run_later.py', 'compare.py']}
    runner = (REFERENCE / 'run_later.py').read_text(encoding='utf-8')
    runner = runner.replace("'parity' / 'builds'", "'cache_parity' / 'builds'")
    runner = runner.replace('receipts under parity/builds', 'receipts under cache_parity/builds')
    runner = runner.replace("'parity_private_builder'", "'cache_parity_private_builder'")
    runner = runner.replace("'/userdata/linaro/100h_performance/parity_'", "'/userdata/linaro/100h_performance/cache_parity_'")
    (HERE / 'run_later.py').write_text(runner, encoding='utf-8')
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'prepared_only', 'candidate_original_snapshot': snapshot(original_files),
        'candidate_harness_snapshot': snapshot(candidate_files),
        'baseline_harness_snapshot': snapshot(baseline_files)}, indent=2))


if __name__ == '__main__':
    main()
