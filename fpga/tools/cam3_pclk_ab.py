# -*- coding: utf-8 -*-
"""A/B: cam3 at 84 MHz vs 54 MHz (runtime SCCB PLL change, no rebuild).

Leaves cam3 at 54 MHz (0x3036=0x36) so a screenshot can be taken; run with
--restore to put it back to 84 MHz (0x3036=0x54).
"""
import argparse
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

BASE = 0x20000400
PING = 0x01000000
PONG = 0x01200000
W, H = 640, 480
F2H = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

RESTORE = __RESTORE__          # 1 = put 0x3036 back to 0x54 at the end

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
    p = rate(0x10)
    v = rate(0x20)
    f = rate(0xf0)
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

if RESTORE:
    print("=== restore 0x3036=0x54 -> 84 MHz ===")
    cam.write(0x3035, 0x11); cam.write(0x3036, 0x54); cam.write(0x3037, 0x13)
    time.sleep(1.0)
    phase("restored")

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
            print("ERR:", err.rstrip()[:400])
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--restore", action="store_true")
args = ap.parse_args()

os.makedirs(OUT, exist_ok=True)
c = connect()
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_pclk_ab.py", "w") as f:
    f.write(BOARD.replace("__RESTORE__", "1" if args.restore else "0"))

sh(c, "killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 6; echo stopped")
out = sh(c, "python3 /tmp/_pclk_ab.py 2>&1")
if "BOARD DONE" not in out:
    print(">> first attempt failed, waiting 8s and retrying ...")
    sh(c, "sleep 8")
    out = sh(c, "python3 /tmp/_pclk_ab.py 2>&1")

# pull the dumps
for name in ("pclk84_a", "pclk84_b", "pclk84_pong", "pclk54_a", "pclk54_b", "pclk54_pong"):
    try:
        sftp.get("/tmp/%s.ppm" % name, os.path.join(OUT, "%s.ppm" % name))
        print("pulled", name)
    except Exception as e:
        print("pull failed", name, e)
sftp.close()

sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
   "> /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")
c.close()
print("DONE")
