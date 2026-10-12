# -*- coding: utf-8 -*-
"""Re-dump cam3 full frames (test pattern) + normal-mode frames to settle the shift."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "rc")
os.makedirs(OUT, exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)


def sh(cmd, t=300, show=True):
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
sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
try:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1")
    time.sleep(1.0)
    for nm, base in (("rc_bar_1", "0x01000000"), ("rc_bar_2", "0x01000000"),
                     ("rc_bar_3", "0x01000000"), ("rc_bar_pong", "0x01200000")):
        sh("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm >/dev/null 2>&1" % (base, nm), show=False)
        names.append(nm)
        print("   dumped", nm)
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    time.sleep(1.0)
    for nm in ("rc_norm_1", "rc_norm_2", "rc_norm_3"):
        sh("python3 /tmp/dump_cam3_frame.py 0x01000000 /tmp/%s.ppm >/dev/null 2>&1" % nm, show=False)
        names.append(nm)
        print("   dumped", nm)
finally:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")

sftp = c.open_sftp()
for nm in names:
    try:
        sftp.get("/tmp/%s.ppm" % nm, os.path.join(OUT, nm + ".ppm"))
    except Exception as e:  # noqa: BLE001
        print("dl fail", nm, e)
sftp.close()
c.close()
print("DONE")
