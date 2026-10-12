# -*- coding: utf-8 -*-
"""Read the three cameras' debug counters (PCLK, VSYNC, frames) to compare clocks.

Read-only.  Bases 0x2000_0000 / 0x2000_0200 / 0x2000_0400; counters:
    +0x10 DBG_PCLK_CNT, +0x20 DBG_VSYNCS, +0xf0 DBG_BEAT_LAST (frames)
Runs on the board via SSH.
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

REMOTE = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m
d = m.PciDriver()
bases = [("cam1", 0x20000000), ("cam2", 0x20000200), ("cam3", 0x20000400)]
offs = [0x10, 0x20, 0xf0, 0x90, 0xe0]
# snapshot 1
s1 = {}
for name, b in bases:
    for o in offs:
        try: s1[(name, o)] = d.read32(b + o)
        except Exception as e: s1[(name, o)] = -1
time.sleep(1.0)
s2 = {}
for name, b in bases:
    for o in offs:
        try: s2[(name, o)] = d.read32(b + o)
        except Exception as e: s2[(name, o)] = -1
lbl = {0x10: "PCLK_CNT", 0x20: "VSYNCS", 0xf0: "FRAMES", 0x90: "HREF_RAW", 0xe0: "VSYNC_RAW"}
for name, b in bases:
    print("== %s (base 0x%08X)" % (name, b))
    for o in offs:
        a = s1[(name, o)] & 0xFFFFFFFF
        c = s2[(name, o)] & 0xFFFFFFFF
        dlt = (c - a) & 0xFFFFFFFF
        print("   +0x%02X %-9s = 0x%08X (0x%08X)  delta/s = %d" % (o, lbl[o], c, a, dlt))
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


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_dbg.py", "w") as f:
    f.write(REMOTE)
sftp.close()
sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
sh("rmmod pango_pci_driver 2>/dev/null; echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove; "
   "sleep 2; echo 1 > /sys/bus/pci/rescan; sleep 4; "
   "insmod /root/ov5640/pango_pci_driver.ko && echo driver-ok", t=120)
try:
    sh("python3 /tmp/_dbg.py 2>&1")
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
print("DONE")
