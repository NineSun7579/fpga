# -*- coding: utf-8 -*-
"""Reload the RK3568 PCIe driver (proven recipe) then optionally run a board cmd."""
import sys
import time

import paramiko

PW = "123456"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.10.203", 22, "linaro", PW, timeout=10, banner_timeout=15,
              auth_timeout=15, allow_agent=False, look_for_keys=False)
    return c


def sudo(c, cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def main():
    c = connect()
    try:
        print("== kill viewers ==")
        print(sudo(c, "killall -9 camview 2>/dev/null; sleep 2; echo killed")[0].strip())
        print("== rmmod ==")
        o, e = sudo(c, "rmmod pango_pci_driver 2>&1; echo rc=$?")
        print(o.strip(), e.strip()[:150])
        time.sleep(2)
        print("== rescan ==")
        o, e = sudo(c, "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 2; "
                       "echo 1 > /sys/bus/pci/rescan; sleep 3; lspci -d 0755: | head -2")
        print(o.strip(), e.strip()[:150])
        print("== insmod ==")
        o, e = sudo(c, "insmod /root/ov5640/pango_pci_driver.ko 2>&1; echo rc=$?; sleep 3; "
                       "lsmod | grep pango")
        print(o.strip(), e.strip()[:150])
        if len(sys.argv) > 1:
            print("== extra ==")
            print(sudo(c, sys.argv[1])[0].strip())
    finally:
        c.close()


if __name__ == "__main__":
    main()
