"""Parent launches only after all compiles/observations finish. Sequential make -j1 and RKNN."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

HERE = Path(__file__).resolve().parent
PERF = HERE.parent
ROOT = PERF.parents[1]
sys.path.insert(0, str(PERF))
sys.path.insert(0, str(ROOT / 'project/tools'))
from compare import compare
from board_host import ssh_connect
import board_session


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


REMOTE = r'''
import hashlib, json, os, subprocess, sys
request = json.loads(sys.stdin.read().splitlines()[-1])
def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()
def emit(**value):
    print(json.dumps(value), flush=True)
try:
    for path, digest in request['pins'].items():
        if sha(path) != digest:
            raise ValueError('Remote asset/binary SHA256 mismatch: ' + path)
    for job in request['jobs']:
        # Explicit common environment for both harnesses. No camera or display args.
        env = dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                   HOME='/root', LANG='C', QT_QPA_PLATFORM='offscreen')
        argv = [job['binary'], '--parity-selftest', job['image'], '--model', request['model']]
        try:
            result = subprocess.run(argv, env=env, cwd=os.path.dirname(job['binary']),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
            emit(state='result', kind=job['kind'], scene=job['scene'], rc=result.returncode,
                 log=result.stdout.decode('utf-8', errors='replace'))
        except subprocess.TimeoutExpired as exc:
            emit(state='result', kind=job['kind'], scene=job['scene'], rc=124,
                 log=(exc.stdout or b'').decode('utf-8', errors='replace'))
            raise RuntimeError('Harness process timeout')
    for path, digest in request['pins'].items():
        if sha(path) != digest:
            raise ValueError('Remote pin changed during inference')
    emit(state='finished', hashes_verified_before_after=True)
except Exception as exc:
    emit(state='failed', error=str(exc))
    sys.exit(1)
'''


def validate_receipt(receipt, harness):
    if (receipt.get('status') != 'built' or
            receipt.get('source_sha256') != harness['source_sha256'] or
            receipt.get('snapshot_sha256') != harness['snapshot_sha256']):
        raise ValueError('Build receipt does not match complete frozen source pins')
    digest = receipt.get('binary_sha256', '')
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Build receipt lacks a valid binary SHA256 pin')
    if not receipt.get('binary', '').startswith('/userdata/linaro/100h_performance/build_'):
        raise ValueError('Expected private harness binary path')
    return receipt


def build(kind, harness, reuse=None):
    if reuse is not None:
        receipt = validate_receipt(json.loads(reuse.read_text(encoding='utf-8')), harness)
        save(HERE / ('reused_' + kind + '.json'), {
            'receipt_path': str(reuse.resolve()), 'receipt_sha256': sha(reuse.read_bytes()),
            'receipt': receipt})
        return receipt
    receipt_path = HERE / 'builds' / harness['snapshot_sha256'][:16] / 'receipt.json'
    if receipt_path.exists():
        return validate_receipt(json.loads(receipt_path.read_text()), harness)
    # Execute parent builder with ONLY output-directory / concurrency adaptations.
    # This keeps its SDK path, private SHA directory, source transfer and hash receipts.
    parent = PERF / 'build_host.py'
    source = parent.read_text(encoding='utf-8')
    old = "local = Path(__file__).parent / 'builds' / digest[:16]"
    if source.count(old) != 1 or source.count('make -j2') != 1:
        raise ValueError('Parent build script changed; review adaptations')
    adapted = source.replace(old, "local = Path(__file__).parent / 'cache_parity' / 'builds' / digest[:16]")
    adapted = adapted.replace('make -j2', 'make -j1')
    save(HERE / ('builder_' + kind + '.json'), {'parent_sha256': sha(parent.read_bytes()),
        'adapted_sha256': sha(adapted.encode()), 'changes': ['receipts under cache_parity/builds', 'make -j1']})
    namespace = {'__name__': 'cache_parity_private_builder', '__file__': str(parent)}
    exec(compile(adapted, str(parent), 'exec'), namespace)
    argv = sys.argv
    try:
        sys.argv = [str(parent), '--source', str(HERE / harness['source'])]
        namespace['main']()
    finally:
        sys.argv = argv
    return validate_receipt(json.loads(receipt_path.read_text()), harness)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-observation', action='store_true', required=True,
                         help='Parent asserts all active performance observations have ended')
    parser.add_argument('--after-compiles', action='store_true', required=True,
                        help='Parent asserts cache target and other parity compiles/runs have ended')
    parser.add_argument('--baseline-receipt', type=Path,
                        help='Reuse completed baseline harness only when all source/binary pins match')
    args = parser.parse_args()
    if (ROOT / 'log/100h_motion/board_session.lock').exists():
        raise RuntimeError('Active board session/observation lock: defer parity')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for name, digest in manifest['prepared_tool_sha256'].items():
        if sha((HERE / name).read_bytes()) != digest:
            raise ValueError('Prepared tool changed: ' + name)
    # Validate immutable harness and scenes locally before making any connection.
    for harness in manifest['harnesses'].values():
        src = HERE / harness['source']
        files = {p.relative_to(src).as_posix(): sha(p.read_bytes())
                 for p in sorted(src.rglob('*')) if p.is_file()}
        if files != harness['source_sha256']:
            raise ValueError('Harness changed after preparation')
        if sha(json.dumps(files, sort_keys=True).encode()) != harness['snapshot_sha256']:
            raise ValueError('Harness snapshot digest differs from source inventory')
    for scene in manifest['scenes'].values():
        if sha((HERE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Scene changed after preparation')
    if len(manifest['assets']) != 1:
        raise ValueError('Exactly one pinned model required')
    if manifest['process_reloads_per_scene_per_harness'] != 3:
        raise ValueError('Exactly three process reloads per scene required')
    if args.baseline_receipt is not None:
        validate_receipt(json.loads(args.baseline_receipt.read_text(encoding='utf-8')),
                         manifest['harnesses']['baseline'])
    client = ssh_connect()
    try:
        command = 'test -f /userdata/linaro/detview-todo-work/sdk/rknn_api.h'
        _, out, err = client.exec_command(command, timeout=15)
        if out.channel.recv_exit_status():
            raise RuntimeError('SDK header unavailable')
    finally:
        client.close()
    receipts = {}
    for kind, harness in manifest['harnesses'].items():
        print('Sequential parity build: ' + kind, flush=True)
        receipts[kind] = build(kind, harness,
                               args.baseline_receipt if kind == 'baseline' else None)
    token = sha((HERE / 'manifest.json').read_bytes())[:16] + '_' + str(time.time_ns())
    remote = '/userdata/linaro/100h_performance/cache_parity_' + token
    output = HERE / ('run_' + token)
    output.mkdir()
    report = {'status': 'running', 'manifest_sha256': sha((HERE / 'manifest.json').read_bytes()),
              'builds': receipts, 'remote_directory': remote, 'events': [], 'comparisons': {}}
    save(output / 'report.json', report)
    client = ssh_connect()
    try:
        _, out, err = client.exec_command('mkdir ' + shlex.quote(remote), timeout=15)
        if out.channel.recv_exit_status():
            raise RuntimeError('Private parity scene directory creation failed')
        pins = dict(manifest['assets'])
        jobs = []
        with client.open_sftp() as transfer:
            for name, scene in manifest['scenes'].items():
                image = remote + '/' + scene['path']
                transfer.put(str(HERE / scene['path']), image)
                pins[image] = scene['sha256']
                for reload in range(1, manifest['process_reloads_per_scene_per_harness'] + 1):
                    for kind in ('baseline', 'candidate'):
                        binary = receipts[kind]['binary']
                        pins[binary] = receipts[kind]['binary_sha256']
                        jobs.append(dict(kind=kind, scene=name + '_reload' + str(reload),
                                         image=image, binary=binary))
        request = dict(timeout=600, pins=pins, jobs=jobs, model=next(iter(manifest['assets'])))
        save(output / 'request.json', request)
        def event(value):
            report['events'].append({k: v for k, v in value.items() if k != 'log'})
            if value['state'] == 'result':
                (output / (value['scene'] + '_' + value['kind'] + '.log')).write_text(value['log'], encoding='utf-8')
            save(output / 'report.json', report)
        prior = board_session.REMOTE_SOURCE
        try:
            board_session.REMOTE_SOURCE = REMOTE
            # Reuse established sudo stdin credential handling; no secrets in args/logs.
            board_session.remote_run(client, request, event)
        finally:
            board_session.REMOTE_SOURCE = prior
        if not report['events'] or report['events'][-1]['state'] != 'finished':
            raise RuntimeError('Remote hash audit did not finish')
        if any(e.get('rc', 0) != 0 for e in report['events']):
            raise RuntimeError('Harness returned error; inspect retained logs')
        names = [name + '_reload' + str(reload) for name in manifest['scenes']
                 for reload in range(1, manifest['process_reloads_per_scene_per_harness'] + 1)]
        results = [e for e in report['events'] if e['state'] == 'result']
        if len(results) != len(jobs) or {(e['kind'], e['scene']) for e in results} != {
                (j['kind'], j['scene']) for j in jobs}:
            raise RuntimeError('Missing or duplicate harness result')
        for name in names:
            report['comparisons'][name] = compare(
                (output / (name + '_baseline.log')).read_text(encoding='utf-8'),
                (output / (name + '_candidate.log')).read_text(encoding='utf-8'))
        from compare import match
        reload_stable = {}
        for scene in manifest['scenes']:
            for kind in ('baseline', 'candidate'):
                first = report['comparisons'][scene + '_reload1'][kind + '_frames'][0]['detections']
                reload_stable[scene + '_' + kind] = all(match(first, frame['detections'], 0, 0)
                    for reload in range(1, 4)
                    for frame in report['comparisons'][scene + '_reload' + str(reload)][kind + '_frames'])
        report['repeat_exact_across_reloads'] = reload_stable
        matched = (all(c['tolerance_match'] and c['baseline_repeat_exact'] and c['candidate_repeat_exact']
                       for c in report['comparisons'].values()) and all(reload_stable.values()))
        positive = any(c['positive_detection_evidence'] for c in report['comparisons'].values())
        report['status'] = 'match' if matched and positive else 'empty_only_inconclusive' if matched else 'mismatch'
    except BaseException as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        client.close()
        save(output / 'report.json', report)
        print('Parity report: ' + str(output / 'report.json'), flush=True)
    return 0 if report['status'] == 'match' else 2


if __name__ == '__main__':
    raise SystemExit(main())
