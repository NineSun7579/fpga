#!/usr/bin/env python3
"""Run on the board: exclusive, sequential detview live FPS acceptance.

Uses the existing X11 session and libraries; writes artifacts under /userdata.
No SSH credentials, package installation, driver changes or camera register writes.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import time

WORK = Path('/userdata/linaro/detview-vision-work')
OUT = WORK / 'live'
ENV = dict(os.environ, DISPLAY=':0', XAUTHORITY='/var/run/lightdm/root/:0')
ENV['QT_QPA_PLATFORM'] = 'xcb'
HZ = os.sysconf('SC_CLK_TCK')
WB = 'wb_v4_combo'
ZEBRA = 'zebra-rk3568-raw-dfl6'


def command(args):
    return subprocess.run(args, env=ENV, capture_output=True, text=True,
                          errors='replace', timeout=10).stdout


def pids(name):
    return [int(p) for p in command(['pgrep', '-x', name]).split()]


def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ')[1][0] != 'Z'
    except FileNotFoundError:
        return False


def key(pid, text):
    tree = command(['xwininfo', '-root', '-tree'])
    window = None
    for match in re.finditer(r'^\s*(0x[0-9a-f]+).*?\s(\d+)x(\d+)[+-]', tree, re.M):
        if int(match[2]) < 100 or int(match[3]) < 100:
            continue
        candidate = match[1]
        prop = command(['xprop', '-id', candidate, '_NET_WM_PID'])
        if re.search(r'=\s*' + str(pid) + r'\s*$', prop):
            window = int(candidate, 16)
            break
    if window is None:
        raise RuntimeError(f'No visible X11 window for PID {pid}')
    x11 = ctypes.CDLL('libX11.so.6')
    xtst = ctypes.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    display = x11.XOpenDisplay(b':0')
    if not display:
        raise RuntimeError('Cannot open the existing X11 display')
    try:
        x11.XSetInputFocus(display, window, 2, 0)
        code = x11.XKeysymToKeycode(display, x11.XStringToKeysym(text.encode()))
        xtst.XTestFakeKeyEvent(display, code, 1, 0)
        xtst.XTestFakeKeyEvent(display, code, 0, 0)
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)


def quit_viewer(pid):
    key(pid, 'q')
    deadline = time.monotonic() + 12
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if alive(pid):
        raise RuntimeError(f'Viewer PID {pid} did not complete graceful shutdown; no second PCIe open')


def read_optional(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def sample(pid, phase):
    stat = Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()
    memory = Path('/proc/meminfo').read_text()
    thermal = {p.parent.name: int(p.read_text()) / 1000
               for p in Path('/sys/class/thermal').glob('thermal_zone*/temp')}
    return {'monotonic_s': time.monotonic(), 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'phase': phase, 'pid': pid, 'cpu_seconds': (int(stat[11]) + int(stat[12])) / HZ,
            'rss_kib': int(stat[21]) * os.sysconf('SC_PAGE_SIZE') // 1024,
            'system_cpu': Path('/proc/stat').read_text().splitlines()[0],
            'mem_available_kib': int(re.search(r'MemAvailable:\s*(\d+)', memory)[1]),
            'npu_load': read_optional('/sys/kernel/debug/rknpu/load'), 'thermal_c': thermal}


def watch(process, samples, seconds, phase):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        try:
            samples.write(json.dumps(sample(process.pid, phase)) + '\n')
            samples.flush()
        except FileNotFoundError:
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def start(label, extra, duration=None):
    if pids('camview') or pids('detview'):
        raise RuntimeError('Another camera viewer remains active')
    args = [str(WORK / 'build/detview'), '--model', WB, '--fullscreen', '--shot', '15'] + extra
    if duration is not None:
        args += ['--duration', str(duration)]
    log = (OUT / (label + '.log')).open('w')
    proc = subprocess.Popen(args, cwd=WORK / 'build', env=ENV, stdout=log, stderr=log,
                            start_new_session=True)
    log.close()
    print(json.dumps({'event': 'start', 'label': label, 'pid': proc.pid, 'args': args}), flush=True)
    return proc


def bounded(label, extra):
    proc = start(label, extra, 55)
    with (OUT / (label + '.jsonl')).open('w') as samples:
        watch(proc, samples, 70, 'six-camera')
    if proc.poll() is None:
        quit_viewer(proc.pid)
    rc = proc.wait(timeout=5)
    print(json.dumps({'event': 'exit', 'label': label, 'rc': rc}), flush=True)
    if rc != 0:
        raise RuntimeError(f'{label} failed with exit {rc}')
    if '[capture] camera=' not in (OUT / (label + '.log')).read_text(errors='replace'):
        raise RuntimeError(f'{label} never reached six-camera acquisition')


def main():
    os.environ.update(DISPLAY=ENV['DISPLAY'], XAUTHORITY=ENV['XAUTHORITY'])
    OUT.mkdir(exist_ok=True)
    (OUT / 'kernel-before.log').write_text(command(['dmesg']))
    previous = pids('camview')
    if len(previous) != 1 or pids('detview'):
        raise RuntimeError('Expected exactly one original camview and no detview')
    pid = previous[0]
    (OUT / 'camview-before.json').write_text(json.dumps({
        'pid': pid, 'exe': os.readlink(f'/proc/{pid}/exe'),
        'cwd': os.readlink(f'/proc/{pid}/cwd'),
        'args': Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')[:-1]}))
    print('Closing camview through its Q key', flush=True)
    quit_viewer(pid)
    print('CAMVIEW_CLOSED', flush=True)
    bounded('tracking', [])
    bounded('no_tracking', ['--no-tracking'])
    bounded('rotation', ['--rotate-model', WB + ',' + ZEBRA])
    proc = start('controls', [])
    with (OUT / 'controls.jsonl').open('w') as samples:
        watch(proc, samples, 18, 'six-camera')
        for camera in range(1, 7):
            key(proc.pid, 'v')
            print(f'CONTROL camera={camera}', flush=True)
            watch(proc, samples, 7, f'camera-{camera}')
        key(proc.pid, 'v')
        watch(proc, samples, 8, 'six-camera-restored')
        key(proc.pid, 'p')
        print('CONTROL paused', flush=True)
        watch(proc, samples, 7, 'paused')
        key(proc.pid, 's')
        key(proc.pid, 'p')
        print('CONTROL resumed', flush=True)
        watch(proc, samples, 15, 'resumed')
        key(proc.pid, 's')
    if proc.poll() is not None:
        raise RuntimeError('Final detview exited during control acceptance')
    (OUT / 'kernel-after.log').write_text(command(['dmesg']))
    (OUT / 'final-pid').write_text(str(proc.pid))
    print(json.dumps({'event': 'acceptance-finished', 'running_pid': proc.pid}), flush=True)


if __name__ == '__main__':
    main()
