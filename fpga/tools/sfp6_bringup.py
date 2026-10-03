# -*- coding: utf-8 -*-
"""sfp6_bringup.py -- PCIe recovery ritual over the RK3568 debug console (COM5),
then start the six-grid camview.  Mirrors recover_hdmi.py's chain.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rk_console import Console

PORT = os.environ.get("RK_PORT", "COM5")
DEV = "/sys/bus/pci/devices/0002:21:00.0"

c = Console(PORT)


def step(name, cmd, t=60, quiet=True):
    print("== %s ==" % name, flush=True)
    out = c.sh(cmd, timeout=t, quiet=quiet)
    print(out if out.strip() else "(no output)")
    print("-" * 60, flush=True)
    return out


try:
    step("0 state",
         "cat /proc/uptime | cut -d' ' -f1; "
         "lsmod | grep -a pango || echo MODULE_NOT_LOADED; "
         "ls -l %s/driver 2>&1 | tail -1" % DEV)

    step("1 stop camview + watchdog",
         "rm -f /tmp/camview.lock; "
         "pkill -9 -x camview 2>/dev/null; pkill -9 -f run_camview 2>/dev/null; sleep 3; "
         "ps -eo pid,args | grep -E '[c]amview' || echo CAMVIEW_GONE")

    step("2 PERST toggle (gpio144)",
         "echo 144 > /sys/class/gpio/export 2>/dev/null; "
         "echo out > /sys/class/gpio/gpio144/direction 2>/dev/null; "
         "echo 0 > /sys/class/gpio/gpio144/value; sleep 0.3; "
         "echo 1 > /sys/class/gpio/gpio144/value; sleep 0.5; echo PERST_TOGGLED")

    step("3 rmmod + remove + rescan",
         "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
         "echo 1 > %s/remove 2>/dev/null; sleep 1; "
         "echo 1 > /sys/bus/pci/rescan; sleep 4; "
         "lspci -d 0755: -nn || echo NO_LSPCI" % DEV, t=90)

    step("4 insmod",
         "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 2; "
         "ls -l %s/driver 2>&1 | tail -1; "
         "ls -l /dev/pango_pci_driver" % DEV, t=90)

    step("5 driver dmesg",
         "dmesg | grep -a -iE 'MSI Interrupt|pango_pci|0755' | tail -10", t=60, quiet=False)
finally:
    c.close()
print("DONE")
