# -*- coding: utf-8 -*-
"""Board-side diagnostics for the pango_pci_driver wedge."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.10.203", 22, "linaro", "123456", timeout=10,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=60):
    full = "echo '%s' | sudo -S bash -c %s" % ("123456", "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    print("$", cmd)
    print(o.read().decode("utf-8", "replace").rstrip())


sh("ps -ef | grep -E 'camview|shift_probe|board_peek' | grep -v grep")
sh("ls -l /dev/pango_pci_driver; lsmod | grep pango; grep pango /proc/modules")
sh("dmesg | tail -30")
c.close()
