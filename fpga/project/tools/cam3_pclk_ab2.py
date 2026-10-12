# -*- coding: utf-8 -*-
"""cam3 PCLK A/B (84 vs 54 MHz), with a MAP-ioctl gate first.

Assumes the board was just rebooted and the driver insmod'ed with NO camview
running.  Leaves cam3 at 54 MHz and leaves camview STOPPED.
"""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk")

MAPTEST = r'''
import fcntl, os, signal, ctypes
class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]
def I(n): return 0xC0000000 | (4 << 16) | (0x53 << 8) | n
class TO(Exception): pass
def al(s, f): raise TO()
signal.signal(signal.SIGALRM, al)
fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
try:
    for c in (0, 1):
        o = O(); o.cmd = c; o.ln = 4194304
        signal.alarm(6)
        try:
            fcntl.ioctl(fd, I(2), o, True); print('MAP', c, 'ok')
        finally:
            signal.alarm(0)
finally:
    os.close(fd)
print('MAPTEST DONE')
'''

BOARD = r'''
import sys, time, fcntl
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

BASE = 0x20000400
PING = 0x01000000
PONG = 0x01200000
W, H = 640, 480
F2H = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

d = m.PciDriver()
cam = m.CamI2c(d, BASE, verbose=False)

def rate(off):
    a = d.read32(BASE + off) & 0xFFFFFFFF
    time.sleep(1.0)
    b = d.read32(BASE + off) & 0xFFFFFFFF
    return (b - a) & 0xFFFFFFFF

def rd(a, n):
    op = m.DmaOp(); op.offset_addr = 0; op.ddr3_addr = a; op.total_length = n
    fcntl.ioctl(d.fd, F2H, op, True)
    return bytes(d.rx[0:n])

def dump(base, out):
    img = bytearray(); CH = W * 2 * 64
    for off in range(0, W * H * 2, CH):
        img += rd(base + off, CH)
    ppm = bytearray(b"P6\n%d %d\n255\n" % (W, H))
    for i in range(W * H):
        v = img[2 * i] | (img[2 * i + 1] << 8)
        r = ((v >> 11) & 0x1F) << 3
        g = ((v >> 5) & 0x3F) << 2
        b = (v & 0x1F) << 3
        ppm += bytes((r, g, b))
    open(out, "wb").write(ppm)
    print("wrote", out, len(ppm))

def phase(tag):
    p = rate(0x10); v = rate(0x20); f = rate(0xf0)
    print("%s  PCLK=%d Hz (%.2f MHz)  VSYNCS/s=%d  FRAMES/s=%d" % (tag, p, p / 1e6, v, f))

print("=== 84 MHz (baseline) ===")
phase("before")
dump(PING, "/tmp/pclk84_a.ppm")
time.sleep(0.7)
dump(PING, "/tmp/pclk84_b.ppm")
dump(PONG, "/tmp/pclk84_pong.ppm")

print("=== set 0x3036=0x36 -> 54 MHz ===")
cam.write(0x3035, 0x11); cam.write(0x3036, 0x36); cam.write(0x3037, 0x13)
time.sleep(1.0)
phase("after ")
dump(PING, "/tmp/pclk54_a.ppm")
time.sleep(0.7)
dump(PING, "/tmp/pclk54_b.ppm")
dump(PONG, "/tmp/pclk54_pong.ppm")
d.close()
print("BOARD DONE")
'''


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=240, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


os.makedirs(OUT, exist_ok=True)
c = connect()
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_maptest.py", "w") as f:
    f.write(MAPTEST)
with sftp.open("/tmp/_pclk_ab.py", "w") as f:
    f.write(BOARD)

print("=== stop any camview (exact-name match, safe) ===")
sh(c, "pkill -9 -x camview 2>/dev/null; pkill -9 -x run_camview.sh 2>/dev/null; sleep 3; "
   "ps -eo comm | grep -E '^camview$' && echo 'STILL RUNNING' || echo 'camview not running'; "
   "fuser /dev/pango_pci_driver 2>&1 || echo 'driver free'")

print("=== MAP gate ===")
out = sh(c, "python3 /tmp/_maptest.py 2>&1")
if "MAPTEST DONE" not in out:
    print("!! MAP still failing - aborting before any A/B work")
else:
    print("=== A/B ===")
    sh(c, "python3 /tmp/_pclk_ab.py 2>&1", t=300)
    for name in ("pclk84_a", "pclk84_b", "pclk84_pong", "pclk54_a", "pclk54_b", "pclk54_pong"):
        try:
            sftp.get("/tmp/%s.ppm" % name, os.path.join(OUT, "%s.ppm" % name))
            print("pulled", name)
        except Exception as e:
            print("pull failed", name, e)

sftp.close()
c.close()
print("DONE (camview left stopped; cam3 left at 54 MHz if the A/B ran)")
