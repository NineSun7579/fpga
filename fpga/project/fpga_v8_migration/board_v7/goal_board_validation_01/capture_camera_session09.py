"""Collect two actual camera-viewer screenshots; collection is not a function PASS."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import time

TOOLS = Path(__file__).resolve().parents[3] / 'tools'
sys.path.insert(0, str(TOOLS))
from board_host import ssh_connect, board_host
from capture_rk3568_screen import convert_xwd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--mode', choices=('driving', 'six-camera'), default='driving')
    p.add_argument('--bit', type=Path, required=True)
    p.add_argument('--program-receipt', type=Path, required=True)
    p.add_argument('--viewer-log', required=True, help='Actual absolute RK camera-viewer log')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.pid <= 0 or not a.viewer_log.startswith('/'):
        p.error('Positive PID and absolute remote log required')
    inputs = {'bit': bound(a.bit), 'program_receipt': bound(a.program_receipt)}
    a.output.mkdir(parents=True, exist_ok=False)
    client = ssh_connect()
    sequence = 0

    def run(command):
        nonlocal sequence
        sequence += 1
        prefix = a.output / f'command_{sequence:02d}'
        start = datetime.now(timezone.utc).isoformat()
        prefix.with_suffix('.command.txt').write_text(command, encoding='utf-8')
        _, stdout, stderr = client.exec_command(command, timeout=30)
        output, errors = stdout.read(), stderr.read()
        rc = stdout.channel.recv_exit_status()
        prefix.with_suffix('.stdout').write_bytes(output)
        prefix.with_suffix('.stderr').write_bytes(errors)
        prefix.with_suffix('.json').write_text(json.dumps({
            'started_utc': start, 'ended_utc': datetime.now(timezone.utc).isoformat(),
            'rc': rc, 'stdout_sha256': hashlib.sha256(output).hexdigest(),
            'stderr_sha256': hashlib.sha256(errors).hexdigest()}, indent=2), encoding='utf-8')
        if rc:
            raise RuntimeError(f'RK command {sequence} failed, rc={rc}; see saved stderr')
        return output

    remote_source = '''import os,json,hashlib
from pathlib import Path
p=Path('/proc')/str(PID)
s=(p/'stat').read_text()
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
'exe':os.readlink(p/'exe'),'exe_sha256':hashlib.sha256((p/'exe').read_bytes()).hexdigest(),
'argv':(p/'cmdline').read_bytes().rstrip(b'\\0').split(b'\\0'),
'starttime':s.rsplit(')',1)[1].split()[19]},default=lambda b:b.decode('utf-8','replace')))
'''.replace('PID', str(a.pid))

    def identity():
        doc = json.loads(run('sudo -n python3 -c ' + shlex.quote(remote_source)))
        expected = '/userdata/detview-driving-demo/detview-driving-demo'
        argv = doc['argv']
        if doc['exe'] != expected or not argv or argv[0] != expected:
            raise RuntimeError('PID is not the actual driving-demo viewer')
        if any(x == '--video' or x.startswith('--video=') for x in argv):
            raise RuntimeError('Camera mode required; video playback is not camera evidence')
        if a.mode == 'driving' and '--driving-demo' not in argv:
            raise RuntimeError('Driving-demo mode required for driving capture')
        if a.mode == 'six-camera':
            if '--driving-demo' in argv or '--camera' in argv:
                raise RuntimeError('Six-camera overview required, without a selected camera or driving override')
            index = argv.index('--prefer-hdmifull') if '--prefer-hdmifull' in argv else -1
            if index < 0 or index + 1 >= len(argv) or argv[index + 1] != 'off':
                raise RuntimeError('Six-camera capture requires --prefer-hdmifull off')
        return doc

    x11 = 'sudo -n env DISPLAY=:0 XAUTHORITY=/home/linaro/.Xauthority '

    def viewer_window():
        clients = run(x11 + 'xprop -root _NET_CLIENT_LIST')
        windows = []
        for window in re.findall(rb'0x[0-9a-fA-F]+', clients):
            window = window.decode('ascii')
            owner = run(x11 + 'xprop -id ' + window + ' _NET_WM_PID')
            if re.search(rb'=\s*' + str(a.pid).encode('ascii') + rb'\s*$', owner):
                info = run(x11 + 'xwininfo -id ' + window)
                if b'Map State: IsViewable' in info:
                    windows.append(window)
        if len(windows) != 1:
            raise RuntimeError('Expected one visible X11 window owned by camera viewer')
        return windows[0]

    try:
        initial = identity()
        window = viewer_window()
        captures = []
        remote_dir = '/tmp/fpga_camera_capture_' + a.output.name
        # Quote even locally generated names; never interpolate arbitrary paths unquoted.
        run('mkdir -m 700 -- ' + shlex.quote(remote_dir))
        for number in (1, 2):
            if number == 2:
                time.sleep(10)
            before = identity()
            if before != initial:
                raise RuntimeError('Viewer or boot changed before screenshot')
            if viewer_window() != window:
                raise RuntimeError('Viewer window changed before screenshot')
            remote = remote_dir + f'/screen_{number}.xwd'
            run(x11 + 'xwd -id ' + window + ' -silent -out ' + shlex.quote(remote) +
                ' && sudo -n chmod 644 -- ' + shlex.quote(remote))
            xwd = a.output / f'screen_{number}.xwd'
            png = xwd.with_suffix('.png')
            with client.open_sftp() as transfer:
                transfer.get(remote, str(xwd))
            dimensions = convert_xwd(xwd, png)
            after = identity()
            if after != initial:
                raise RuntimeError('Viewer or boot changed during screenshot')
            if viewer_window() != window:
                raise RuntimeError('Viewer window changed during screenshot')
            log = run('sudo -n tail -n 1000 -- ' + shlex.quote(a.viewer_log))
            log_path = a.output / f'viewer_{number}.log'
            log_path.write_bytes(log)
            doc = {'captured_utc': datetime.now(timezone.utc).isoformat(),
                   'host': board_host(), 'viewer': after, 'viewer_window': window,
                   'capture_mode': a.mode, 'inputs': inputs,
                   'dimensions': dimensions, 'xwd': bound(xwd), 'png': bound(png),
                   'viewer_log': bound(log_path), 'functional_pass': False}
            xwd.with_suffix('.json').write_text(json.dumps(doc, indent=2), encoding='utf-8')
            captures.append(doc)
        run('sudo -n dmesg --color=never')
        (a.output / 'collection.json').write_text(json.dumps({
            'status': 'CAPTURED_REQUIRES_FRAME_AND_VISUAL_REVIEW',
            'captures': captures, 'functional_pass': False}, indent=2), encoding='utf-8')
        print(str(a.output.resolve()))
    finally:
        client.close()


if __name__ == '__main__':
    main()
