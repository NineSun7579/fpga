# -*- coding: utf-8 -*-
"""Why does the pango driver probe fail with -22?  Read-only inspection."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

CHECKS = [
    "dmesg | tail -70",
    "lspci -vv -s 0002:21:00.0 2>&1 | head -40",
    "lspci -xxx -s 0002:21:00.0 2>&1 | head -18",
    "ls -l /sys/bus/pci/devices/0002:21:00.0/driver 2>&1 || echo 'NO driver bound'",
    "cat /sys/bus/pci/devices/0002:21:00.0/{vendor,device,class,revision} 2>&1",
    "cat /sys/bus/pci/devices/0002:21:00.0/resource 2>&1",
    "cat /proc/iomem | grep -i -B1 -A1 '21:00' || echo 'no iomem region'",
    "lsmod | grep -i pango || echo 'module gone'",
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
