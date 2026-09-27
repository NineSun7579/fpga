# -*- coding: utf-8 -*-
"""Reboot -> settle -> insmod -> granular probe of the 32-bit read path, then
the PCLK A/B, all inside ONE process (single driver open).

The granular probe pinpoints whether the F2H ioctl itself or the mmap access
segfaults.
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk")

BOARD = r'''
import sys, time, fcntl, signal, struct
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a); sys.stdout.flush()

P("import ok")
d = m.PciDriver()
P("open+map+mmap ok")

P("probe: build op")
op = m.DmaOp(); op.offset_addr = 0; op.ddr3_addr = 0x20000410; op.total_length = 16
P("probe: ioctl F2H ...")
signal.alarm(8)
try:
    r = fcntl.ioctl(d.fd, m.F2H_CMD, op, True)
finally:
    signal.alarm(0)
P("probe: ioctl returned", r)
b = bytes(d.rx[0:4])
P("probe: rx[0:4] =", b.hex())
P("probe: unpack =", struct.unpack("<I", b)[0])
P("PROBE DONE")

BASE = 0x20000400
PING = 0x01000000
PONG = 0x01200000
W, H = 640, 480
F2H = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

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
        ppm += bytes((((v >> 11) & 0x1F) << 3, ((v >> 5) & 0x3F) << 2, (v & 0x1F) << 3))
    open(out, "wb").write(ppm)
    P("   wrote", out, len(ppm))

def phase(tag):
    p = rate(0x10); v = rate(0x20); f = rate(0xf0)
    P("%s  PCLK=%d Hz (%.2f MHz)  VSYNCS/s=%d  FRAMES/s=%d" % (tag, p, p / 1e6, v, f))

P("=== 84 MHz baseline ===")
phase("before")
dump(PING, "/tmp/pclk84_a.ppm"); time.sleep(0.7)
dump(PING, "/tmp/pclk84_b.ppm")
dump(PONG, "/tmp/pclk84_pong.ppm")

P("=== set 0x3036=0x36 -> 54 MHz ===")
cam.write(0x3035, 0x11); cam.write(0x3036, 0x36); cam.write(0x3037, 0x13)
time.sleep(1.0)
phase("after ")
dump(PING, "/tmp/pclk54_a.ppm"); time.sleep(0.7)
dump(PING, "/tmp/pclk54_b.ppm")
dump(PONG, "/tmp/pclk54_pong.ppm")
d.close()
P("BOARD DONE")
'''


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=300, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd)
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


os.makedirs(OUT, exist_ok=True)
c = connect()
sh(c, "sync; (sleep 1; reboot) > /dev/null 2>&1 & echo reboot-issued")
try:
    c.close()
except Exception:
    pass

print("=== waiting for the board ===")
c = None
for i in range(40):
    time.sleep(6)
    try:
        c = connect(timeout=8)
        print("back after ~%ds" % ((i + 1) * 6))
        break
    except Exception:
        pass
if c is None:
    print("!! board did not come back")
    sys.exit(1)

print("=== settle 60s (let the FPGA/PCIe come fully ready) ===")
time.sleep(60)
sh(c, "uptime | head -1; lspci | grep -i 21:00 || echo 'no device'")

print("=== fresh probe: remove device -> rescan -> insmod ===")
sh(c, "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 2; "
   "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
   "echo 1 > /sys/bus/pci/rescan 2>/dev/null; sleep 4; "
   "insmod /root/ov5640/pango_pci_driver.ko && echo insmod-ok; sleep 2; "
   "lsmod | grep -i pango; ls -l /dev/pango_pci_driver", t=120)
sh(c, "dmesg | grep -i pango | tail -15 || echo 'no pango dmesg'")

sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_probe.py", "w") as f:
    f.write(BOARD)

print("=== probe + A/B (single driver open) ===")
sh(c, "python3 -u /tmp/_probe.py 2>&1", t=300)
sh(c, "dmesg | grep -i pango | tail -15 || echo 'no pango dmesg'")
for name in ("pclk84_a", "pclk84_b", "pclk84_pong", "pclk54_a", "pclk54_b", "pclk54_pong"):
    try:
        sftp.get("/tmp/%s.ppm" % name, os.path.join(OUT, "%s.ppm" % name))
        print("pulled", name)
    except Exception as e:
        print("pull failed", name, e)
sftp.close()
c.close()
print("DONE")
