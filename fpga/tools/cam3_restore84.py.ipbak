# -*- coding: utf-8 -*-
"""Restore cam3 to 84 MHz (0x3036=0x54), verify with the FPGA counter, then
restart camview and grab a screenshot."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "pclk")

BOARD = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a); sys.stdout.flush()

BASE = 0x20000400
d = m.PciDriver()
cam = m.CamI2c(d, BASE, verbose=False)

def rate(off):
    a = d.read32(BASE + off) & 0xFFFFFFFF
    time.sleep(1.0)
    b = d.read32(BASE + off) & 0xFFFFFFFF
    return (b - a) & 0xFFFFFFFF

P("before: PCLK=%d Hz (%.2f MHz)  FRAMES/s=%d" % (rate(0x10), rate(0x10) / 1e6, rate(0xf0)))

P("restore 0x3036=0x54 (84 MHz) ...")
cam.write(0x3035, 0x11); cam.write(0x3036, 0x54); cam.write(0x3037, 0x13)
time.sleep(1.5)

p = rate(0x10); f = rate(0xf0)
P("after : PCLK=%d Hz (%.2f MHz)  FRAMES/s=%d" % (p, p / 1e6, f))
d.close()
P("RESTORE DONE")
'''


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
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
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_restore.py", "w") as f:
    f.write(BOARD)
sh(c, "pkill -9 -x camview 2>/dev/null; pkill -9 -x run_camview.sh 2>/dev/null; sleep 2")
sh(c, "python3 -u /tmp/_restore.py 2>&1")

print("=== restart camview ===")
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 10; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
sh(c, "rm -f /tmp/abshot.png; DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
      "/root/ov5640/qshot/qshot /tmp/abshot.png 900 >/dev/null 2>&1; ls -la /tmp/abshot.png")
try:
    sftp.get("/tmp/abshot.png", os.path.join(OUT, "after_restore_84.png"))
    print("pulled after_restore_84.png")
except Exception as e:
    print("screenshot pull failed:", e)
sftp.close()
c.close()
print("DONE")
