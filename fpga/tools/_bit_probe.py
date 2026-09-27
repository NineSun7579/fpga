# -*- coding: utf-8 -*-
"""Dump cam3 twice (4 s apart) plus cam1 once, for bit-level corruption analysis.
Viewer must be stopped for the whole session."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def run(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "dump_cam3_frame.py"), "/tmp/dump_cam3_frame.py")
sftp.close()

print(run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 3; echo stopped")[0].strip())

for tag, base in (("c3a", "0x01000000"), ("c1a", "0x00800000"), ("c3b", "0x01000000"),
                  ("c1b", "0x00800000"), ("c3pa", "0x01200000"), ("c3pb", "0x01200000")):
    out, err = run("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm 2>&1" % (base, tag))
    print(tag, out.strip()[-60:] or err.strip()[-120:])
    time.sleep(3)

print(run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")[0].strip())

sftp = c.open_sftp()
for tag in ("c3a", "c3b", "c1a", "c1b", "c3pa", "c3pb"):
    sftp.get("/tmp/%s.ppm" % tag, os.path.join(ROOT, "%s_bit.ppm" % tag))
sftp.close()
c.close()
print("fetched")
