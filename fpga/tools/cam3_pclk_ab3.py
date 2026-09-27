# -*- coding: utf-8 -*-
"""cam3 PCLK A/B run with unbuffered, granular progress prints to locate any
crash.  Assumes the driver is loaded and camview is NOT running."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk")

BOARD = r'''
import sys, time, fcntl
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a)
    sys.stdout.flush()

BASE = 0x20000400
PING = 0x01000000
PONG = 0x01200000
W, H = 640, 480
F2H = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

P("A import ok")
d = m.PciDriver()
P("B driver open+map+mmap ok")
cam = m.CamI2c(d, BASE, verbose=False)
P("C read32 pclk =", d.read32(BASE + 0x10))

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
    P("   dump", out, "from 0x%08X" % base)
    for off in range(0, W * H * 2, CH):
        img += rd(base + off, CH)
    P("   read", len(img), "bytes; converting")
    ppm = bytearray(b"P6\n%d %d\n255\n" % (W, H))
    for i in range(W * H):
        v = img[2 * i] | (img[2 * i + 1] << 8)
        ppm += bytes((((v >> 11) & 0x1F) << 3, ((v >> 5) & 0x3F) << 2, (v & 0x1F) << 3))
    open(out, "wb").write(ppm)
    P("   wrote", out, len(ppm))

def phase(tag):
    p = rate(0x10); v = rate(0x20); f = rate(0xf0)
    P("%s  PCLK=%d Hz (%.2f MHz)  VSYNCS/s=%d  FRAMES/s=%d" % (tag, p, p / 1e6, v, f))

P("=== 84 MHz baseline ===")
phase("before")
dump(PING, "/tmp/pclk84_a.ppm")
time.sleep(0.7)
dump(PING, "/tmp/pclk84_b.ppm")
dump(PONG, "/tmp/pclk84_pong.ppm")

P("=== set 0x3036=0x36 -> 54 MHz ===")
cam.write(0x3035, 0x11); cam.write(0x3036, 0x36); cam.write(0x3037, 0x13)
time.sleep(1.0)
phase("after ")
dump(PING, "/tmp/pclk54_a.ppm")
time.sleep(0.7)
dump(PING, "/tmp/pclk54_b.ppm")
dump(PONG, "/tmp/pclk54_pong.ppm")
d.close()
P("BOARD DONE")
'''


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=300, show=True):
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
with sftp.open("/tmp/_ab3.py", "w") as f:
    f.write(BOARD)

sh(c, "pkill -9 -x camview 2>/dev/null; pkill -9 -x run_camview.sh 2>/dev/null; sleep 2; "
   "ps -eo comm | grep -E '^camview$' && echo STILL-RUNNING || echo 'camview not running'")
print("=== A/B (python3 -u) ===")
sh(c, "python3 -u /tmp/_ab3.py 2>&1")
for name in ("pclk84_a", "pclk84_b", "pclk84_pong", "pclk54_a", "pclk54_b", "pclk54_pong"):
    try:
        sftp.get("/tmp/%s.ppm" % name, os.path.join(OUT, "%s.ppm" % name))
        print("pulled", name)
    except Exception as e:
        print("pull failed", name, e)
sftp.close()
c.close()
print("DONE")
