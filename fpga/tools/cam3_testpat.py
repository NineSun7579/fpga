# -*- coding: utf-8 -*-
"""Orchestrate the cam3 test-pattern (colour bar) experiment from the host.

Sequence:
  1. upload cam3_i2c_pt.py / dump_cam3_frame.py to the board
  2. stop camview (frees /dev/pango_pci_driver)
  3. enable cam3 test pattern (0x503D = 0x80) and read it back
  4. dump cam3 ping (0x01000000) and pong (0x01200000) twice each
  5. disable test pattern (0x503D = 0x00)
  6. restart camview
  7. download the PPMs
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
LOCAL_OUT = os.path.join(ROOT, "tp")

os.makedirs(LOCAL_OUT, exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def run(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    return out, err


def sh(cmd, t=180):
    out, err = run(cmd, t)
    print("$", cmd)
    if out.strip():
        print(out.rstrip())
    if err.strip() and "password for" not in err:
        print("ERR:", err.rstrip()[:400])
    return out


sftp = c.open_sftp()
for f in ("cam3_i2c_pt.py", "dump_cam3_frame.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()
print("uploaded tools")

# 1. stop viewer
sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; "
   "pgrep -af camview | head -3; echo STOPPED")

# 2. enable test pattern + read back
sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1")
sh("python3 /tmp/cam3_i2c_pt.py --quiet rd 0x503d 2>&1")

# 3. dump ping/pong twice each (a/b back to back, then again after 3 s)
dumps = [
    ("c3tp_ping_a", 0x01000000, 0),
    ("c3tp_ping_b", 0x01000000, 0),
    ("c3tp_pong_a", 0x01200000, 0),
    ("c3tp_pong_b", 0x01200000, 0),
    ("c3tp_ping_c", 0x01000000, 3),
    ("c3tp_pong_c", 0x01200000, 3),
]
for name, base, delay in dumps:
    if delay:
        time.sleep(delay)
    sh("python3 /tmp/dump_cam3_frame.py 0x%08X /tmp/%s.ppm 2>&1" % (base, name))

# also a live-viewer-independent register snapshot
sh("python3 /tmp/board_peek.py 0x20000410 0x20000420 0x200004A0 0x200004F0 2>&1 || true")

# 4. restore test pattern off
sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
sh("python3 /tmp/cam3_i2c_pt.py --quiet rd 0x503d 2>&1")

# 5. restart viewer
sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & "
   "sleep 2; echo RESTARTED")

# 6. download
sftp = c.open_sftp()
for name, _b, _d in dumps:
    rp = "/tmp/%s.ppm" % name
    lp = os.path.join(LOCAL_OUT, "%s.ppm" % name)
    try:
        sftp.get(rp, lp)
        print("downloaded", lp, os.path.getsize(lp))
    except Exception as e:
        print("download FAIL", name, e)
sftp.close()
c.close()
print("DONE")
