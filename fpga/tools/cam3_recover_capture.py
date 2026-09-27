# -*- coding: utf-8 -*-
"""Recover cam3's frame capture after the 54 MHz experiment stalled it.

Re-burns the verified bitstream (resets the capture FSM and re-runs the sensor
init), then rescans/insmods, verifies the counters, and restarts camview.
"""
import os
import subprocess
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk")
DEV = "/sys/bus/pci/devices/0002:21:00.0"
TCL = os.path.join(ROOT, "flash_verified_cam3.tcl")

VERIFY = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m
def P(*a):
    print(*a); sys.stdout.flush()
BASE = 0x20000400
d = m.PciDriver()
def rate(off):
    a = d.read32(BASE + off) & 0xFFFFFFFF
    time.sleep(1.0)
    b = d.read32(BASE + off) & 0xFFFFFFFF
    return (b - a) & 0xFFFFFFFF
P("cam3 PCLK=%d Hz (%.2f MHz)  VSYNCS/s=%d  FRAMES/s=%d" %
  (rate(0x10), rate(0x10) / 1e6, rate(0x20), rate(0xf0)))
d.close()
P("VERIFY DONE")
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
c.open_sftp()

print("=== 1. stop watchdog first, then camview; link down ===")
sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 3; "
      "ps -eo comm | grep -E '^camview$' && echo STILL-RUNNING || echo 'camview stopped'")
sh(c, "rmmod pango_pci_driver 2>/dev/null; sleep 2; "
      "test -e %s && echo 1 > %s/remove; sleep 2; "
      "(test -e %s && echo 'still present') || echo 'device removed'; "
      "lsmod | grep -i pango || echo 'module unloaded'" % (DEV, DEV, DEV))

print("=== 2. JTAG re-burn (fresh FPGA configure -> FSM reset + sensor init) ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-1200:], flush=True)
if "BURN OK" not in out:
    print("!! BURN FAILED")
    c.close()
    sys.exit(2)

print("=== 3. rescan + insmod ===")
sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; "
      "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 4; "
      "ls -l %s/driver 2>&1" % DEV)
sh(c, "dmesg | grep -i pango | tail -6")

print("=== 4. verify cam3 counters (single driver open) ===")
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_ver.py", "w") as f:
    f.write(VERIFY)
sh(c, "python3 -u /tmp/_ver.py 2>&1", t=120)

print("=== 5. restart camview + screenshot ===")
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 12; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
sh(c, "rm -f /tmp/rec1.png /tmp/rec2.png; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/rec1.png 900 >/dev/null 2>&1; "
      "sleep 3; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/rec2.png 900 >/dev/null 2>&1; "
      "ls -la /tmp/rec1.png /tmp/rec2.png")
for n in ("rec1", "rec2"):
    try:
        sftp.get("/tmp/%s.png" % n, os.path.join(OUT, "recovered_%s.png" % n))
        print("pulled recovered_%s.png" % n)
    except Exception as e:
        print("pull failed", n, e)
sftp.close()
c.close()
print("DONE")
