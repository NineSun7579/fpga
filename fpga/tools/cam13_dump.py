# -*- coding: utf-8 -*-
"""Dump cam1 / cam2 / cam3 frames (normal mode) for side-by-side comparison."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "cmp")
os.makedirs(OUT, exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)


def sh(cmd, t=300, show=False):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$", cmd)
        print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


sftp = c.open_sftp()
for f in ("cam3_i2c_pt.py", "dump_cam3_frame.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()

names = []
sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped", show=True)
try:
    for nm, base in (("c1_1", "0x00800000"), ("c1_2", "0x00800000"),
                     ("c2_1", "0x00A00000"),
                     ("c3_1", "0x01000000"), ("c3_2", "0x01000000")):
        sh("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm >/dev/null 2>&1" % (base, nm))
        names.append(nm)
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1", show=True)
    time.sleep(1.0)
    sh("python3 /tmp/dump_cam3_frame.py 0x01000000 /tmp/c3_bar.ppm >/dev/null 2>&1")
    names.append("c3_bar")
finally:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted", show=True)

sftp = c.open_sftp()
for nm in names:
    try:
        sftp.get("/tmp/%s.ppm" % nm, os.path.join(OUT, nm + ".ppm"))
        print("got", nm)
    except Exception as e:  # noqa: BLE001
        print("dl fail", nm, e)
sftp.close()
c.close()
print("DONE")
