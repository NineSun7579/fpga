"""Pinned candidate detview lifecycle. --check/--self-test are local only.

Never stops/restores the original viewer. See deployment_review.md for recipe.
Private baseline environment is sent over SSH stdin, never printed or retained
in candidate receipts. All board actions share current_viewer_session's lock.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'project/tools'))
import current_viewer_session as viewer

DIRECTORY = ROOT / 'log/100h_motion'
ALLOWED_ENV = {'DET_BENCH', 'DETVIEW_TEXTURE_RING', 'DETVIEW_CAPTURE_MAX_FPS'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pinned_hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Expected lowercase SHA256')
    return value


def remote_path(value):
    if (not isinstance(value, str) or not value.startswith('/') or
            any(c in value for c in '\0\r\n') or
            any(p in ('.', '..', '') for p in value.split('/')[1:])):
        raise ValueError('Expected canonical absolute remote path')
    return value


def validate_spec(spec):
    exe = remote_path(spec['exe'])
    if not re.fullmatch(r'/userdata/linaro/100h_performance/(?:[0-9a-f]{64}|build_[0-9a-f]{16})/build/detview', exe):
        raise ValueError('Candidate must be in a SHA256-isolated build/detview path')
    pinned_hash(spec['sha256'])
    overrides = spec.get('overrides', {})
    if not isinstance(overrides, dict) or set(overrides) - ALLOWED_ENV:
        raise ValueError('Only explicit benchmark/ring/capture overrides are allowed')
    for key, value in overrides.items():
        if not isinstance(value, str) or not value or any(c in value for c in '\0\r\n'):
            raise ValueError('Invalid override')
        if key == 'DET_BENCH' and value not in ('0', '1'):
            raise ValueError('DET_BENCH must be 0 or 1')
        if key == 'DETVIEW_TEXTURE_RING' and not re.fullmatch(r'[1-9][0-9]*', value):
            raise ValueError('Texture ring must be a positive integer')
        if key == 'DETVIEW_CAPTURE_MAX_FPS':
            try:
                number = float(value)
            except ValueError:
                raise ValueError('Capture FPS must be finite and nonnegative') from None
            if not math.isfinite(number) or number < 0:
                raise ValueError('Capture FPS must be finite and nonnegative')
    assets = spec.get('assets')
    if not isinstance(assets, dict) or not assets:
        raise ValueError('Pin model asset files with --asset PATH=SHA256')
    for path, value in assets.items():
        remote_path(path)
        pinned_hash(value)
    return spec


def candidate_config(original, snapshot, spec):
    config = copy.deepcopy(original)
    config['exe'] = spec['exe']
    config['argv'][0] = spec['exe']
    # Keep relative model resolution and every other original argument/setting.
    config['env'] = {**snapshot['environment'], **original['env'], **spec['overrides']}
    return viewer.validate_config(config)


def target_from_receipt(receipt, binding):
    if (receipt.get('schema') != 1 or receipt.get('action') != 'start' or
            receipt.get('status') != 'success' or receipt.get('binding') != binding):
        raise ValueError('Successful matching candidate start receipt required')
    events = receipt.get('events', [])
    event = events[-1] if events else {}
    if (event.get('state') != 'started' or type(event.get('pid')) is not int or
            event['pid'] <= 0 or not re.fullmatch(r'[1-9][0-9]*', str(event.get('starttime', ''))) or
            event.get('exe_sha256') != receipt['spec']['sha256'] or
            event.get('log') != receipt.get('log')):
        raise ValueError('Receipt lacks exact candidate process identity')
    return {'pid': event['pid'], 'starttime': event['starttime']}


REMOTE_EXTENSION = r'''
original_action = action
original_process = process
def process(pid):
    try:
        return original_process(pid)
    except (FileNotFoundError, ProcessLookupError):
        # A graceful exit can remove proc files between identity reads.
        if not (Path('/proc') / str(pid)).exists():
            return None
        raise

def exact(request):
    config, baseline, target = request['config'], request['baseline'], request['target']
    current = identity(config, baseline, target['pid'], target['starttime'])
    require(current['pid'] == target['pid'], 'PID mismatch')
    require(current['groups'] == baseline['groups'], 'Groups changed')
    require(current['environment'] == config['env'], 'Full environment changed')
    return current

def measurement_quiescent():
    busy = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / 'comm').read_text().strip()
            args = (entry / 'cmdline').read_bytes().split(b'\0')
            if name in {'make', 'cc1plus', 'cc1', 'clang', 'clang++', 'ld', 'ld.bfd', 'qmake'} or any(
                    value in {b'--parity-selftest', b'--rotate-selftest'} for value in args):
                busy.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            pass
    require(not busy, 'Performance observation interfered with by compiler/extra inference PIDs: ' + str(busy))

def action(request, emit):
    mode = request['action']
    config, baseline = request['config'], request['baseline']
    require(boot() == baseline['boot_id'], 'Board rebooted')
    verify_files(config, baseline)
    if mode == 'stop':
        exact(request)
        original_action(request, emit)
        return
    if mode == 'observe':
        exact(request)
        measurement_quiescent()
        require(owners() == [request['target']['pid']], 'Not sole DMA owner')
        # An open inode pins the log; reject rotation/truncation rather than
        # silently interpreting old data as a new measurement.
        with open(request['log'], 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode), 'Log must be a regular file')
            offset = stream.seek(0, os.SEEK_END)
            partial = False
            if offset:
                stream.seek(offset - 1)
                partial = stream.read(1) != b'\n'
                stream.seek(offset)
            start = time.monotonic()
            emit('observation_started', offset=offset, log=request['log'], partial_first_line=partial,
                 monotonic=start)
            collected = 0
            while True:
                exact(request)
                measurement_quiescent()
                require(owners() == [request['target']['pid']], 'DMA ownership changed')
                now_info = os.stat(request['log'])
                require((now_info.st_dev, now_info.st_ino) == (info.st_dev, info.st_ino), 'Log rotated')
                require(now_info.st_size >= stream.tell(), 'Log truncated')
                block = stream.read(65536)
                if block:
                    collected += len(block)
                    require(collected <= request['max_bytes'], 'Observation log byte limit exceeded')
                    emit('log_chunk', text=block.decode('utf-8', errors='replace'))
                elapsed = time.monotonic() - start
                if elapsed >= request['seconds']:
                    # Drain only bytes present at the verified endpoint.
                    end = os.fstat(stream.fileno()).st_size
                    while stream.tell() < end:
                        block = stream.read(min(65536, end - stream.tell()))
                        require(block, 'Log truncated at endpoint')
                        collected += len(block)
                        require(collected <= request['max_bytes'], 'Observation log byte limit exceeded')
                        emit('log_chunk', text=block.decode('utf-8', errors='replace'))
                    exact(request)
                    measurement_quiescent()
                    require(owners() == [request['target']['pid']], 'Endpoint DMA ownership changed')
                    verify_files(config, baseline)
                    endpoint = time.monotonic()
                    emit('observed', seconds=endpoint - start, monotonic=endpoint, bytes=collected,
                         offset=offset, end_offset=end, pid=request['target']['pid'],
                         starttime=request['target']['starttime'])
                    return
                time.sleep(min(1, request['seconds'] - elapsed))
    require(mode == 'start', 'Unknown candidate action')
    require(os.path.realpath(config['exe']) == config['exe'], 'Candidate path contains symlinks')
    require(not owners(), 'DMA device already owned; candidate launch refused')
    require(not same_exe_pids(config['exe']), 'Candidate executable already running')
    deadline = time.monotonic() + request['timeout']
    def credentials():
        os.setgroups(baseline['groups'])
        os.setgid(baseline['gid'])
        os.setuid(baseline['uid'])
    executable_fd = os.open(config['exe'], os.O_RDONLY | os.O_NOFOLLOW)
    try:
        executable = '/proc/self/fd/' + str(executable_fd)
        require(stat.S_ISREG(os.fstat(executable_fd).st_mode), 'Candidate must be a regular file')
        require(sha(executable) == baseline['exe_sha256'], 'Opened candidate hash mismatch')
        require(not owners(), 'DMA ownership changed before launch')
        verify_files(config, baseline)
        fd = os.open(request['log'], os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb', buffering=0) as stream:
            os.fchown(stream.fileno(), baseline['uid'], baseline['gid'])
            child = subprocess.Popen(config['argv'], executable=executable, cwd=config['cwd'],
                env=config['env'], stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True, close_fds=True,
                pass_fds=(executable_fd,), preexec_fn=credentials)
    finally:
        os.close(executable_fd)
    emit('launched', pid=child.pid, log=request['log'])
    target = None
    stable_since = None
    while time.monotonic() < deadline:
        require(child.poll() is None, 'Candidate exited; inspect retained log')
        current = process(child.pid)
        if current:
            if target is None:
                target = {'pid': child.pid, 'starttime': current['starttime']}
                request['target'] = target
                emit('candidate_identity', **target, exe_sha256=current['exe_sha256'])
            exact(request)
            own = owners()
            require(not any(pid != child.pid for pid in own), 'Unexpected DMA owner; left untouched')
            win = windows(child.pid, config['env'])
            ready = own == [child.pid] and len(win) == 1 and win[0]['delete_supported']
            stable_since = (stable_since or time.monotonic()) if ready else None
            if stable_since is not None and time.monotonic() - stable_since >= request['ready_seconds']:
                verify_files(config, baseline)
                exact(request)
                emit('started', **target, exe_sha256=baseline['exe_sha256'],
                     log=request['log'], window=win[0]['id'], ready_seconds=request['ready_seconds'])
                return
        time.sleep(.2)
    raise RuntimeError('Candidate readiness timed out; process left untouched; inspect receipt/log')

if __name__ == '__main__':
    def emit(state, **details):
        print(json.dumps(dict(state=state, **details)), flush=True)
    try:
        # Keep the captured private environment out of ps command arguments.
        # sudo may consume the password line, or leave it on stdin under
        # NOPASSWD/cached credentials. The request is always the last line.
        request = json.loads(sys.stdin.read().splitlines()[-1])
        def expired(signum, frame):
            raise TimeoutError('Candidate action deadline exceeded; process left untouched')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request['timeout'])
        action(request, emit)
    except BaseException as exc:
        emit('failed', error=str(exc))
        sys.exit(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
'''
REMOTE_SOURCE = viewer.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + REMOTE_EXTENSION


def remote_run(client, request, event):
    command = "sudo -S -p '' python3 -c " + shlex.quote(REMOTE_SOURCE)
    stdin, stdout, stderr = client.exec_command(command, timeout=15)
    channel = stdout.channel
    deadline = time.monotonic() + request['timeout'] + 20
    pending = b''
    try:
        stdin.write('123456\n')
        stdin.write(json.dumps(request))
        stdin.flush()
        channel.shutdown_write()
        while time.monotonic() < deadline:
            if channel.recv_ready():
                pending += channel.recv(65536)
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if line:
                        event(json.loads(line.decode()))
            # Do not echo diagnostics that could contain private request data.
            if channel.recv_stderr_ready():
                channel.recv_stderr(65536)
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                code = channel.recv_exit_status()
                if pending:
                    event(json.loads(pending.decode()))
                if code:
                    raise RuntimeError('Remote candidate action failed; inspect receipt')
                return
            time.sleep(.01)
        raise TimeoutError('SSH deadline exceeded; inspect receipt before retry')
    finally:
        channel.close()


def summarize(text):
    rows = {key: [] for key in ('display-perf', 'display-events', 'display-upload', 'infer-perf', 'tdm')}
    for line in text.splitlines():
        match = re.match(r'\[(display-perf|display-events|display-upload|infer-perf|tdm)\]', line)
        if match:
            rows[match[1]].append({'line': line, 'values': dict(re.findall(r'([\w.]+)=([^\s,]+)', line))})
    # Retain raw metrics, rather than guess counters/units as formats evolve.
    return {'metrics': rows,
            'inference_measurement': ('infer-perf windows retained; use explicit counts/elapsed fields'
                if rows['infer-perf'] else 'Only cumulative tdm diagnostics available; exact inference FPS unavailable'
                if rows['tdm'] else 'No inference performance evidence'),
            'limit': 'Fresh log interval may begin/end inside metric windows. Cumulative tdm is not exact FPS; upload bytes are payload, not physical DDR bandwidth.'}


def pairs(values):
    result = {}
    for value in values:
        if '=' not in value:
            raise ValueError('Expected KEY=VALUE')
        key, item = value.split('=', 1)
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = item
    return result


def run(args):
    from board_host import board_host, ssh_connect
    host = board_host()
    original = viewer.validate_config(viewer.read_json(args.config))
    config_hash = viewer.config_digest(args.config)
    baseline_hash = viewer.config_digest(args.baseline)
    baseline = viewer.validate_baseline(viewer.read_json(args.baseline), config_hash, host, original)
    prior = viewer.read_json(args.start_receipt) if args.start_receipt else None
    spec = validate_spec(prior['spec'] if prior else {'exe': args.exe, 'sha256': args.sha256,
            'overrides': pairs(args.env), 'assets': pairs(args.asset)})
    for asset, expected in spec['assets'].items():
        if asset in baseline['files'] and baseline['files'][asset] != expected:
            raise ValueError('Model asset pin conflicts with captured baseline settings')
    config = candidate_config(original, baseline, spec)
    binding = {'host': host, 'config_sha256': config_hash, 'baseline_sha256': baseline_hash,
               'candidate_sha256': spec['sha256'], 'spec_sha256': digest(spec),
               'argv_sha256': digest(config['argv']), 'settings_sha256': digest(baseline['files'])}
    target = target_from_receipt(prior, binding) if prior else None
    if args.check:
        print(json.dumps({'valid': True, 'binding': binding, 'ssh': False}, indent=2))
        return
    mode = 'start' if args.start else 'stop' if args.stop else 'observe'
    token = uuid.uuid4().hex
    log = prior['log'] if prior else original['log'] + '.candidate-' + token
    remote_path(log)
    if prior and (not re.fullmatch(r'[0-9a-f]{32}', str(prior.get('operation', ''))) or
                  log != original['log'] + '.candidate-' + prior['operation']):
        raise ValueError('Start receipt log is not its unique candidate log')
    snapshot = dict(baseline, exe_sha256=spec['sha256'],
                    files=dict(baseline['files'], **spec['assets']))
    request = {'action': mode, 'config': config, 'baseline': snapshot, 'target': target,
               'timeout': args.seconds + 60 if args.observe else args.timeout,
               'ready_seconds': args.ready_seconds, 'seconds': args.seconds,
               'max_bytes': args.max_bytes, 'log': log}
    receipt = {'schema': 1, 'operation': token, 'action': mode, 'status': 'running',
               'binding': binding, 'spec': spec, 'log': log, 'events': [],
               'start_receipt': str(args.start_receipt.resolve()) if prior else None}
    path = DIRECTORY / ('candidate_' + mode + '_' + token + '.json')
    lock = DIRECTORY / 'board_session.lock'
    held = False
    client = None
    try:
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        with lock.open('x', encoding='utf-8') as stream:
            json.dump({'pid': os.getpid(), 'operation': token, 'action': mode}, stream)
        held = True
        viewer.atomic_json(path, receipt)
        def event(value):
            receipt['events'].append(value)
            viewer.atomic_json(path, receipt)
        client = ssh_connect()
        remote_run(client, request, event)
        expected = {'start': 'started', 'stop': 'stopped', 'observe': 'observed'}[mode]
        if not receipt['events'] or receipt['events'][-1]['state'] != expected:
            raise RuntimeError('No verified remote outcome')
        if args.observe:
            # Drop records straddling either boundary, while retaining raw bytes.
            text = ''.join(e['text'] for e in receipt['events'] if e['state'] == 'log_chunk')
            partial = next(e['partial_first_line'] for e in receipt['events']
                           if e['state'] == 'observation_started')
            complete = (text.split('\n', 1)[1] if '\n' in text else '') if partial else text
            receipt['summary'] = summarize(complete.rsplit('\n', 1)[0])
        receipt['status'] = 'success'
    except BaseException as exc:
        receipt.update(status='failed', error=str(exc))
        raise
    finally:
        if held:
            viewer.atomic_json(path, receipt)
            print('Candidate receipt: ' + str(path))
        if client:
            client.close()
        if held and viewer.read_json(lock).get('operation') == token:
            lock.unlink()


def self_test():
    import unittest
    from unittest.mock import Mock, patch
    spec = {'exe': '/userdata/linaro/100h_performance/' + 'a' * 64 + '/build/detview',
            'sha256': 'b' * 64, 'overrides': {}, 'assets': {'/models/weights': 'c' * 64}}
    namespace = {'__name__': 'candidate_test'}
    exec(compile(REMOTE_SOURCE, '<candidate remote>', 'exec'), namespace)
    class SafetyTests(unittest.TestCase):
        def test_invalid_pins_paths_and_overrides(self):
            for key, value in [('exe', '/tmp/detview'), ('exe', spec['exe'].replace('/build/', '/../build/')),
                               ('sha256', 'b' * 63), ('sha256', 'B' * 64), ('assets', {}),
                               ('overrides', {'LD_PRELOAD': '/tmp/evil'}),
                               ('overrides', {'DETVIEW_CAPTURE_MAX_FPS': 'nan'})]:
                bad = dict(spec, **{key: value})
                with self.assertRaises(ValueError):
                    validate_spec(bad)
        def test_wrong_pid_never_closes(self):
            close = Mock()
            request = {'action': 'stop', 'config': {}, 'baseline': {'boot_id': 'boot'},
                       'target': {'pid': 7, 'starttime': '8'}}
            with patch.dict(namespace, {'boot': lambda: 'boot', 'verify_files': Mock(),
                                       'identity': Mock(return_value={'pid': 9}), 'close_window': close}):
                with self.assertRaises(RuntimeError):
                    namespace['action'](request, Mock())
            close.assert_not_called()
        def test_dma_owner_never_launches(self):
            launch = Mock()
            with patch.dict(namespace, {'boot': lambda: 'boot', 'verify_files': Mock(), 'owners': lambda: [42262]}):
                with patch.object(namespace['subprocess'], 'Popen', launch):
                    with self.assertRaises(RuntimeError):
                        namespace['action']({'action': 'start', 'config': {'exe': spec['exe']},
                                             'baseline': {'boot_id': 'boot'}}, Mock())
            launch.assert_not_called()
        def test_receipt_pid_hash_binding(self):
            receipt = {'schema': 1, 'action': 'start', 'status': 'success', 'binding': {},
                       'spec': spec, 'log': '/log', 'events': [{'state': 'started', 'pid': 7,
                       'starttime': '8', 'exe_sha256': spec['sha256'], 'log': '/log'}]}
            self.assertEqual(target_from_receipt(receipt, {})['pid'], 7)
            with self.assertRaises(ValueError):
                target_from_receipt(receipt, {'host': 'different'})
            for key, value in [('pid', True), ('pid', 0), ('exe_sha256', 'd' * 64), ('starttime', 'reused')]:
                bad = copy.deepcopy(receipt); bad['events'][-1][key] = value
                with self.assertRaises(ValueError):
                    target_from_receipt(bad, {})
        def test_identity_hash_and_starttime_rejected_before_close(self):
            config = {'exe': spec['exe'], 'argv': [spec['exe']], 'cwd': '/work', 'env': {}}
            snap = {'pid': 7, 'starttime': '8', 'exe': spec['exe'], 'exe_sha256': spec['sha256'],
                    'argv': config['argv'], 'cwd': '/work', 'boot_id': 'boot',
                    'uid': 1000, 'gid': 1000, 'groups': [1000], 'environment': {}}
            for key, value in [('starttime', '9'), ('exe_sha256', 'd' * 64)]:
                close = Mock()
                with patch.dict(namespace, {'boot': lambda: 'boot', 'verify_files': Mock(),
                           'process': Mock(return_value=dict(snap, **{key: value})), 'close_window': close}):
                    with self.assertRaises(RuntimeError):
                        namespace['action']({'action': 'stop', 'config': config, 'baseline': snap,
                                             'target': {'pid': 7, 'starttime': '8'}}, Mock())
                close.assert_not_called()
        def test_observe_truncation_fails_without_mutation(self):
            stream = Mock()
            stream.seek.return_value = 100
            stream.tell.return_value = 100
            stream.read.return_value = b'\n'
            context = Mock()
            context.__enter__ = Mock(return_value=stream)
            context.__exit__ = Mock(return_value=False)
            info = Mock(st_mode=0o100600, st_dev=1, st_ino=2, st_size=100)
            shortened = Mock(st_dev=1, st_ino=2, st_size=99)
            close = Mock()
            with patch.dict(namespace, {'boot': lambda: 'boot', 'verify_files': Mock(), 'exact': Mock(),
                      'measurement_quiescent': Mock(), 'owners': lambda: [7],
                      'open': Mock(return_value=context), 'close_window': close}):
                with patch.object(namespace['os'], 'fstat', Mock(return_value=info)), \
                     patch.object(namespace['os'], 'stat', Mock(return_value=shortened)):
                    with self.assertRaisesRegex(RuntimeError, 'truncated'):
                        namespace['action']({'action': 'observe', 'config': {}, 'baseline': {'boot_id': 'boot'},
                                             'target': {'pid': 7}, 'log': '/log'}, Mock())
            close.assert_not_called()
        def test_measurement_rejects_compiler_and_harness(self):
            class Entry:
                name = '10'
                def __init__(self, comm, args):
                    self.comm, self.args = comm, args
                def __truediv__(self, name):
                    return self
                def read_text(self):
                    return self.comm
                def read_bytes(self):
                    return self.args
            for comm, args in [('cc1plus', b'compiler\0'), ('detview', b'detview\0--parity-selftest\0')]:
                fake = Mock()
                fake.iterdir.return_value = [Entry(comm, args)]
                with patch.dict(namespace, {'Path': Mock(return_value=fake)}):
                    with self.assertRaisesRegex(RuntimeError, 'interfered'):
                        namespace['measurement_quiescent']()
            fake = Mock()
            fake.iterdir.return_value = [Entry('python3', b'python3\0-c\0script mentions --parity-selftest\0')]
            with patch.dict(namespace, {'Path': Mock(return_value=fake)}):
                namespace['measurement_quiescent']()
        def test_metrics_never_invent_fps(self):
            result = summarize('[tdm] infer=123\n[display-events] paints=9\n[infer-perf] completed=4 seconds=2')
            self.assertEqual(result['metrics']['infer-perf'][0]['values']['completed'], '4')
            self.assertIn('exact inference FPS unavailable', summarize('[tdm] infer=123')['inference_measurement'])
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for flag in ('check', 'start', 'stop', 'observe', 'self-test'):
        actions.add_argument('--' + flag, action='store_true')
    parser.add_argument('--config', type=Path, default=viewer.DEFAULT_CONFIG)
    parser.add_argument('--baseline', type=Path, default=DIRECTORY / 'current_viewer_baseline.json')
    parser.add_argument('--exe')
    parser.add_argument('--sha256')
    parser.add_argument('--asset', action='append', default=[])
    parser.add_argument('--env', action='append', default=[])
    parser.add_argument('--start-receipt', type=Path)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--ready-seconds', type=float, default=3)
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--max-bytes', type=int, default=16 * 1024 * 1024)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not 0 < args.ready_seconds < args.timeout <= 60:
        parser.error('Require 0 < ready-seconds < timeout <= 60')
    if not 120 <= args.seconds <= 1800 or not 1 <= args.max_bytes <= 64 * 1024 * 1024:
        parser.error('Observe requires 120..1800 seconds and 1..64MiB max bytes')
    if args.stop or args.observe:
        if not args.start_receipt or args.exe or args.sha256 or args.asset or args.env:
            parser.error('Stop/observe require only --start-receipt, not new candidate pins/overrides')
    elif not args.exe or not args.sha256 or args.start_receipt:
        parser.error('Start/check require --exe and --sha256, without --start-receipt')
    try:
        run(args)
    except (ValueError, RuntimeError, OSError, TimeoutError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
