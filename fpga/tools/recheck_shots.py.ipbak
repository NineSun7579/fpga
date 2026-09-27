# -*- coding: utf-8 -*-
"""Zero-risk recheck: two display screenshots, no driver touch."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.10.241", 22, "linaro", "123456", timeout=15,
          allow_agent=False, look_for_keys=False)
inner = ("DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
         "/root/ov5640/qshot/qshot /tmp/recheck_a.png 900 >/dev/null 2>&1; "
         "sleep 3; "
         "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
         "/root/ov5640/qshot/qshot /tmp/recheck_b.png 900 >/dev/null 2>&1; "
         "ls -la /tmp/recheck_a.png /tmp/recheck_b.png; "
         "pgrep -a -x camview | head -3")
cmd = "echo '123456' | sudo -S bash -c " + "'" + inner + "'"
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode("utf-8", "replace"), flush=True)
print(e.read().decode("utf-8", "replace")[:300], flush=True)
s = c.open_sftp()
s.get("/tmp/recheck_a.png", "tp/recheck_a.png")
s.get("/tmp/recheck_b.png", "tp/recheck_b.png")
print("pulled", flush=True)
c.close()
