# -*- coding: utf-8 -*-
"""Quick board state check after a power cycle."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"

CHECKS = [
    "uname -a",
    "lsmod | grep -i pango || echo 'no pango module'",
    "ls -l /dev/pango_pci_driver 2>&1",
    "pgrep -af camview || echo 'no camview'",
    "lspci -s 0002:21:00.0 2>&1 || lspci | grep -i 21:00",
    "free -m | head -2",
    "uptime",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
for cmd in CHECKS:
    full = "echo '%s' | sudo -S bash -c \"%s\"" % (PW, cmd.replace('"', '\\"'))
    _, o, e = c.exec_command(full, timeout=30)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("$ " + cmd)
    if out:
        print(out)
    if err and "password for" not in err:
        print("ERR:", err)
    print()
c.close()
