# -*- coding: utf-8 -*-
"""Reboot the board, then bring the driver up WITHOUT starting camview
(so the driver stays free for the PCLK A/B).  Ends with a MAP test."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"

MAPTEST = r'''
import fcntl, os, signal, ctypes
class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]
def I(n): return 0xC0000000 | (4 << 16) | (0x53 << 8) | n
class TO(Exception): pass
def al(s, f): raise TO()
signal.signal(signal.SIGALRM, al)
fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
try:
    for c in (0, 1):
        o = O(); o.cmd = c; o.ln = 4194304
        signal.alarm(6)
        try:
            fcntl.ioctl(fd, I(2), o, True); print('MAP', c, 'ok')
        finally:
            signal.alarm(0)
finally:
    os.close(fd)
print('MAPTEST DONE')
'''


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=120, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd)
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


print("=== rebooting the board ===")
try:
    c = connect()
    sftp = c.open_sftp()
    with sftp.open("/tmp/_maptest.py", "w") as f:
        f.write(MAPTEST)
    sftp.close()
    sh(c, "sync; (sleep 1; reboot) > /dev/null 2>&1 & echo reboot-issued")
    try:
        c.close()
    except Exception:
        pass
except Exception as ex:
    print("note:", ex)

print("=== waiting for it to come back ===")
up = None
for i in range(40):
    time.sleep(6)
    try:
        up = connect(timeout=8)
        print("back after ~%ds" % ((i + 1) * 6))
        break
    except Exception:
        pass
if up is None:
    print("!! board did not come back (needs a manual power cycle)")
    sys.exit(1)

sh(up, "uptime; lsmod | grep -i pango || echo 'driver not loaded'")
sh(up, "test -c /dev/pango_pci_driver && echo 'dev present' || "
      "(insmod /root/ov5640/pango_pci_driver.ko && echo insmod-ok); sleep 2; "
      "ls -l /dev/pango_pci_driver")
print("=== MAP test (with NO camview running) ===")
sh(up, "python3 /tmp/_maptest.py 2>&1")
up.close()
print("DONE")
