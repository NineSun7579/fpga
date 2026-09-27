# -*- coding: utf-8 -*-
"""Re-flash the verified cam3 bitstream over JTAG and bring the driver up.

The FPGA is configured into SRAM over JTAG, so a power cycle reverts it to the
stale flash image and the pango driver's probe then fails (-22) -> the F2H ioctl
faults.  This reproduces the documented bring-up:

    reboot -> link down (rmmod + pci remove) -> JTAG burn -> rescan -> insmod

Then it prints the driver dmesg so the probe result is visible.
"""
import os
import subprocess
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
DEV = "/sys/bus/pci/devices/0002:21:00.0"
TCL = os.path.join(ROOT, "flash_verified_cam3.tcl")


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=180, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd, flush=True)
        if out.strip():
            print(out.rstrip(), flush=True)
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:400], flush=True)
    return out


print("=== 0. no PDS/cdt running on the PC ===")
r = subprocess.run(["tasklist"], capture_output=True)
tl = r.stdout.decode("utf-8", "replace").lower()
for name in ("pds.exe", "pds_shell.exe", "cdt_cfg.exe", "cdt_js.exe"):
    print("  %-15s %s" % (name, "RUNNING" if name in tl else "-"))

print("=== 1. reboot the board (clear any leaked driver state) ===")
c = connect()
sh(c, "sync; (sleep 1; reboot) > /dev/null 2>&1 & echo reboot-issued")
try:
    c.close()
except Exception:
    pass

c = None
for i in range(40):
    time.sleep(6)
    try:
        c = connect(timeout=8)
        print("back after ~%ds" % ((i + 1) * 6), flush=True)
        break
    except Exception:
        pass
if c is None:
    print("!! board did not come back")
    sys.exit(1)

sh(c, "lsmod | grep -i pango || echo 'driver not loaded (expected)'")

print("=== 2. link down (so the host is not bound during reconfig) ===")
sh(c, "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "test -e %s && echo 1 > %s/remove; sleep 2; "
      "(test -e %s && echo 'still present') || echo 'device removed'" % (DEV, DEV, DEV))

print("=== 3. JTAG burn the verified cam3 bitstream ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-1500:], flush=True)
if "BURN OK" not in out:
    print("!! BURN FAILED -- is the JTAG cable connected?")
    c.close()
    sys.exit(2)

print("=== 4. rescan + insmod ===")
sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; "
      "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 2; "
      "lsmod | grep -i pango; "
      "ls -l %s/driver 2>&1" % DEV)

print("=== 5. driver dmesg (probe result) ===")
sh(c, "dmesg | grep -i pango | tail -30 || echo 'no pango dmesg'")

c.close()
print("DONE")
