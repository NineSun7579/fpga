
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys

DEVICE = '/dev/pango_pci_driver'
def process(pid):
    base = Path('/proc') / str(pid)
    text = (base / 'stat').read_text().rsplit(')', 1)[1].split()
    exe = os.readlink(str(base / 'exe'))
    return {'pid': int(pid), 'state': text[0], 'starttime': text[19],
            'exe': exe, 'sha256': hashlib.sha256((base / 'exe').read_bytes()).hexdigest(),
            'cmdline': (base / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')}

def owners():
    result = []
    dev = Path(DEVICE)
    if not dev.exists():
        raise RuntimeError('Device node missing; ownership cannot be established')
    for base in Path('/proc').iterdir():
        if not base.name.isdigit():
            continue
        try:
            found = False
            for fd in (base / 'fd').iterdir():
                try:
                    target = os.readlink(str(fd))
                    if target == DEVICE or target.startswith(DEVICE + ' '):
                        found = True
                except FileNotFoundError:
                    pass
            if found:
                result.append(process(base.name))
        except FileNotFoundError:
            continue
        # Permission errors intentionally fail rather than implying no owner.
    return result

class Key(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong), ('x', C.c_int),
                ('y', C.c_int), ('x_root', C.c_int), ('y_root', C.c_int),
                ('state', C.c_uint), ('keycode', C.c_uint), ('same_screen', C.c_int)]
class Event(C.Union):
    _fields_ = [('key', Key), ('pad', C.c_long * 24)]

def quit_ui(pid, start, sha, symbol):
    expected = process(pid)
    if (expected['starttime'] != start or expected['sha256'] != sha or
            expected['state'] in ('T', 't', 'Z', 'D') or
            [r['pid'] for r in owners()] != [pid]):
        raise RuntimeError('Viewer identity/state/sole ownership changed')
    x = C.CDLL('libX11.so.6')
    signatures = {
        'XOpenDisplay': ([C.c_char_p], C.c_void_p),
        'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
        'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
        'XQueryTree': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                        C.POINTER(C.POINTER(C.c_ulong)), C.POINTER(C.c_uint)], C.c_int),
        'XGetWindowProperty': ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long,
            C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int),
            C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.c_void_p)], C.c_int),
        'XFree': ([C.c_void_p], C.c_int),
        'XStringToKeysym': ([C.c_char_p], C.c_ulong),
        'XKeysymToKeycode': ([C.c_void_p, C.c_ulong], C.c_uint),
        'XSendEvent': ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)], C.c_int),
        'XSync': ([C.c_void_p, C.c_int], C.c_int),
        'XCloseDisplay': ([C.c_void_p], C.c_int)}
    for name, (inputs, output) in signatures.items():
        func = getattr(x, name)
        func.argtypes, func.restype = inputs, output
    display = x.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open production X display')
    try:
        root = x.XDefaultRootWindow(display)
        atom = x.XInternAtom(display, b'_NET_WM_PID', 1)
        if not atom:
            raise RuntimeError('No _NET_WM_PID atom')
        windows, todo, seen = [], [root], set()
        while todo:
            window = todo.pop()
            if window in seen:
                continue
            seen.add(window)
            actual, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
            fmt, data = C.c_int(), C.c_void_p()
            rc = x.XGetWindowProperty(display, window, atom, 0, 1, 0, 6,
                C.byref(actual), C.byref(fmt), C.byref(count), C.byref(remaining), C.byref(data))
            if rc == 0 and data.value:
                try:
                    if actual.value == 6 and fmt.value == 32 and count.value == 1:
                        if C.cast(data, C.POINTER(C.c_ulong))[0] == pid:
                            windows.append(window)
                finally:
                    x.XFree(data)
            tree_root, parent, children, n = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
            if x.XQueryTree(display, window, C.byref(tree_root), C.byref(parent), C.byref(children), C.byref(n)):
                todo.extend(children[i] for i in range(n.value))
                if children:
                    x.XFree(C.cast(children, C.c_void_p))
        if len(windows) != 1:
            raise RuntimeError('Expected exactly one PID-matched Qt window: ' + repr(windows))
        current = process(pid)
        if current['starttime'] != start or current['sha256'] != sha:
            raise RuntimeError('PID reused before key dispatch')
        code = x.XKeysymToKeycode(display, x.XStringToKeysym(symbol.encode()))
        if not code:
            raise RuntimeError('Quit key has no keycode')
        for event_type, mask in ((2, 1), (3, 2)):
            event = Event()
            event.key.type, event.key.send_event = event_type, 1
            event.key.display, event.key.window, event.key.root = display, windows[0], root
            event.key.keycode, event.key.same_screen = code, 1
            if not x.XSendEvent(display, windows[0], 0, mask, C.byref(event)):
                raise RuntimeError('XSendEvent failed')
        x.XSync(display, 0)
        print(json.dumps({'pid': pid, 'window': windows[0], 'key': symbol, 'method': 'XSendEvent'}))
    finally:
        x.XCloseDisplay(display)

if sys.argv[1] == 'owners':
    print(json.dumps(owners()))
elif sys.argv[1] == 'process':
    print(json.dumps(process(int(sys.argv[2]))))
elif sys.argv[1] == 'retired':
    pid, start = int(sys.argv[2]), sys.argv[3]
    try:
        current = process(pid)
        retired = current['starttime'] != start or current['state'] == 'Z'
    except FileNotFoundError:
        retired = True
    print(json.dumps({'retired': retired, 'owners': owners()}))
elif sys.argv[1] == 'quit':
    quit_ui(int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5])
else:
    raise RuntimeError('Unknown helper operation')
