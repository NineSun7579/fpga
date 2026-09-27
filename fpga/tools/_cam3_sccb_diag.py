# -*- coding: utf-8 -*-
"""Stop viewer, run cam3 SCCB diagnostics (id + read/write with ack reporting)."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def run(cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
sftp.close()

print(run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 3; echo stopped")[0].strip())
for cmd in ("id", "rd 0x300a", "rd 0x300b", "rd 0x503d",
            "wr 0x503d 0x80", "rd 0x503d",
            "wr 0x503d 0x00", "rd 0x503d"):
    out, err = run("python3 /tmp/cam3_i2c_pt.py %s 2>&1" % cmd)
    print("$ %-16s -> %s %s" % (cmd, out.strip().replace("\n", " | "), err.strip()[:120]))
out, err = run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")
print(out.strip())
c.close()
