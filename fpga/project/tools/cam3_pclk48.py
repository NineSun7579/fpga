# -*- coding: utf-8 -*-
"""Clean cam3 PCLK 48 MHz test (no rebuild).

Runtime PLL change normally wedges the DDR write engine (engine_busy sticks, so
IDLEGATE just drops every frame -> FRAMES collapses).  To change PCLK cleanly we
gate frame admission off first:

    CAM_EN=0 (drain the engine) -> write 0x3036=0x30 -> CAM_EN=1

Then measure PCLK/VSYNC/FRAMES and dump frames, restore to 84 MHz, and confirm
recovery.  A fresh JTAG config is done first for a deterministic starting state.
"""
import os
import subprocess
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk48")
DEV = "/sys/bus/pci/devices/0002:21:00.0"
TCL = os.path.join(ROOT, "flash_verified_cam3.tcl")

BOARD = r'''
import sys, time, fcntl, signal, struct
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a); sys.stdout.flush()

BASE = 0x20000400
CAM_EN = 0x20000440
PING = 0x01000000
W, H = 640, 480
F2H = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

d = m.PciDriver()
P("open+map+mmap ok")
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

P("=== baseline (84 MHz) ===")
phase("base ")
dump(PING, "/tmp/p48_base_a.ppm"); time.sleep(0.7)
dump(PING, "/tmp/p48_base_b.ppm")

P("=== CAM_EN=0 (drain write engine) ===")
d.write32(CAM_EN, 0); time.sleep(0.8)

P("=== set 0x3035=0x11, 0x3036=0x30, 0x3037=0x13  -> 48 MHz ===")
cam.write(0x3035, 0x11); cam.write(0x3036, 0x30); cam.write(0x3037, 0x13)
time.sleep(1.5)

P("=== CAM_EN=1 ===")
d.write32(CAM_EN, 1); time.sleep(2.0)
phase("48M  ")
dump(PING, "/tmp/p48_48_a.ppm"); time.sleep(0.7)
dump(PING, "/tmp/p48_48_b.ppm")

P("=== restore to 84 MHz ===")
d.write32(CAM_EN, 0); time.sleep(0.8)
cam.write(0x3035, 0x11); cam.write(0x3036, 0x54); cam.write(0x3037, 0x13)
time.sleep(1.5)
d.write32(CAM_EN, 1); time.sleep(2.0)
phase("rest ")
dump(PING, "/tmp/p48_rest_a.ppm")
d.close()
P("BOARD DONE")
'''


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=200, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd, flush=True)
        if out.strip():
            print(out.rstrip(), flush=True)
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300], flush=True)
    return out


os.makedirs(OUT, exist_ok=True)
c = connect()

print("=== 1. stop watchdog then camview; link down ===")
sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 3; "
      "ps -eo comm | grep -E '^camview$' && echo STILL-RUNNING || echo 'camview stopped'")
sh(c, "rmmod pango_pci_driver 2>/dev/null; sleep 2; "
      "test -e %s && echo 1 > %s/remove; sleep 2; "
      "(test -e %s && echo 'still present') || echo 'device removed'" % (DEV, DEV, DEV))

print("=== 2. JTAG configure (deterministic start) ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-800:], flush=True)
if "BURN OK" not in out:
    print("!! BURN FAILED")
    c.close()
    sys.exit(2)

print("=== 3. rescan + insmod ===")
sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; "
      "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 4; "
      "ls -l %s/driver 2>&1" % DEV)
sh(c, "dmesg | grep -i pango | tail -4")

print("=== 4. 48 MHz test (single driver open) ===")
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_p48.py", "w") as f:
    f.write(BOARD)
sh(c, "python3 -u /tmp/_p48.py 2>&1", t=400)
for n in ("p48_base_a", "p48_base_b", "p48_48_a", "p48_48_b", "p48_rest_a"):
    try:
        sftp.get("/tmp/%s.ppm" % n, os.path.join(OUT, "%s.ppm" % n))
        print("pulled", n)
    except Exception as e:
        print("pull failed", n, e)
sftp.close()

print("=== 5. restart camview ===")
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 10; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
c.close()
print("DONE")
