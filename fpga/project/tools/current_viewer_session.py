"""Safely pause/restore the detview described by viewer_launch_current.json.

Local-only: --check; --self-test. Neither connects to SSH.
Read-only board inspection (writes only a local baseline when requested):
  python project/tools/current_viewer_session.py --preflight --capture-baseline
  python project/tools/current_viewer_session.py --preflight
Explicit board actions:
  python project/tools/current_viewer_session.py --stop
  python project/tools/current_viewer_session.py --restore --stop-receipt PATH

--config defaults to log/100h_motion/viewer_launch_current.json; --baseline
defaults to its sibling current_viewer_baseline.json. Capture is exclusive:
an existing baseline is never overwritten. Stop refuses without that baseline.
Every action retains a unique local receipt, including failures. Restore needs
a successful stop receipt and creates a new remote log beside the saved log;
the old log is never truncated. The restore receipt records the new PID and
starttime; pass it to --target-receipt when subsequently stopping that launch.

No signals, force kills, PCI/module/register operations, or keyboard injection.
Graceful close and readiness waits share a maximum 60 second deadline per
action. A timeout leaves the process alone and retains its receipt for review.
The saved env is a set of overrides: restore reuses the captured process's full
environment, credentials, exact argv and cwd, then reapplies those overrides.
Baselines therefore contain process environment values: keep them private.
The tool uses board_host.ssh_connect and sudo just like other workspace tools.
Requires board python3, X11, xwininfo and xprop. Only --preflight/--stop/--restore
connect. The remote source embedded below is sent in memory, never installed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / 'log/100h_motion/viewer_launch_current.json'
DEVICE = '/dev/pango_pci_driver'


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError('Config must be an object')
    pid = config.get('pid')
    if isinstance(pid, bool) or not re.fullmatch(r'[1-9][0-9]*', str(pid)):
        raise ValueError('pid must be a positive decimal PID')
    for key in ('exe', 'cwd', 'log'):
        value = config.get(key)
        if not isinstance(value, str) or not value.startswith('/') or any(c in value for c in '\0\r\n'):
            raise ValueError(key + ' must be an absolute remote path')
    if Path(config['exe']).name != 'detview':
        raise ValueError('Only the saved detview executable is supported')
    argv = config.get('argv')
    if not isinstance(argv, list) or not argv or argv[0] != config['exe']:
        raise ValueError('argv[0] must equal exe')
    if any(not isinstance(v, str) or '\0' in v for v in argv):
        raise ValueError('argv must contain NUL-free strings')
    if argv.count('--stereo-config') != 1:
        raise ValueError('Expected exactly one --stereo-config')
    index = argv.index('--stereo-config') + 1
    if index >= len(argv) or not argv[index].startswith('/') or '\n' in argv[index]:
        raise ValueError('Stereo config must be an absolute path')
    env = config.get('env')
    if not isinstance(env, dict) or not all(k in env for k in ('DISPLAY', 'XAUTHORITY', 'QT_QPA_PLATFORM')):
        raise ValueError('Saved X11/Qt environment is required')
    for key, value in env.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) or not isinstance(value, str) or '\0' in value:
            raise ValueError('Invalid environment entry')
    if env['QT_QPA_PLATFORM'] != 'xcb' or not env['DISPLAY'] or not env['XAUTHORITY'].startswith('/'):
        raise ValueError('Expected saved xcb/X11 display environment')
    return config


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def config_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_baseline(baseline, digest, host, config):
    if baseline.get('schema') != 1 or baseline.get('config_sha256') != digest or baseline.get('host') != host:
        raise ValueError('Baseline schema, saved config hash or board host mismatch')
    snap = baseline.get('snapshot', {})
    if not re.fullmatch(r'[0-9a-f]{64}', snap.get('exe_sha256', '')):
        raise ValueError('Stop/restore requires a captured executable SHA256')
    if snap.get('pid') != int(config['pid']) or snap.get('argv') != config['argv'] or snap.get('cwd') != config['cwd']:
        raise ValueError('Baseline does not identify this saved viewer')
    if snap.get('exe') != config['exe'] or not snap.get('starttime') or not snap.get('boot_id'):
        raise ValueError('Incomplete process identity baseline')
    stereo = config['argv'][config['argv'].index('--stereo-config') + 1]
    if not re.fullmatch(r'[0-9a-f]{64}', snap.get('files', {}).get(stereo, '')):
        raise ValueError('Captured stereo configuration hash required')
    if not isinstance(snap.get('environment'), dict) or any(snap['environment'].get(k) != v for k, v in config['env'].items()):
        raise ValueError('Baseline environment does not match saved overrides')
    for key, value in snap['environment'].items():
        if not isinstance(key, str) or not isinstance(value, str) or '=' in key or '\0' in key + value:
            raise ValueError('Invalid captured environment')
    for key in ('uid', 'gid'):
        if type(snap.get(key)) is not int or snap[key] < 0:
            raise ValueError('Captured process credentials required')
    if not isinstance(snap.get('groups'), list) or any(type(v) is not int or v < 0 for v in snap['groups']):
        raise ValueError('Captured process groups required')
    for path, value in snap['files'].items():
        if not isinstance(path, str) or not path.startswith('/') or '\0' in path or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Invalid captured config/source hash')
    return snap


# This source is also exercised locally with mocked /proc/X11/process operations.
REMOTE_SOURCE = r'''
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

DEVICE = '/dev/pango_pci_driver'

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def sha(path):
    with open(path, 'rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()

def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def process(pid):
    p = Path('/proc') / str(pid)
    try:
        raw = (p / 'stat').read_text()
    except FileNotFoundError:
        return None
    fields = raw[raw.rfind(')') + 2:].split()
    if fields[0] == 'Z':
        return None
    status = (p / 'status').read_text()
    env = {}
    for item in (p / 'environ').read_bytes().split(b'\0'):
        if item:
            key, value = item.split(b'=', 1)
            env[os.fsdecode(key)] = os.fsdecode(value)
    return {'pid': int(pid), 'starttime': fields[19],
            'exe': os.readlink(str(p / 'exe')), 'exe_sha256': sha(p / 'exe'),
            'cwd': os.readlink(str(p / 'cwd')),
            'argv': [os.fsdecode(v) for v in (p / 'cmdline').read_bytes().split(b'\0') if v],
            'environment': env,
            'uid': int(re.search(r'^Uid:\s+(\d+)', status, re.M)[1]),
            'gid': int(re.search(r'^Gid:\s+(\d+)', status, re.M)[1]),
            'groups': [int(v) for v in re.search(r'^Groups:\s*(.*)$', status, re.M)[1].split()],
            'boot_id': boot()}

def owners():
    # Inspect descriptors without opening the DMA device. Root access is required;
    # permission errors fail closed instead of being interpreted as no owners.
    device = os.stat(DEVICE)
    require(stat.S_ISCHR(device.st_mode), 'DMA device absent/not a character device')
    found = set()
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            fds = list((p / 'fd').iterdir())
        except FileNotFoundError:
            continue
        for fd in fds:
            try:
                info = fd.stat()
            except FileNotFoundError:
                continue
            if stat.S_ISCHR(info.st_mode) and info.st_rdev == device.st_rdev:
                found.add(int(p.name))
        # A process can retain a device mmap after closing its descriptor.
        # Match the backing node's filesystem device/inode, as fuser does.
        try:
            mappings = (p / 'maps').read_text().splitlines()
        except FileNotFoundError:
            continue
        for line in mappings:
            fields = line.split(None, 5)
            major, minor = (int(v, 16) for v in fields[3].split(':'))
            if (major, minor, int(fields[4])) == (os.major(device.st_dev), os.minor(device.st_dev), device.st_ino):
                found.add(int(p.name))
    return sorted(found)

def same_exe_pids(exe):
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            actual = os.readlink(str(p / 'exe'))
        except FileNotFoundError:
            continue
        if actual == exe:
            found.append(int(p.name))
    return sorted(found)

def windows(pid, env):
    effective = dict(os.environ, **env)
    tree = subprocess.check_output(['xwininfo', '-root', '-tree'], env=effective, timeout=3).decode()
    found = []
    for wid in dict.fromkeys(re.findall(r'0x[0-9a-fA-F]+', tree)):
        props = subprocess.run(['xprop', '-id', wid, '_NET_WM_PID', 'WM_PROTOCOLS'],
                               env=effective, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=3)
        m = re.search(r'_NET_WM_PID\([^)]*\)\s*=\s*(\d+)', props.stdout)
        if props.returncode == 0 and m and int(m[1]) == pid:
            found.append({'id': wid, 'delete_supported': 'WM_DELETE_WINDOW' in props.stdout})
    return found

def close_window(wid, env):
    for k in ('DISPLAY', 'XAUTHORITY'):
        os.environ[k] = env[k]
    x = C.CDLL('libX11.so.6')
    class Data(C.Union):
        _fields_ = [('b', C.c_char * 20), ('s', C.c_short * 10), ('l', C.c_long * 5)]
    class Client(C.Structure):
        _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                    ('display', C.c_void_p), ('window', C.c_ulong),
                    ('message_type', C.c_ulong), ('format', C.c_int), ('data', Data)]
    class Event(C.Union):
        _fields_ = [('client', Client), ('pad', C.c_long * 24)]
    x.XOpenDisplay.argtypes = [C.c_char_p]; x.XOpenDisplay.restype = C.c_void_p
    x.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]; x.XInternAtom.restype = C.c_ulong
    x.XSendEvent.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)]
    x.XSendEvent.restype = C.c_int
    x.XSync.argtypes = [C.c_void_p, C.c_int]
    x.XCloseDisplay.argtypes = [C.c_void_p]
    d = x.XOpenDisplay(None)
    require(d, 'Cannot open saved X display')
    try:
        event = Event()
        event.client.type = 33  # ClientMessage
        event.client.send_event = 1
        event.client.display = d
        event.client.window = int(wid, 16)
        event.client.message_type = x.XInternAtom(d, b'WM_PROTOCOLS', 0)
        event.client.format = 32
        event.client.data.l[0] = x.XInternAtom(d, b'WM_DELETE_WINDOW', 0)
        event.client.data.l[1] = 0  # CurrentTime
        require(x.XSendEvent(d, event.client.window, 0, 0, C.byref(event)), 'XSendEvent failed')
        x.XSync(d, 0)
    finally:
        x.XCloseDisplay(d)

def files(config):
    stereo = config['argv'][config['argv'].index('--stereo-config') + 1]
    paths = [stereo]
    source = str(Path(config['exe']).parent.parent / 'src/main.cpp')
    if Path(source).is_file():
        paths.append(source)
    return {path: sha(path) for path in paths}

def verify_files(config, baseline):
    require(sha(config['exe']) == baseline['exe_sha256'], 'Executable file SHA256 changed')
    require(all(sha(p) == h for p, h in baseline['files'].items()), 'Config/source file SHA256 changed')

def identity(config, baseline, pid, starttime):
    current = process(pid)
    require(current is not None, 'Saved viewer process is absent')
    for key, expected in [('exe', config['exe']), ('exe_sha256', baseline['exe_sha256']),
                          ('argv', config['argv']), ('cwd', config['cwd']),
                          ('starttime', starttime), ('boot_id', baseline['boot_id']),
                          ('uid', baseline['uid']), ('gid', baseline['gid'])]:
        require(current[key] == expected, 'Viewer identity mismatch: ' + key)
    require(all(current['environment'].get(k) == v for k, v in config['env'].items()),
            'Saved environment mismatch')
    return current

def inspect(config):
    current = process(int(config['pid']))
    require(current is not None, 'Saved PID is absent; cannot capture baseline')
    require(current['exe'] == config['exe'] and current['argv'] == config['argv'] and
            current['cwd'] == config['cwd'], 'Saved PID/exe/argv/cwd mismatch')
    require(all(current['environment'].get(k) == v for k, v in config['env'].items()), 'Saved env mismatch')
    require(sha(config['exe']) == current['exe_sha256'], 'Running executable differs from disk')
    current['files'] = files(config)
    current['owners'] = owners()
    current['windows'] = windows(current['pid'], config['env'])
    require(current['owners'] == [current['pid']], 'Expected saved PID as sole DMA owner')
    require(len(current['windows']) == 1 and current['windows'][0]['delete_supported'],
            'Expected one PID-associated WM_DELETE_WINDOW window')
    # Reject process replacement during the preflight itself.
    identity(config, current, current['pid'], current['starttime'])
    return current

def action(request, emit):
    config = request['config']
    mode = request['action']
    if mode == 'preflight':
        snap = inspect(config)
        if request.get('baseline'):
            expected = request['baseline']
            identity(config, expected, snap['pid'], expected['starttime'])
            verify_files(config, expected)
        emit('preflight', snapshot=snap)
        return
    baseline = request['baseline']
    require(boot() == baseline['boot_id'], 'Board boot changed since baseline')
    verify_files(config, baseline)
    deadline = time.monotonic() + request['timeout']
    if mode == 'stop':
        pid, start = request['target']['pid'], request['target']['starttime']
        identity(config, baseline, pid, start)
        require(owners() == [pid], 'Expected exact target PID as sole DMA owner')
        require(same_exe_pids(config['exe']) == [pid], 'Another saved-exe viewer exists')
        win = windows(pid, config['env'])
        require(len(win) == 1 and win[0]['delete_supported'], 'No unique PID-associated closeable window')
        # Revalidate immediately before the sole mutation.
        identity(config, baseline, pid, start)
        require(owners() == [pid], 'DMA ownership changed before close')
        require(windows(pid, config['env']) == win, 'Viewer window changed before close')
        require(time.monotonic() < deadline, 'Deadline exceeded before close')
        emit('close_requested', pid=pid, starttime=start, window=win[0]['id'])
        close_window(win[0]['id'], config['env'])
        while time.monotonic() < deadline:
            current = process(pid)
            own = owners()
            require(not any(v != pid for v in own), 'Another DMA owner appeared; left untouched')
            if current is not None:
                require(current['starttime'] == start, 'PID reused during shutdown; left untouched')
            if current is None and not own and not same_exe_pids(config['exe']):
                emit('stopped', pid=pid, starttime=start, device_unowned=True)
                return
            time.sleep(.2)
        raise RuntimeError('Graceful shutdown timed out; no force kill attempted')
    require(mode == 'restore', 'Unknown action')
    require(not owners(), 'DMA device already owned; restore refused')
    require(not same_exe_pids(config['exe']), 'Saved-exe viewer already running; restore refused')
    target = request['target']
    require(process(target['pid']) is None, 'Stopped PID exists/reused; restore refused')
    log = request['restore_log']
    environment = dict(baseline['environment'], **config['env'])
    def credentials():
        os.setgroups(baseline['groups'])
        os.setgid(baseline['gid'])
        os.setuid(baseline['uid'])
    # O_EXCL guarantees a unique log and never truncates the saved one.
    executable_fd = os.open(config['exe'], os.O_RDONLY | os.O_NOFOLLOW)
    try:
        executable = '/proc/self/fd/' + str(executable_fd)
        require(stat.S_ISREG(os.fstat(executable_fd).st_mode), 'Executable is not a regular file')
        require(sha(executable) == baseline['exe_sha256'], 'Opened executable SHA256 mismatch')
        fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb', buffering=0) as stream:
            os.fchown(stream.fileno(), baseline['uid'], baseline['gid'])
            child = subprocess.Popen(config['argv'], executable=executable, cwd=config['cwd'],
                                     env=environment, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True,
                                     close_fds=True, pass_fds=(executable_fd,), preexec_fn=credentials)
    except BaseException:
        # Log is retained even when launch fails.
        emit('launch_failed', log=log)
        raise
    finally:
        os.close(executable_fd)
    emit('launched', pid=child.pid, log=log)
    while time.monotonic() < deadline:
        require(child.poll() is None, 'Restored viewer exited; inspect unique log')
        current = process(child.pid)
        if current:
            identity(config, baseline, child.pid, current['starttime'])
            own = owners()
            require(not any(v != child.pid for v in own), 'Unexpected DMA owner after restore; left untouched')
            win = windows(child.pid, config['env'])
            if own == [child.pid] and len(win) == 1 and win[0]['delete_supported']:
                verify_files(config, baseline)
                emit('restored', pid=child.pid, starttime=current['starttime'],
                     exe_sha256=current['exe_sha256'], log=log, window=win[0]['id'])
                return
        time.sleep(.2)
    raise RuntimeError('Restore readiness timed out; launched process left untouched; inspect receipt/log')

if __name__ == '__main__':
    def emit(state, **details):
        print(json.dumps(dict(state=state, **details)), flush=True)
    try:
        request = json.loads(sys.argv[1])
        def expired(signum, frame):
            raise TimeoutError('60-second action bound reached; processes left untouched')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request['timeout'])
        action(request, emit)
    except BaseException as exc:
        emit('failed', error=str(exc))
        sys.exit(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
'''


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def remote_run(client, request, on_event):
    command = ('sudo -S -p \'\' python3 -c ' + shlex.quote(REMOTE_SOURCE)
               + ' ' + shlex.quote(json.dumps(request)))
    stdin, stdout, stderr = client.exec_command(command, timeout=15)
    channel = stdout.channel
    deadline = time.monotonic() + request['timeout'] + 20
    pending = b''
    diagnostics = bytearray()
    try:
        stdin.write('123456\n')
        stdin.flush()
        channel.shutdown_write()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('SSH deadline exceeded; inspect retained receipt before any retry')
            if channel.recv_ready():
                pending += channel.recv(65536)
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if line:
                        on_event(json.loads(line.decode()))
            if channel.recv_stderr_ready():
                diagnostics.extend(channel.recv_stderr(65536))
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                code = channel.recv_exit_status()
                if pending:
                    on_event(json.loads(pending.decode()))
                if code:
                    raise RuntimeError('Remote action failed (%s): %s' % (code, diagnostics.decode(errors='replace')))
                return
            time.sleep(.01)
    finally:
        channel.close()


def validate_receipt(receipt, action, digest, host, baseline_hash):
    if (receipt.get('schema') != 1 or receipt.get('action') != action or receipt.get('status') != 'success'
            or receipt.get('config_sha256') != digest or receipt.get('host') != host
            or receipt.get('baseline_sha256') != baseline_hash):
        raise ValueError('Receipt action/status/config/host/baseline mismatch')
    expected = 'stopped' if action == 'stop' else 'restored'
    event = receipt.get('events', [])[-1] if receipt.get('events') else {}
    if event.get('state') != expected or not isinstance(event.get('pid'), int) or event['pid'] <= 0 or not event.get('starttime'):
        raise ValueError('Receipt lacks verified process outcome')
    if action == 'stop' and event.get('device_unowned') is not True:
        raise ValueError('Stop receipt lacks verified unowned DMA device')
    return {'pid': event['pid'], 'starttime': event['starttime']}


def run(args):
    config = validate_config(read_json(args.config))
    digest = config_digest(args.config)
    if args.check:
        print(json.dumps({'valid': True, 'config_sha256': digest, 'pid': config['pid'],
                          'exe': config['exe'], 'ssh': False}, indent=2))
        return
    from board_host import board_host, ssh_connect
    host = board_host()
    baseline_path = args.baseline or args.config.with_name('current_viewer_baseline.json')
    baseline = None
    baseline_hash = None
    if baseline_path.exists():
        baseline = validate_baseline(read_json(baseline_path), digest, host, config)
        baseline_hash = config_digest(baseline_path)
    if args.capture_baseline and baseline_path.exists():
        raise ValueError('Baseline exists; capture never overwrites it')
    if not args.preflight and baseline is None:
        raise ValueError('Stop/restore requires --preflight --capture-baseline first')
    mode = 'preflight' if args.preflight else 'stop' if args.stop else 'restore'
    target = {'pid': int(config['pid']), 'starttime': baseline['starttime']} if baseline else None
    if args.target_receipt:
        target = validate_receipt(read_json(args.target_receipt), 'restore', digest, host, baseline_hash)
    if args.restore:
        if args.stop_receipt is None:
            raise ValueError('--restore requires --stop-receipt')
        target = validate_receipt(read_json(args.stop_receipt), 'stop', digest, host, baseline_hash)
    token = uuid.uuid4().hex
    directory = args.config.parent
    lock = directory / 'current_viewer_session.lock'
    directory.mkdir(parents=True, exist_ok=True)
    # Share the parent's board-session lock so the two tools cannot mutate the
    # same board concurrently. Preflight is serialized for consistent capture.
    board_lock = ROOT / 'log/100h_motion/board_session.lock'
    locks = [board_lock, lock]
    held = []
    receipt_path = directory / ('current_viewer_' + mode + '_' + token + '.json')
    receipt = {'schema': 1, 'action': mode, 'operation': token, 'status': 'running',
               'host': host, 'config_sha256': digest, 'baseline_sha256': baseline_hash,
               'config_path': str(args.config.resolve()), 'events': [],
               'stop_receipt': str(args.stop_receipt.resolve()) if args.stop_receipt else None}
    client = None
    try:
        for path in locks:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as stream:
                json.dump({'pid': os.getpid(), 'operation': token, 'action': mode}, stream)
            held.append(path)
        atomic_json(receipt_path, receipt)
        request = {'action': mode, 'config': config, 'baseline': baseline, 'target': target,
                   'timeout': args.timeout, 'restore_log': config['log'] + '.restore-' + token}
        def event(value):
            receipt['events'].append(value)
            atomic_json(receipt_path, receipt)
        client = ssh_connect()
        remote_run(client, request, event)
        expected = {'preflight': 'preflight', 'stop': 'stopped', 'restore': 'restored'}[mode]
        if not receipt['events'] or receipt['events'][-1]['state'] != expected:
            raise RuntimeError('Remote command returned without verified outcome')
        if args.capture_baseline:
            captured = {'schema': 1, 'host': host, 'config_sha256': digest,
                        'snapshot': receipt['events'][-1]['snapshot']}
            validate_baseline(captured, digest, host, config)
            with baseline_path.open('x', encoding='utf-8') as stream:
                json.dump(captured, stream, indent=2)
            receipt['captured_baseline'] = str(baseline_path)
        if args.preflight:
            snap = receipt['events'][-1]['snapshot']
            print(json.dumps({'exe_sha256': snap['exe_sha256'], 'config_sha256': digest,
                              'files': snap['files'], 'owners': snap['owners'], 'windows': snap['windows']}, indent=2))
        receipt['status'] = 'success'
    except BaseException as exc:
        receipt['status'] = 'failed'
        receipt['error'] = str(exc)
        raise
    finally:
        if held:
            atomic_json(receipt_path, receipt)
            print('Session receipt: ' + str(receipt_path))
        if client:
            client.close()
        for path in reversed(held):
            if read_json(path).get('operation') == token:
                path.unlink()


def self_test():
    """Local mocked safety regressions; never imports SSH or touches hardware."""
    import copy
    import unittest
    from unittest.mock import Mock, patch
    namespace = {'__name__': 'viewer_remote_test'}
    exec(compile(REMOTE_SOURCE, '<remote viewer agent>', 'exec'), namespace)
    config = validate_config(read_json(DEFAULT_CONFIG))
    snap = {'pid': int(config['pid']), 'exe': config['exe'], 'exe_sha256': 'a' * 64,
            'argv': config['argv'], 'cwd': config['cwd'], 'starttime': '1234', 'boot_id': 'boot',
            'environment': config['env'], 'uid': 0, 'gid': 0, 'groups': [], 'files': {'stereo': 'b' * 64}}
    class SafetyTests(unittest.TestCase):
        def test_schema_rejects_bad_pid_argv_env(self):
            for key, value in [('pid', '0'), ('pid', '-1'), ('pid', True), ('exe', '/tmp/unknown'),
                               ('argv', ['sh', '-c', 'detview']), ('env', {'DISPLAY': ':0'})]:
                bad = copy.deepcopy(config); bad[key] = value
                with self.assertRaises(ValueError):
                    validate_config(bad)

        def test_baseline_required_hash_and_binding(self):
            base = {'schema': 1, 'host': 'board', 'config_sha256': 'c' * 64, 'snapshot': snap}
            with self.assertRaises(ValueError):
                validate_baseline(base, 'd' * 64, 'board', config)
            bad = copy.deepcopy(base); bad['snapshot']['exe_sha256'] = ''
            with self.assertRaises(ValueError):
                validate_baseline(bad, 'c' * 64, 'board', config)

        def stop_case(self, owner_list=None, identity_error=None, win=None, timeout=1, proc=None):
            close = Mock()
            events = []
            request = {'config': config, 'action': 'stop', 'baseline': snap, 'timeout': timeout,
                       'target': {'pid': snap['pid'], 'starttime': snap['starttime']}}
            mocks = {'boot': lambda: 'boot', 'verify_files': Mock(), 'identity': Mock(side_effect=identity_error),
                     'owners': Mock(side_effect=owner_list or [[snap['pid']], [snap['pid']], []]),
                     'same_exe_pids': Mock(side_effect=[[snap['pid']], []]),
                     'windows': Mock(return_value=win if win is not None else [{'id': '0x123', 'delete_supported': True}]),
                     'close_window': close, 'process': Mock(return_value=proc)}
            with patch.dict(namespace, mocks):
                try:
                    namespace['action'](request, lambda state, **details: events.append(dict(state=state, **details)))
                except RuntimeError:
                    return close, events, False
            return close, events, True

        def test_unknown_owner_no_mutation(self):
            close, _, ok = self.stop_case(owner_list=[[999]])
            self.assertFalse(ok); close.assert_not_called()

        def test_wrong_identity_no_mutation(self):
            close, _, ok = self.stop_case(identity_error=RuntimeError('SHA mismatch'))
            self.assertFalse(ok); close.assert_not_called()

        def test_wrong_window_no_mutation(self):
            for win in ([], [{'id': '0x1', 'delete_supported': False}],
                        [{'id': '0x1', 'delete_supported': True}] * 2):
                close, _, ok = self.stop_case(win=win)
                self.assertFalse(ok); close.assert_not_called()

        def test_graceful_close_then_exited_unowned(self):
            close, events, ok = self.stop_case()
            self.assertTrue(ok); close.assert_called_once_with('0x123', config['env'])
            self.assertEqual(events[-1]['state'], 'stopped')
            self.assertTrue(events[-1]['device_unowned'])

        def test_deadline_and_reused_pid(self):
            close, _, ok = self.stop_case(timeout=0)
            self.assertFalse(ok); close.assert_not_called()
            close, events, ok = self.stop_case(proc={'starttime': 'different'})
            self.assertFalse(ok); close.assert_called_once()
            self.assertNotIn('stopped', [e['state'] for e in events])

        def test_restore_refuses_owned_device_before_launch(self):
            launch = Mock()
            with patch.dict(namespace, {'boot': lambda: 'boot', 'verify_files': Mock(), 'owners': lambda: [999]}):
                with patch.object(namespace['subprocess'], 'Popen', launch):
                    with self.assertRaises(RuntimeError):
                        namespace['action']({'config': config, 'action': 'restore', 'baseline': snap,
                                             'timeout': 1}, Mock())
            launch.assert_not_called()

        def test_identity_rejects_hash_pid_reuse_and_argv_change(self):
            for key, value in [('exe_sha256', 'f' * 64), ('starttime', 'reused'),
                               ('argv', ['different']), ('boot_id', 'reboot')]:
                changed = copy.deepcopy(snap); changed[key] = value
                with patch.dict(namespace, {'process': lambda pid: changed}):
                    with self.assertRaises(RuntimeError):
                        namespace['identity'](config, snap, snap['pid'], snap['starttime'])

        def test_restore_exact_launch_and_verified_receipt(self):
            child = Mock(pid=456); child.poll.return_value = None
            stream = Mock(); stream.fileno.return_value = 17
            context = Mock(); context.__enter__ = Mock(return_value=stream)
            context.__exit__ = Mock(return_value=False)
            launch = Mock(return_value=child)
            events = []
            current = copy.deepcopy(snap); current.update(pid=456, starttime='new-start')
            request = {'config': config, 'action': 'restore', 'baseline': snap, 'timeout': 1,
                       'target': {'pid': snap['pid'], 'starttime': snap['starttime']},
                       'restore_log': config['log'] + '.restore-unique'}
            mocks = {'boot': lambda: 'boot', 'verify_files': Mock(),
                     'owners': Mock(side_effect=[[], [456]]), 'same_exe_pids': Mock(return_value=[]),
                     'process': Mock(side_effect=[None, current, current]), 'sha': Mock(return_value='a' * 64),
                     'windows': Mock(return_value=[{'id': '0xabc', 'delete_supported': True}])}
            with patch.dict(namespace, mocks):
                with patch.object(namespace['os'], 'open', Mock(side_effect=[16, 17])) as opening, \
                     patch.object(namespace['os'], 'O_NOFOLLOW', 131072, create=True), \
                     patch.object(namespace['os'], 'fstat', Mock(return_value=Mock(st_mode=0o100755))), \
                     patch.object(namespace['os'], 'fdopen', Mock(return_value=context)), \
                     patch.object(namespace['os'], 'fchown', Mock(), create=True), \
                     patch.object(namespace['os'], 'close', Mock()), \
                     patch.object(namespace['subprocess'], 'Popen', launch):
                    namespace['action'](request, lambda state, **details: events.append(dict(state=state, **details)))
            positional, options = launch.call_args
            self.assertEqual(positional[0], config['argv'])
            self.assertEqual(options['cwd'], config['cwd'])
            self.assertEqual(options['env'], snap['environment'])
            self.assertEqual(options['executable'], '/proc/self/fd/16')
            self.assertEqual(options['pass_fds'], (16,))
            self.assertTrue(opening.call_args_list[1].args[1] & os.O_EXCL)
            self.assertEqual(events[-1]['state'], 'restored')
            self.assertEqual(events[-1]['pid'], 456)
            self.assertEqual(events[-1]['starttime'], 'new-start')

        def test_failed_or_unbound_stop_receipt_refused(self):
            receipt = {'schema': 1, 'action': 'stop', 'status': 'success', 'host': 'board',
                       'config_sha256': 'config', 'baseline_sha256': 'baseline',
                       'events': [{'state': 'stopped', 'pid': 3, 'starttime': '4', 'device_unowned': True}]}
            self.assertEqual(validate_receipt(receipt, 'stop', 'config', 'board', 'baseline')['pid'], 3)
            for key, value in [('status', 'failed'), ('host', 'other'), ('baseline_sha256', 'changed')]:
                bad = copy.deepcopy(receipt); bad[key] = value
                with self.assertRaises(ValueError):
                    validate_receipt(bad, 'stop', 'config', 'board', 'baseline')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_mutually_exclusive_group(required=True)
    for flag in ('check', 'preflight', 'stop', 'restore', 'self-test'):
        actions.add_argument('--' + flag, action='store_true')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--capture-baseline', action='store_true')
    parser.add_argument('--stop-receipt', type=Path)
    parser.add_argument('--target-receipt', type=Path)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error('--timeout must be in (0, 60]')
    if args.capture_baseline and not args.preflight:
        parser.error('--capture-baseline requires --preflight')
    if args.stop_receipt and not args.restore:
        parser.error('--stop-receipt requires --restore')
    if args.target_receipt and not args.stop:
        parser.error('--target-receipt requires --stop')
    if args.self_test:
        return self_test()
    try:
        run(args)
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
