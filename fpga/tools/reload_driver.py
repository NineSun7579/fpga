# -*- coding: utf-8 -*-
"""Reload the pango PCIe driver after a JTAG reconfiguration."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    print("$", cmd)
    if out.strip():
        print(out.rstrip())
    if err.strip() and "password for" not in err:
        print("ERR:", err.rstrip()[:300])
    return out


sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 1; true")
sh("rmmod pango_pci_driver 2>/dev/null; sleep 1; "
   "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 2; "
   "echo 1 > /sys/bus/pci/rescan; sleep 4; "
   "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK")
sh("ls -l /dev/pango_pci_driver; lsmod | grep pango")
sh("python3 /tmp/board_poke.py r 0x20000410 2>/dev/null || "
   "python3 /tmp/board_peek.py 0x20000410 0x200004E0 2>/dev/null || true")
c.close()
print("DONE")
