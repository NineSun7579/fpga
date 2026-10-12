# -*- coding: utf-8 -*-
"""Bring the RK3568 board up after a power cycle: load the pango driver and
start camview, then verify the three cameras are alive via the FPGA counters."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"


def sh(cmd, t=120, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd)
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:400])
    return out


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)

sh("ls -l /root/ov5640/ | head -40")
sh("lsmod | grep -i pango || echo 'driver not loaded yet'")
# load the driver if needed
sh("test -c /dev/pango_pci_driver && echo 'dev present, skip insmod' || "
   "(insmod /root/ov5640/pango_pci_driver.ko && echo insmod-ok); sleep 1; "
   "ls -l /dev/pango_pci_driver")
# start camview
sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
   "> /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo started; "
   "pgrep -af camview | head -5")
sh("sleep 3; tail -20 /tmp/camview.log")
c.close()
print("DONE")
