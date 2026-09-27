# -*- coding: utf-8 -*-
"""Recover the board and compare the three cameras' write-engine throughput.

Measures each camera's frame counter over a 4 s window using ONLY 2 register
reads (to avoid the host's own PCIe reads perturbing the DMA), then repeats.
Also does a burst-read test on cam3 to see whether host reads starve the DDR
write path, and finally restarts camview + grabs two screenshots.
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
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a); sys.stdout.flush()

B = {"cam1": 0x20000000, "cam2": 0x20000200, "cam3": 0x20000400}
STATE = {1: "IDLE", 2: "ADDR", 4: "DATA", 3: "ADDR_TAG", 5: "DATA_TAG", 6: "WAIT_TAG_DONE"}

d = m.PciDriver()
P("open ok")

def rd(a):
    return d.read32(a) & 0xFFFFFFFF

def frames(name, win=4):
    a = rd(B[name] + 0xf0)
    time.sleep(win)
    b = rd(B[name] + 0xf0)
    n = (b - a) & 0xFFFFFFFF
    P("  %s frames/%ds = %d  (%.1f/s)" % (name, win, n, n / float(win)))

P("--- pass 1 (minimal reads) ---")
for k in (1, 2, 3):
    frames("cam%d" % k)

P("--- pass 2 ---")
for k in (1, 2, 3):
    frames("cam%d" % k)

st = rd(B["cam3"] + 0x60)
P("cam3 +0x60=0x%08X state=%d/%s  +0xd0=0x%08X  +0x50=0x%08X"
  % (st, (st >> 16) & 7, STATE.get((st >> 16) & 7, "?"), rd(B["cam3"] + 0xd0), rd(B["cam3"] + 0x50)))

P("--- burst: 3000 register reads, then cam3 rate ---")
t0 = time.time()
for _ in range(3000):
    rd(B["cam3"] + 0x10)
P("   3000 reads took %.2fs" % (time.time() - t0))
for k in (3, 1, 2):
    frames("cam%d" % k)

P("--- pass 4 ---")
for k in (1, 2, 3):
    frames("cam%d" % k)

d.close()
P("BOARD DONE")
'''


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=200, show=True):
    full_cmd = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full_cmd, timeout=t)
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
sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 3; "
      "ps -eo comm | grep -E '^camview$' && echo STILL-RUNNING || echo 'camview stopped'")
sh(c, "rmmod pango_pci_driver 2>/dev/null; sleep 2; "
      "test -e %s && echo 1 > %s/remove; sleep 2; "
      "(test -e %s && echo 'still present') || echo 'device removed'" % (DEV, DEV, DEV))

print("=== JTAG configure ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-300:], flush=True)
if "BURN OK" not in out:
    print("!! BURN FAILED"); c.close(); sys.exit(2)

sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 4")

print("=== throughput comparison ===")
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_thr.py", "w") as f:
    f.write(BOARD)
sh(c, "python3 -u /tmp/_thr.py 2>&1", t=400)

print("=== restart camview + screenshots ===")
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 12; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
sh(c, "rm -f /tmp/th1.png /tmp/th2.png; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/th1.png 900 >/dev/null 2>&1; "
      "sleep 3; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/th2.png 900 >/dev/null 2>&1; "
      "ls -la /tmp/th1.png /tmp/th2.png")
for n in ("th1", "th2"):
    try:
        sftp.get("/tmp/%s.png" % n, os.path.join(OUT, "throughput_%s.png" % n))
        print("pulled throughput_%s.png" % n)
    except Exception as e:
        print("pull failed", n, e)
sftp.close()
c.close()
print("DONE")
