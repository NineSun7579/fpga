#!/usr/bin/env python3
"""push_detview.py -- push the detview package to the RK3568 board over serial
(COM9@1500000) using xfer_hex.py (FIQ-immune hex chunking), with md5 verify
and retries. Sources first, then lib, then models (priority order)."""
import subprocess, sys, os, re, time, hashlib

BASE = r'C:\Users\NineSun\Desktop\ov56401'
PKG = os.path.join(BASE, 'usb_deploy', 'detview')
XFER = os.path.join(BASE, 'xfer_hex.py')
SH = os.path.join(BASE, 'sh2.py')

# (local rel, board abs)
FILES = [
    ('main.cpp',            '/root/ov5640/detview/main.cpp'),
    ('frame_source.cpp',    '/root/ov5640/detview/frame_source.cpp'),
    ('frame_source.h',      '/root/ov5640/detview/frame_source.h'),
    ('pango_dev.h',         '/root/ov5640/detview/pango_dev.h'),
    ('preprocess.h',        '/root/ov5640/detview/preprocess.h'),
    ('yolo26_rknn.cpp',     '/root/ov5640/detview/yolo26_rknn.cpp'),
    ('yolo26_rknn.h',       '/root/ov5640/detview/yolo26_rknn.h'),
    ('detview.pro',         '/root/ov5640/detview/detview.pro'),
    ('include/rknn_api.h',  '/root/ov5640/detview/include/rknn_api.h'),
    ('lib/librknnrt.so',    '/root/ov5640/lib/librknnrt.so'),
    ('models/zebra_3cls_640_e2e.rknn',    '/root/ov5640/models/zebra_3cls_640_e2e.rknn'),
    ('models/zebra_3cls_640_std.rknn',    '/root/ov5640/models/zebra_3cls_640_std.rknn'),
    ('models/vehicles_1cls_640_e2e.rknn', '/root/ov5640/models/vehicles_1cls_640_e2e.rknn'),
    ('models/vehicles_1cls_640_std.rknn', '/root/ov5640/models/vehicles_1cls_640_std.rknn'),
]

def board(cmd, timeout=90):
    r = subprocess.run([sys.executable, SH, cmd], capture_output=True, timeout=timeout)
    return (r.stdout + r.stderr).decode('utf-8', 'replace')

def local_md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

def push(rel, dst, retries=3):
    src = os.path.join(PKG, rel)
    size = os.path.getsize(src)
    lm = local_md5(src)
    ddir = os.path.dirname(dst)
    board("mkdir -p %s" % ddir)
    for attempt in range(1, retries + 1):
        t0 = time.time()
        r = subprocess.run([sys.executable, XFER, src, dst],
                           capture_output=True, timeout=1800)
        out = (r.stdout + r.stderr).decode('utf-8', 'replace')
        m = re.findall(r'([0-9a-f]{32})\s+%s' % re.escape(dst), out)
        ok = bool(m) and m[-1] == lm
        print("  %s %s -> %s  (%.0fs) %s" % ('OK ' if ok else 'BAD', rel, dst,
                                             time.time() - t0,
                                             m[-1][:8] if m else out.strip()[-60:]),
              flush=True)
        if ok:
            return True
        time.sleep(3)
    return False

def main():
    # board prep: stop running apps, make dirs
    print(board("pkill -f camview; pkill -f detview; rm -f /tmp/camview.lock /tmp/detview.lock; "
                "mkdir -p /root/ov5640/detview/include /root/ov5640/models /root/ov5640/lib; echo PREP_DONE"),
          flush=True)
    fail = []
    for rel, dst in FILES:
        if not push(rel, dst):
            fail.append(rel)
    print("=== PUSH DONE, failed: %s ===" % (fail if fail else "none"), flush=True)

if __name__ == '__main__':
    main()
