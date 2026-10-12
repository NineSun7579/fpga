"""Board-side lifecycle primitives. Imported locally without side effects.

Only deploy_candidate.py uploads/invokes this helper after explicit execution.
No signals are sent to viewers. Unknown owners and uncertain retirement fail closed.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

DEVICE = '/dev/pango_pci_driver'
BDF = '0002:21:00.0'
PCI = Path('/sys/bus/pci/devices') / BDF
MODULE = Path('/sys/module/pango_zc')


def digest(path):
    with open(path, 'rb') as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        return value.hexdigest()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(pid):
    p = Path('/proc') / str(int(pid))
    stat = (p / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': int(pid), 'starttime': stat[19],
            'sha256': digest(p / 'exe'), 'exe': os.readlink(p / 'exe')}


def same_process(expected):
    try:
        return identity(expected['pid']) == expected
    except FileNotFoundError:
        return False


def process_state(pid):
    """Read lifetime identity independently of /proc/PID/exe during teardown."""
    try:
        stat = Path('/proc', str(int(pid)), 'stat').read_text().rsplit(')', 1)[1].split()
        return {'state': stat[0], 'starttime': stat[19]}
    except FileNotFoundError:
        return None


def owners():
    # fuser includes mmap ownership; /proc FD inspection alone misses VMAs.
    if not Path(DEVICE).exists():
        check(not (PCI / 'driver').exists(), 'Missing device node with bound endpoint')
        check(not MODULE.exists() or (MODULE / 'refcnt').read_text().strip() == '0',
              'Missing node with outstanding module references')
        return []
    result = subprocess.run(['fuser', DEVICE], capture_output=True, text=True)
    check(result.returncode in (0, 1), 'fuser failed: ' + result.stderr)
    if result.returncode == 1:
        check(not result.stdout.strip() and not result.stderr.strip(),
              'fuser error cannot be treated as no owner: ' + result.stderr)
        return []
    return sorted(int(x) for x in result.stdout.split())


def no_owner():
    check(not owners(), 'Device owned; preserve process and hardware state')


def retired():
    no_owner()
    check(MODULE.is_dir(), 'Expected loaded pango_zc module')
    check((MODULE / 'refcnt').read_text().strip() == '0',
          'Module references remain: lease/import/VMA/quarantine uncertain; preserve state')


class KeyEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong),
                ('x', C.c_int), ('y', C.c_int), ('x_root', C.c_int), ('y_root', C.c_int),
                ('state', C.c_uint), ('keycode', C.c_uint), ('same_screen', C.c_int)]


class XEvent(C.Union):
    _fields_ = [('key', KeyEvent), ('pad', C.c_long * 24)]


def send_q(expected, env):
    """Find precisely one _NET_WM_PID window recursively and send q press/release."""
    pid = expected['pid']
    for key in ('DISPLAY', 'XAUTHORITY'):
        if key in env:
            os.environ[key] = env[key]
    x = C.CDLL('libX11.so.6')
    window = C.c_ulong
    x.XOpenDisplay.argtypes = [C.c_char_p]; x.XOpenDisplay.restype = C.c_void_p
    x.XDefaultRootWindow.argtypes = [C.c_void_p]; x.XDefaultRootWindow.restype = window
    x.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]; x.XInternAtom.restype = window
    x.XQueryTree.argtypes = [C.c_void_p, window, C.POINTER(window), C.POINTER(window),
                            C.POINTER(C.POINTER(window)), C.POINTER(C.c_uint)]
    x.XGetWindowProperty.argtypes = [C.c_void_p, window, window, C.c_long, C.c_long,
                                    C.c_int, window, C.POINTER(window), C.POINTER(C.c_int),
                                    C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                                    C.POINTER(C.POINTER(C.c_ubyte))]
    x.XKeysymToKeycode.argtypes = [C.c_void_p, C.c_ulong]; x.XKeysymToKeycode.restype = C.c_uint
    x.XSendEvent.argtypes = [C.c_void_p, window, C.c_int, C.c_long, C.POINTER(XEvent)]
    x.XFlush.argtypes = [C.c_void_p]; x.XCloseDisplay.argtypes = [C.c_void_p]
    x.XFree.argtypes = [C.c_void_p]
    display = x.XOpenDisplay(env.get('DISPLAY', ':0').encode())
    check(display, 'Cannot open X display; viewer preserved')
    try:
        root = x.XDefaultRootWindow(display)
        atom = x.XInternAtom(display, b'_NET_WM_PID', 1)
        check(atom, 'No _NET_WM_PID atom')
        stack, found = [root], []
        while stack:
            w = stack.pop()
            actual = window(); fmt = C.c_int(); count = C.c_ulong(); after = C.c_ulong()
            data = C.POINTER(C.c_ubyte)()
            rc = x.XGetWindowProperty(display, w, atom, 0, 1, 0, 6,
                                      C.byref(actual), C.byref(fmt), C.byref(count),
                                      C.byref(after), C.byref(data))
            if rc == 0 and data:
                try:
                    if actual.value == 6 and fmt.value == 32 and count.value == 1:
                        if C.cast(data, C.POINTER(C.c_ulong))[0] == pid:
                            found.append(w)
                finally:
                    x.XFree(data)
            children = C.POINTER(window)(); n = C.c_uint(); rr = window(); parent = window()
            if x.XQueryTree(display, w, C.byref(rr), C.byref(parent), C.byref(children), C.byref(n)):
                stack.extend(children[i] for i in range(n.value))
            if children:
                x.XFree(children)
        check(len(found) == 1, 'Expected exactly one PID-owned X window; viewer preserved')
        check(same_process(expected) and owners() == [pid],
              'Process/ownership changed during X tree query; no q sent')
        for event_type, mask in ((2, 1), (3, 2)):
            event = XEvent()
            event.key = KeyEvent(type=event_type, send_event=1, display=display,
                                 window=found[0], root=root, keycode=x.XKeysymToKeycode(display, ord('q')),
                                 same_screen=1)
            check(x.XSendEvent(display, found[0], 0, mask, C.byref(event)), 'XSendEvent failed')
        x.XFlush(display)
    finally:
        x.XCloseDisplay(display)


def stop(q):
    expected = q['identity']
    check(same_process(expected), 'PID/executable/start time changed; no q sent')
    check(owners() == [expected['pid']], 'Unknown or missing device owner; no q sent')
    send_q(expected, q['env'])
    deadline = time.monotonic() + q.get('timeout', 45)
    while time.monotonic() < deadline:
        state = process_state(expected['pid'])
        if state is not None:
            check(state['starttime'] == expected['starttime'], 'PID reused; preserve state')
            if state['state'] != 'Z':
                try:
                    check(identity(expected['pid']) == expected,
                          'Executable identity changed; preserve state')
                except FileNotFoundError:
                    # Exit may remove exe before stat. Wait for zombie/disappearance.
                    pass
                time.sleep(.2)
                continue
        if state is None or state['state'] == 'Z':
            if q.get('status') and not Path(q['status']).exists():
                time.sleep(.2)
                continue
            if q.get('status'):
                status = Path(q['status'])
                result = json.loads(status.read_text())
                check(result['identity'] == expected and result['returncode'] == 0,
                       'Candidate exit not clean; consumer completion uncertain')
            check(MODULE.is_dir(), 'Expected loaded pango_zc module')
            remaining = owners()
            check(remaining in ([], [expected['pid']]), 'Unknown owner after exit; preserve state')
            if remaining or (MODULE / 'refcnt').read_text().strip() != '0':
                time.sleep(.2)
                continue
            retired()
            final_state = process_state(expected['pid'])
            check(final_state is None or
                  (final_state['starttime'] == expected['starttime'] and final_state['state'] == 'Z'),
                  'PID changed during retirement; preserve state')
            return {'retired': True, 'consumer_contract':
                    'clean exit plus refcnt=0; token/quarantine would pin module; no independent NPU fence proof'}
        time.sleep(.2)
    raise RuntimeError('Graceful q timeout; no signal, removal or automatic rollback')


def snapshot(q):
    pid = q['pid']; current = identity(pid)
    check(current['sha256'] == q['active_sha'], 'ACTIVE executable identity mismatch')
    check(owners() == [pid], 'Baseline PID is not sole real device owner')
    p = Path('/proc', str(pid))
    env = dict(item.decode().split('=', 1) for item in (p / 'environ').read_bytes().split(b'\0') if item)
    argv = [item.decode() for item in (p / 'cmdline').read_bytes().split(b'\0') if item]
    status = (p / 'status').read_text().splitlines()
    uid = int(next(line for line in status if line.startswith('Uid:')).split()[2])
    gid = int(next(line for line in status if line.startswith('Gid:')).split()[2])
    return {'identity': current, 'argv': argv, 'env': env, 'uid': uid, 'gid': gid,
            'groups': [int(x) for x in next(line for line in status
                                           if line.startswith('Groups:')).split()[1:]],
            'cwd': os.readlink(p / 'cwd'),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def detached(q):
    no_owner()
    check(not PCI.exists(), 'Endpoint must be removed before module operation')
    if q['operation'] == 'unload':
        retired()
        subprocess.run(['rmmod', 'pango_zc'], check=True)
        check(not MODULE.exists(), 'Module did not unload')
    else:
        check(not MODULE.exists(), 'Old module remains; no insertion')
        check(digest(q['module']) == q['sha256'], 'Module hash mismatch')
        subprocess.run(['insmod', q['module'], 'vendor_id=0x0755', 'device_id=0x0755'], check=True)
    return {'module_operation': q['operation']}


def remove(q):
    retired()
    check(PCI.exists(), 'Expected enumerated endpoint')
    driver = (PCI / 'driver').resolve()
    check(driver.name in ('pango_zc', 'pango_pci_driver'), 'Unexpected PCI driver')
    (driver / 'unbind').write_text(BDF)
    # Do not continue if unbind discovered a live generation/quarantine.
    retired()
    (PCI / 'remove').write_text('1')
    check(not PCI.exists(), 'PCI removal failed')
    return {'removed': BDF}


def rescan(q):
    check(MODULE.exists() and not PCI.exists(), 'Insert module before rescan')
    host = Path('/sys/bus/platform/devices/3c0800000.pcie')
    if not (host / 'driver').exists():
        Path('/sys/bus/platform/drivers/rk-pcie/bind').write_text(host.name)
    Path('/sys/bus/pci/rescan').write_text('1')
    for _ in range(50):
        if PCI.exists():
            break
        time.sleep(.1)
    check(PCI.exists(), 'PCI rescan failed')
    # Probe can bind automatically. Never reinsert/unload a module here.
    if not (PCI / 'driver').exists():
        Path('/sys/bus/pci/drivers/pango_zc/bind').write_text(BDF)
    check((PCI / 'driver').resolve().name == 'pango_zc', 'Unexpected binding')
    return {'bound': str((PCI / 'driver').resolve())}


def parse_modinfo(text, field):
    """Extract exactly one nonempty field from GNU readelf's string dump."""
    values = []
    for line in text.splitlines():
        match = re.fullmatch(r'\s*\[\s*[0-9a-fA-F]+\]\s+(.*)', line)
        if match and match.group(1).startswith(field + '='):
            values.append(match.group(1)[len(field) + 1:].strip())
    check(len(values) == 1 and bool(values[0]),
          'Missing, empty or duplicate ELF .modinfo field: ' + field)
    return values[0]


def elf_modinfo(path, field):
    env = dict(os.environ, LC_ALL='C')
    output = subprocess.check_output(['readelf', '-p', '.modinfo', str(path)],
                                     text=True, env=env)
    return parse_modinfo(output, field)


def stage(q):
    import pwd  # Linux-only, imported only during explicitly executed staging.
    dest = Path(q['remote'])
    check(str(dest).startswith('/userdata/linaro/ov56401-deploy-'), 'Stage must use userdata')
    check(shutil.disk_usage('/userdata').free >= 128 * 1024 * 1024, 'Insufficient userdata free space')
    dest.mkdir(exist_ok=False)
    account = pwd.getpwnam('linaro')
    os.chown(dest, account.pw_uid, account.pw_gid)
    os.chmod(dest, 0o700)
    lock = Path('/userdata/linaro/ov56401-deploy.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(str(dest))
    old = Path('/userdata/linaro/fpga-zero-copy-driver-stage/pango_zc.ko')
    loaded_src = (MODULE / 'srcversion').read_text().strip()
    file_src = elf_modinfo(old, 'srcversion')
    check(loaded_src and loaded_src == file_src, 'Backup file does not match loaded module srcversion')
    shutil.copy2(old, dest / 'original-pango_zc.ko')
    check(digest(old) == digest(dest / 'original-pango_zc.ko'), 'Original module backup mismatch')
    return {'module': str(dest / 'original-pango_zc.ko'), 'sha256': digest(old)}


def module_compatible(q):
    check(digest(q['module']) == q['sha256'], 'Module identity mismatch')
    magic = elf_modinfo(q['module'], 'vermagic')
    check(magic.split()[0] == os.uname().release, 'Module/kernel release mismatch')
    return {'vermagic': magic, 'kernel_release': os.uname().release}


def launch(q):
    no_owner()
    check(digest(q['exe']) == q['sha256'], 'Launch executable hash mismatch')
    # Older callers use fixed filenames. Preserve their evidence before starting.
    archive = uuid.uuid4().hex
    for key in ('config', 'identity_file', 'status'):
        previous = Path(q[key])
        if previous.exists():
            previous.rename(previous.with_name(previous.name + '.previous-' + archive))
    temporary = Path(q['config']).parent / 'tmp'
    temporary.mkdir(exist_ok=True)
    os.chown(temporary, q['uid'], q['gid'])
    os.chmod(temporary, 0o700)
    # Keep candidate scratch off the small root filesystem. ACTIVE restores its
    # captured environment exactly and may already specify a TMPDIR.
    if q.get('candidate'):
        q['env']['TMPDIR'] = str(temporary)
    config = Path(q['config'])
    config.write_text(json.dumps(q))
    os.chmod(config, 0o600)
    with open(q['supervisor_log'], 'ab', buffering=0) as log:
        subprocess.Popen([sys.executable, __file__, '--supervise', str(config)],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        path = Path(q['identity_file'])
        if path.exists():
            current = json.loads(path.read_text())
            check(current['sha256'] == q['sha256'] and same_process(current), 'Launched process mismatch')
            if owners() == [current['pid']]:
                return current
            check(owners() in ([], [current['pid']]), 'Unknown owner after launch; preserve all processes')
        time.sleep(.2)
    raise RuntimeError('Launch did not acquire device; preserve process, inspect logs')


def supervise(config):
    q = json.loads(Path(config).read_text())
    def demote():
        os.setgroups(q['groups']); os.setgid(q['gid']); os.setuid(q['uid'])
    with open(q['log'], 'ab', buffering=0) as log:
        child = subprocess.Popen(q['argv'], executable=q['exe'], cwd=q['cwd'], env=q['env'],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, preexec_fn=demote)
        current = None
        for _ in range(100):
            try:
                observed = identity(child.pid)
                if observed['sha256'] == q['sha256']:
                    current = observed; break
            except FileNotFoundError:
                pass
            time.sleep(.01)
        check(current, 'Child exec failed; no valid launch identity')
        target = Path(q['identity_file'])
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(current))
        temporary.replace(target)
        rc = child.wait()
        target = Path(q['status'])
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'identity': current, 'returncode': rc}))
        temporary.replace(target)


def dispatch(q):
    action = q['action']
    if action == 'snapshot': return snapshot(q)
    if action == 'stage': return stage(q)
    if action == 'module_compatible': return module_compatible(q)
    if action == 'stop': return stop(q)
    if action == 'remove': return remove(q)
    if action == 'module': return detached(q)
    if action == 'rescan': return rescan(q)
    if action == 'launch': return launch(q)
    if action == 'hash': return {'sha256': digest(q['path'])}
    if action == 'boot': return {'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    if action == 'verify_retired':
        if q.get('status'):
            result = json.loads(Path(q['status']).read_text())
            check(result['identity'] == q['identity'] and result['returncode'] == 0,
                  'Candidate exit not clean; consumer completion uncertain')
        if q.get('identity'):
            state = process_state(q['identity']['pid'])
            check(state is None or (state['starttime'] == q['identity']['starttime'] and state['state'] == 'Z'),
                  'PID changed or still running; preserve state')
        retired(); return {'retired': True}
    if action == 'verify_lock':
        check(Path('/userdata/linaro/ov56401-deploy.lock').read_text() == q['remote'],
              'Receipt does not own deployment lock')
        return {'lock_owned': True}
    if action == 'release_lock':
        lock = Path('/userdata/linaro/ov56401-deploy.lock')
        check(lock.read_text() == q['remote'], 'Lock ownership mismatch')
        lock.unlink(); return {'released': True}
    raise RuntimeError('Unknown action')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--supervise':
        supervise(sys.argv[2])
    else:
        print(json.dumps(dispatch(json.loads(sys.argv[1]))))
