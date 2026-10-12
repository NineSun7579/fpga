#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_grab.py -- grab a small screenshot from the RK3568 X display over the debug
serial port (COM5 @1.5Mbaud) with md5-verified base64 streaming.

Board-side: qshot (Qt, scaled) -> PNG, ffmpeg -> small JPEG, base64 stream.
Small payload (tens of KB) is what makes the 1.5M CH340 link reliable.
"""
import base64, hashlib, os, sys, time
import serial

PORT, BAUD = 'COM5', 1500000
QSHOT = '/root/ov5640/qshot/qshot'
XV = 'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0'


def op():
    return serial.Serial(PORT, BAUD, timeout=0.2)


def run(s, cmd, tmo=60):
    s.reset_input_buffer()
    s.write((cmd + '; echo __EOC__\n').encode())
    s.flush()
    t0 = time.time()
    buf = b''
    while time.time() - t0 < tmo:
        c = s.read(65536)
        if c:
            buf += c
            if b'__EOC__' in buf:
                break
    s.reset_input_buffer()
    return buf.decode('utf-8', 'replace')


def stat(s, path):
    out = run(s, 'md5sum %s; wc -c < %s' % (path, path))
    md5 = None
    size = 0
    for ln in out.splitlines():
        p = ln.split()
        if len(p) == 2 and p[1] == path:
            md5 = p[0]
        t = ln.strip()
        if t.isdigit():
            size = int(t)
    return md5, size


def pull(s, path, local, tries=6):
    md5, size = stat(s, path)
    print('remote %s md5=%s size=%d' % (path, md5, size))
    if not md5 or size <= 0:
        return False
    tmo = max(30, size * 16 // 1024)
    for a in range(tries):
        s.reset_input_buffer()
        s.write(b'echo __SMS__; cat ' + path.encode() + b'; echo; echo __EMS__\n')
        s.flush()
        t0 = time.time()
        buf = b''
        while time.time() - t0 < tmo:
            c = s.read(65536)
            if c:
                buf += c
                if b'__EMS__' in buf:
                    break
        if b'__SMS__' not in buf or b'__EMS__' not in buf:
            print('  attempt %d: incomplete (%d bytes)' % (a, len(buf)))
            continue
        body = buf.split(b'__SMS__', 1)[1].split(b'__EMS__', 1)[0]
        b64 = bytes(ch for ch in body
                    if ch in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        got = hashlib.md5(b64).hexdigest()
        if got == md5:
            open(local, 'wb').write(base64.b64decode(b64))
            print('  OK attempt %d -> %s (%d bytes)' % (a, local, os.path.getsize(local)))
            return True
        print('  attempt %d: md5 mismatch (board=%s pc=%s, %d b64 chars)'
              % (a, md5[:8], got[:8], len(b64)))
        time.sleep(0.4)
    return False


def main():
    local = sys.argv[1] if len(sys.argv) > 1 else 'grab.png'
    width = sys.argv[2] if len(sys.argv) > 2 else '800'
    s = op()
    try:
        print(run(s, '%s %s /tmp/g.png %s 2>&1; ls -l /tmp/g.png' % (XV, QSHOT, width), 40))
        print(run(s, 'ffmpeg -loglevel error -y -i /tmp/g.png -q:v 4 /tmp/g.jpg 2>&1; '
                     'ls -l /tmp/g.jpg 2>&1', 60))
        # prefer JPEG; fall back to PNG if transcode failed
        if stat(s, '/tmp/g.jpg')[1] > 0:
            ok = pull(s, '/tmp/g.jpg', os.path.splitext(local)[0] + '.jpg')
        else:
            ok = pull(s, '/tmp/g.png', os.path.splitext(local)[0] + '.png')
        return 0 if ok else 1
    finally:
        s.close()


if __name__ == '__main__':
    sys.exit(main())
