"""Parent launches ONLY after performance observation finishes. Sequential make -j1 and RKNN."""
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


def build(kind, harness):
    receipt_path = HERE / 'builds' / harness['snapshot_sha256'][:16] / 'receipt.json'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['status'] != 'built' or receipt['source_sha256'] != harness['source_sha256']:
            raise RuntimeError('Existing build is failed or does not match pinned source; inspect it')
        return receipt
    # Execute parent builder with ONLY output-directory / concurrency adaptations.
    # This keeps its SDK path, private SHA directory, source transfer and hash receipts.
    parent = PERF / 'build_host.py'
    source = parent.read_text(encoding='utf-8')
    old = "local = Path(__file__).parent / 'builds' / digest[:16]"
    if source.count(old) != 1 or source.count('make -j2') != 1:
        raise ValueError('Parent build script changed; review adaptations')
    adapted = source.replace(old, "local = Path(__file__).parent / 'parity' / 'builds' / digest[:16]")
    adapted = adapted.replace('make -j2', 'make -j1')
    save(HERE / ('builder_' + kind + '.json'), {'parent_sha256': sha(parent.read_bytes()),
        'adapted_sha256': sha(adapted.encode()), 'changes': ['receipts under parity/builds', 'make -j1']})
    namespace = {'__name__': 'parity_private_builder', '__file__': str(parent)}
    exec(compile(adapted, str(parent), 'exec'), namespace)
    argv = sys.argv
    try:
        sys.argv = [str(parent), '--source', str(HERE / harness['source'])]
        namespace['main']()
    finally:
        sys.argv = argv
    return json.loads(receipt_path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-observation', action='store_true', required=True,
                        help='Parent asserts all active performance observations have ended')
    args = parser.parse_args()
    if (ROOT / 'log/100h_motion/board_session.lock').exists():
        raise RuntimeError('Active board session/observation lock: defer parity')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    # Validate immutable harness and scenes locally before making any connection.
    for harness in manifest['harnesses'].values():
        src = HERE / harness['source']
        files = {p.relative_to(src).as_posix(): sha(p.read_bytes())
                 for p in sorted(src.rglob('*')) if p.is_file()}
        if files != harness['source_sha256']:
            raise ValueError('Harness changed after preparation')
    for scene in manifest['scenes'].values():
        if sha((HERE / scene['path']).read_bytes()) != scene['sha256']:
            raise ValueError('Scene changed after preparation')
    if len(manifest['assets']) != 1:
        raise ValueError('Exactly one pinned model required')
    # Parent authorized brief overlap with its separate build after observation.
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
        receipts[kind] = build(kind, harness)
    token = sha((HERE / 'manifest.json').read_bytes())[:16] + '_' + str(time.time_ns())
    remote = '/userdata/linaro/100h_performance/parity_' + token
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
                for kind in ('baseline', 'candidate'):
                    binary = receipts[kind]['binary']
                    pins[binary] = receipts[kind]['binary_sha256']
                    jobs.append(dict(kind=kind, scene=name, image=image, binary=binary))
        request = dict(timeout=240, pins=pins, jobs=jobs, model=next(iter(manifest['assets'])))
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
        for name in manifest['scenes']:
            report['comparisons'][name] = compare(
                (output / (name + '_baseline.log')).read_text(encoding='utf-8'),
                (output / (name + '_candidate.log')).read_text(encoding='utf-8'))
        matched = all(c['tolerance_match'] for c in report['comparisons'].values())
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
