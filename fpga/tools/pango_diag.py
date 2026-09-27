# -*- coding: utf-8 -*-
"""Diagnose why the pango driver MAP ioctl times out (after a power cycle)."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

CHECKS = [
    "pgrep -af camview || echo 'no camview process'",
    "pgrep -af run_camview || echo 'no run_camview'",
    "fuser -v /dev/pango_pci_driver 2>&1 || echo 'fuser: none'",
    "lsmod | grep -i pango",
    "dmesg | tail -30",
    "cat /proc/interrupts | grep -i -E 'pango|misc|21:00' || echo 'no irq line'",
    "lspci -vv -s 0002:21:00.0 2>&1 | head -25",
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
        print("ERR:", err[:400])
    print()
c.close()
