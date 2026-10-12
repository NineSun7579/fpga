# -*- coding: utf-8 -*-
"""Read-only: who holds the pango driver, and is xdotool available?"""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

CHECKS = [
    "echo sanity-ok",
    "ps -eo pid,ppid,stat,comm,args | grep -iE 'cam|pango' | grep -v grep || echo 'no cam/pango procs'",
    "fuser -v /dev/pango_pci_driver 2>&1 || echo 'fuser: no holder'",
    "cat /proc/modules | grep -i pango || echo 'module not in /proc/modules'",
    "ls -l /proc/*/fd 2>/dev/null | grep -i pango_pci || echo 'no fd maps to pango'",
    "which xdotool || echo 'no xdotool'",
    "ls -l /root/ov5640/camview/ 2>/dev/null | head -20",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
for cmd in CHECKS:
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=40)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("$ " + cmd)
    if out:
        print(out)
    if err and "password for" not in err:
        print("ERR:", err[:300])
    print()
c.close()
