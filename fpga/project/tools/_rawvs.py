# -*- coding: utf-8 -*-
"""Compare cam3 raw vs filtered vsync/href edge counters (glitch detector)."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")
ADDR = "0x20000410 0x20000420 0x20000490 0x200004E0 0x200004F0"
try:
    for i in range(4):
        o, _ = sh("python3 /tmp/board_peek.py " + ADDR)
        print("--- sample %d (t=%.1fs) ---" % (i, i * 1.5))
        print(o.strip())
        time.sleep(1.5)
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
