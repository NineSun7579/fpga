# -*- coding: utf-8 -*-
"""Is the DDR frame content actually advancing? Stop viewer, dump cam1/cam2/cam3
ping buffers twice ~4 s apart, compare. Restart viewer afterwards."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
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

BASES = {"c1": "0x00800000", "c2": "0x00C00000", "c3": "0x01000000"}
for tag in ("x", "y"):
    for name, base in BASES.items():
        out, err = run("python3 /tmp/dump_cam3_frame.py %s /tmp/%s%s.ppm 2>&1" % (base, name, tag))
        print("%s%s %s" % (name, tag, out.strip()[-60:]))
    time.sleep(4)

print(run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")[0].strip())

sftp = c.open_sftp()
for name in BASES:
    for tag in ("x", "y"):
        sftp.get("/tmp/%s%s.ppm" % (name, tag), os.path.join(ROOT, "%s%s_adv.ppm" % (name, tag)))
sftp.close()
c.close()
print("fetched")
