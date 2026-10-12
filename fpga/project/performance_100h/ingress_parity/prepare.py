"""Local-only frozen preparation; no imports of SSH/build/board modules."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
PERF = HERE.parent
REFERENCE = PERF / 'cache_parity'
PIN = 'fb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(source):
    return {p.relative_to(source).as_posix(): sha(p.read_bytes())
            for p in sorted(source.rglob('*')) if p.is_file()}


def snapshot(files):
    return sha(json.dumps(files, sort_keys=True).encode())


def main():
    if (HERE / 'manifest.json').exists():
        raise ValueError('Already frozen; refusing overwrite')
    ref_bytes = (REFERENCE / 'manifest.json').read_bytes()
    ref = json.loads(ref_bytes)
    for name, digest in ref['prepared_tool_sha256'].items():
        if sha((REFERENCE / name).read_bytes()) != digest:
            raise ValueError('Reference tool changed: ' + name)
    source = PERF / 'direct_ingress/src'
    original = inventory(source)
    if original['main.cpp'] != PIN:
        raise ValueError('Direct-ingress main differs from fb670 pin')
    frozen = (REFERENCE / 'candidate/src/main.cpp').read_bytes()
    if inventory(REFERENCE / 'candidate/src') != ref['harnesses']['candidate']['source_sha256']:
        raise ValueError('Reference candidate changed')
    start = b'    // Private parity harness: dispatch before camera/controller construction.'
    anchor = b'    const int rotateTest = args.indexOf("--rotate-selftest");'
    block = frozen[frozen.index(start):frozen.index(anchor)]
    if sha(block) != ref['parity_branch_sha256']:
        raise ValueError('Reference branch changed')
    baseline = ref['harnesses']['baseline']
    if inventory(REFERENCE / baseline['source']) != baseline['source_sha256']:
        raise ValueError('Reference baseline changed')
    receipt_path = PERF / 'parity/builds/619b6eb48a32ca26/receipt.json'
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt['status'] != 'built' or receipt['source_sha256'] != baseline['source_sha256']
            or receipt['snapshot_sha256'] != baseline['snapshot_sha256']
            or receipt['binary_sha256'] != '5887fc2d32734b234e1005d020c781fa2f0f47f4d9ef607790fc1315025c8c03'):
        raise ValueError('619b baseline receipt mismatch')
    for scene in ref['scenes'].values():
        if sha((REFERENCE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Reference scene changed')
    shutil.copytree(source, HERE / 'candidate/src')
    shutil.copytree(REFERENCE / baseline['source'], HERE / 'baseline/src')
    data = (HERE / 'candidate/src/main.cpp').read_bytes()
    if data.count(anchor) != 1 or start in data:
        raise ValueError('Unexpected insertion anchor')
    (HERE / 'candidate/src/main.cpp').write_bytes(data.replace(anchor, block + anchor))
    for scene in ref['scenes'].values():
        shutil.copyfile(REFERENCE / scene['path'], HERE / scene['path'])
    shutil.copyfile(REFERENCE / 'compare.py', HERE / 'compare.py')
    runner = (REFERENCE / 'run_later.py').read_text(encoding='utf-8').replace('cache_parity', 'ingress_parity')
    # Require the already-built baseline; do not compile another baseline.
    runner = runner.replace("help='Reuse completed baseline harness only when all source/binary pins match')",
        "default=PERF / 'parity/builds/619b6eb48a32ca26/receipt.json',\n                        help='Pinned 619b baseline receipt; reused without compilation')")
    marker = '    client = ssh_connect()\n    try:\n        command = '
    if runner.count(marker) != 1:
        raise ValueError('Runner preflight anchor changed')
    runner = runner.replace(marker,
        "    from verify_local import audit\n    audit()\n    client = ssh_connect()\n    try:\n"
        "        with client.open_sftp() as transfer:\n"
        "            for asset, digest in manifest['sdk_pins'].items():\n"
        "                with transfer.open(asset, 'rb') as stream:\n"
        "                    if sha(stream.read()) != digest:\n"
        "                        raise ValueError('Target SDK differs from local expected pin: ' + asset)\n"
        "        command = ")
    runner = runner.replace("pins = dict(manifest['assets'])", "pins = dict(manifest['assets'])\n        pins.update(manifest['sdk_pins'])")
    runner = runner.replace('    return receipt\n',
        "    frozen = json.loads((HERE / 'manifest.json').read_bytes())['baseline_reuse']\n"
        "    if harness['snapshot_sha256'] == frozen['snapshot_sha256']:\n"
        "        if receipt['binary'] != frozen['binary'] or digest != frozen['binary_sha256']:\n"
        "            raise ValueError('Reused baseline binary differs from frozen 619b pin')\n"
        "    return receipt\n", 1)
    (HERE / 'run_later.py').write_text(runner, encoding='utf-8')
    manifest = {k: ref[k] for k in ['schema', 'sdk_include', 'completions_per_scene_per_harness',
        'coordinate_space', 'assets', 'scenes', 'process_reloads_per_scene_per_harness']}
    manifest.update(status='prepared_only', board_actions=False,
        candidate_original_main_sha256=PIN, candidate_original_build=snapshot(original),
        reference_manifest_sha256=sha(ref_bytes), parity_branch_sha256=sha(block),
        native_output_formats_changed=False, coverage='worker preprocess/output cache RKNN image parity; controller bypassed',
        controller_acceptance_status='required_target_later', harnesses={})
    manifest['harnesses']['baseline'] = dict(baseline, source='baseline/src')
    files = inventory(HERE / 'candidate/src')
    manifest['harnesses']['candidate'] = dict(source='candidate/src', original_source_sha256=original,
        source_sha256=files, original_snapshot_sha256=snapshot(original), snapshot_sha256=snapshot(files),
        input_path='raw RGB888 640x480, directly submitted to InferenceThread')
    manifest['baseline_reuse'] = dict(receipt_path='parity/builds/619b6eb48a32ca26/receipt.json',
        receipt_sha256=sha(receipt_bytes), binary=receipt['binary'], binary_sha256=receipt['binary_sha256'],
        source_sha256=receipt['source_sha256'], snapshot_sha256=receipt['snapshot_sha256'])
    sdk = {'/userdata/linaro/detview-todo-work/sdk/rknn_api.h': 'host/detview/include/rknn_api.h',
           '/usr/lib/librknnrt.so': 'host/detview/lib/librknnrt.so'}
    manifest['sdk_local_references'] = sdk
    manifest['sdk_pins'] = {remote: sha((PERF.parent / local).read_bytes()) for remote, local in sdk.items()}
    manifest['sdk_pin_status'] = 'local reference hashes; target equality required before build, not yet observed'
    manifest['candidate_binary_pin_status'] = 'not built; runner requires complete-source receipt and pins produced binary before/after RKNN'
    manifest['reference_file_sha256'] = {name: sha((PERF / name).read_bytes()) for name in
        ['cache_parity/manifest.json', 'cache_parity/prepare.py', 'cache_parity/run_later.py',
         'cache_parity/verify_local.py', 'cache_parity/compare.py', 'build_host.py', 'board_session.py',
         '../tools/board_host.py']}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'prepared_only', 'original': snapshot(original), 'candidate': snapshot(files)}, indent=2))


if __name__ == '__main__':
    main()
