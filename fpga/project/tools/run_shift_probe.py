# -*- coding: utf-8 -*-
"""host runner: push + run cam3_shift_probe.py with the test pattern on."""
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


def sh(cmd, t=300, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    if show:
        print("$", cmd)
        print(out.rstrip())
    return out


sftp = c.open_sftp()
for f in ("cam3_shift_probe.py", "cam3_i2c_pt.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
try:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1")
    time.sleep(1.0)
    sh("python3 /tmp/cam3_shift_probe.py 0x01000000 40 0.05 2>&1")
    print("---- pong buffer (0x01200000) ----")
    sh("python3 /tmp/cam3_shift_probe.py 0x01200000 20 0.05 2>&1")
finally:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")

c.close()
print("DONE")
