# -*- coding: utf-8 -*-
"""Runtime PCLK retarget test for cam3 (no rebuild).

cam3's sensor PLL is currently 0x3035=0x11 / 0x3036=0x54 / 0x3037=0x13,
which measures 84 MHz (PCLK[HZ] ~= 0x3036 decimal).  Write 0x3036=0x36 to
try 54 MHz, then measure with the FPGA's own PCLK counter so we know it took.

Restores nothing by itself - run with --restore to put 0x3036 back to 0x54.
"""
import argparse
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

REMOTE = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

BASE = 0x20000400
TARGET = %d          # 0x36 = 54 MHz, 0x54 = 84 MHz (restore)

d = m.PciDriver()

def rate(off):
    a = d.read32(BASE + off) & 0xFFFFFFFF
    time.sleep(1.0)
    b = d.read32(BASE + off) & 0xFFFFFFFF
    return (b - a) & 0xFFFFFFFF

cam = m.CamI2c(d, BASE, verbose=False)
p0 = rate(0x10)
print("PCLK before = %d Hz (%.2f MHz)" % (p0, p0 / 1e6))
cam.write(0x3035, 0x11)
cam.write(0x3036, TARGET)
cam.write(0x3037, 0x13)
time.sleep(0.5)
p1 = rate(0x10)
print("PCLK after  = %d Hz (%.2f MHz)" % (p1, p1 / 1e6))
print("VSYNCS/s    = %d" % rate(0x20))
print("FRAMES/s    = %d" % rate(0xf0))
d.close()
'''


def sh(cmd, t=180, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--restore", action="store_true")
args = ap.parse_args()
target = 0x54 if args.restore else 0x36

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_pclk54.py", "w") as f:
    f.write(REMOTE % target)
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 5; echo stopped")
try:
    out = sh("python3 /tmp/_pclk54.py 2>&1")
    if ("EBUSY" in out) or ("Timeout" in out) or ("Traceback" in out):
        print(">> driver busy, reloading ...")
        sh("rmmod pango_pci_driver 2>/dev/null; echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove; "
           "sleep 2; echo 1 > /sys/bus/pci/rescan; sleep 4; "
           "insmod /root/ov5640/pango_pci_driver.ko && echo driver-ok", t=120)
        sh("python3 /tmp/_pclk54.py 2>&1")
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
print("DONE target=0x%02X" % target)
