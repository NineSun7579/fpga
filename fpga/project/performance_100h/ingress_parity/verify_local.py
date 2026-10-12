"""All-file byte/hash audit only: never import board or remote builder tools."""
import argparse
import json
from pathlib import Path
from prepare import sha, inventory, snapshot, PIN

HERE = Path(__file__).resolve().parent
PERF = HERE.parent
TOOLS = ['prepare.py', 'verify_local.py', 'run_later.py', 'compare.py', 'README.md', 'CONTROLLER_ACCEPTANCE.md']


def audit(seal=False):
    path = HERE / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    tools = {name: sha((HERE / name).read_bytes()) for name in TOOLS}
    if seal:
        if 'prepared_tool_sha256' in manifest:
            raise ValueError('Already sealed')
        manifest['prepared_tool_sha256'] = tools
        path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if tools != manifest['prepared_tool_sha256']:
        raise ValueError('Prepared tool/document bytes changed')
    for name, digest in manifest['reference_file_sha256'].items():
        if sha((PERF / name).read_bytes()) != digest:
            raise ValueError('Reference changed: ' + name)
    for kind, harness in manifest['harnesses'].items():
        files = inventory(HERE / harness['source'])
        if files != harness['source_sha256'] or snapshot(files) != harness['snapshot_sha256']:
            raise ValueError('Complete source inventory mismatch: ' + kind)
    candidate = manifest['harnesses']['candidate']
    main = (HERE / 'candidate/src/main.cpp').read_bytes()
    start = b'    // Private parity harness: dispatch before camera/controller construction.'
    anchor = b'    const int rotateTest = args.indexOf("--rotate-selftest");'
    if main.count(start) != 1 or main.count(anchor) != 1:
        raise ValueError('Insertion anchors differ')
    block = main[main.index(start):main.index(anchor)]
    if sha(block) != manifest['parity_branch_sha256']:
        raise ValueError('Branch differs')
    reconstructed = dict(candidate['source_sha256'], **{'main.cpp': sha(main.replace(block, b'', 1))})
    if (reconstructed != candidate['original_source_sha256'] or reconstructed['main.cpp'] != PIN
            or snapshot(reconstructed) != candidate['original_snapshot_sha256']
            or inventory(PERF / 'direct_ingress/src') != reconstructed):
        raise ValueError('Change beyond early branch, or original source changed')
    changed = [name for name in reconstructed if reconstructed[name] != candidate['source_sha256'][name]]
    if changed != ['main.cpp']:
        raise ValueError('Expected exactly one changed file')
    for scene in manifest['scenes'].values():
        if sha((HERE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Scene mismatch')
    reuse = manifest['baseline_reuse']
    receipt_bytes = (PERF / reuse['receipt_path']).read_bytes()
    receipt = json.loads(receipt_bytes)
    if sha(receipt_bytes) != reuse['receipt_sha256'] or receipt['status'] != 'built':
        raise ValueError('Baseline receipt changed')
    for name in ['binary', 'binary_sha256', 'source_sha256', 'snapshot_sha256']:
        if receipt[name] != reuse[name]:
            raise ValueError('Baseline reuse pin differs: ' + name)
    for remote, local in manifest['sdk_local_references'].items():
        if sha((PERF.parent / local).read_bytes()) != manifest['sdk_pins'][remote]:
            raise ValueError('Local SDK reference changed')
    for name in TOOLS:
        if name.endswith('.py'):
            compile((HERE / name).read_bytes(), str(HERE / name), 'exec')
    report = dict(status='local_static_verified', board_actions=False, runner_executed=False,
        manifest_sha256=sha(path.read_bytes()), exact_frozen_branch_insertion=True,
        source_file_count=len(reconstructed), unchanged_non_main_files=len(reconstructed)-1,
        controller_and_worker_bytes_preserved_after_branch_removal=True,
        full_inventory_scene_tool_reference_sdk_and_baseline_receipt_pins_verified=True,
        original_main_sha256=PIN, candidate_snapshot_sha256=candidate['snapshot_sha256'],
        baseline_snapshot_sha256=reuse['snapshot_sha256'], python_syntax_verified=True,
        actual_rknn_image_parity='prepared, not executed', controller_mode_transition_acceptance='required target later')
    (HERE / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal-tools', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.seal_tools), indent=2))
