#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shot_pull.py : RK3568 X11 screenshot puller over COM9 (FMC dualcam bring-up)

Usage:
    python shot_pull.py N [prefix]   # capture N screenshots, interval ~2.5s,
                                     # save prefix_0.png..prefix_{N-1}.png

Board side: xwd -root | gzip | base64, streamed raw over the console tty
(~150 KB/s at 1.5 Mbaud). PC side: gunzip -> parse XWD -> PNG (Pillow).
"""
import sys, os, time, base64, gzip, io, struct, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from push_dualcam import open_port, board_ready, sh

XENV = 'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0'


def capture_b64(s):
    sh(s, f'{XENV} xwd -root -silent | gzip -1 | base64 -w0 > /tmp/shot.b64', 30)
    out = sh(s, 'wc -c < /tmp/shot.b64; md5sum /tmp/shot.b64', 15)
    size = 0
    for ln in out.splitlines():
        if ln.strip().isdigit():
            size = int(ln.strip()); break
    if size <= 0:
        raise RuntimeError('board screenshot empty: %r' % out[:200])
    # raw stream read: cat with start/end markers
    s.reset_input_buffer()
    s.write(b'echo __SMS__; cat /tmp/shot.b64; echo; echo __EMS__\n'); s.flush()
    tmo = max(20, size * 12 // 1024)  # ~12s/MB, generous
    t0 = time.time(); buf = b''
    while time.time() - t0 < tmo:
        c = s.read(65536)
        if c:
            buf += c
            if b'__EMS__' in buf:
                break
    if b'__SMS__' not in buf or b'__EMS__' not in buf:
        raise RuntimeError('stream incomplete: got %d bytes in %ds' % (len(buf), time.time() - t0))
    body = buf.split(b'__SMS__')[1].split(b'__EMS__')[0]
    b64 = bytes(ch for ch in body if ch in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
    md5 = ''
    for ln in out.splitlines():
        if len(ln.split()) == 2 and ln.split()[1] == '/tmp/shot.b64':
            md5 = ln.split()[0]
    got = hashlib.md5(b64).hexdigest()
    if md5 and got != md5:
        raise RuntimeError('b64 md5 mismatch board=%s pc=%s' % (md5, got))
    return b64


def xwd_to_png(raw):
    """Parse XWD (big-endian header) -> PIL Image."""
    from PIL import Image
    (hsize, _ver, fmt, depth, w, h, xoff, byte_order, _bu, _bbo, _bp,
     bpp, bpl, _vclass, rmask, gmask, bmask) = struct.unpack('>17I', raw[:68])
    ncolors = struct.unpack('>I', raw[76:80])[0]
    off = hsize + ncolors * 12
    if fmt != 2:
        raise RuntimeError('unsupported pixmap format %d' % fmt)
    if bpp == 32:
        px = bytearray(w * h * 3)
        ro = (rmask >> 24) & 0xFF if byte_order == 0 else ((rmask & 0xFF) != 0) * 0 + {0xFF000000: 3, 0xFF0000: 2, 0xFF00: 1}.get(rmask if byte_order else rmask, 2)
        # generic: derive per-color byte index from masks + byte order
        def idx(mask):
            shift = 0
            while mask and not (mask & 0xFF):
                mask >>= 8; shift += 1
            return shift
        ri, gi, bi = idx(rmask), idx(gmask), idx(bmask)
        for y in range(h):
            row = raw[off + y * bpl: off + (y + 1) * bpl]
            po = y * w * 3
            for x in range(w):
                o = x * 4
                px[po + x * 3]     = row[o + ri]
                px[po + x * 3 + 1] = row[o + gi]
                px[po + x * 3 + 2] = row[o + bi]
    elif bpp == 24:
        px = bytearray(w * h * 3)
        for y in range(h):
            row = raw[off + y * bpl: off + (y + 1) * bpl]
            po = y * w * 3
            px[po:po + w * 3] = row[:w * 3]
    else:
        raise RuntimeError('unsupported bpp %d' % bpp)
    return Image.frombytes('RGB', (w, h), bytes(px))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    prefix = sys.argv[2] if len(sys.argv) > 2 else 'shot'
    here = os.path.dirname(os.path.abspath(__file__))
    s = open_port()
    try:
        if not board_ready(s):
            raise SystemExit('board not responding')
        for i in range(n):
            b64 = None
            for attempt in range(3):           # serial streams can corrupt; retry
                try:
                    b64 = capture_b64(s)
                    break
                except RuntimeError as e:
                    print('attempt %d failed: %s' % (attempt, e))
                    import time as _t; _t.sleep(1)
            if b64 is None:
                raise RuntimeError('capture failed after retries')
            raw = gzip.decompress(base64.b64decode(b64))
            img = xwd_to_png(raw)
            out = os.path.join(here, '%s_%d.png' % (prefix, i))
            img.save(out, 'PNG')
            print('saved %s  %dx%d  (%d KB gz)' % (out, img.width, img.height, len(b64) * 3 // 4 // 1024))
            if i < n - 1:
                time.sleep(2.5)
    finally:
        s.close()


if __name__ == '__main__':
    main()
