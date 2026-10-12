# -*- coding: utf-8 -*-
"""Stop camview cleanly and (if needed) recover the wedge-prone pango driver,
then verify the MAP ioctl works.  Leaves camview STOPPED so the A/B can run."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"

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
            fcntl.ioctl(fd, I(2), o, True)
            print('MAP', c, 'ok')
        finally:
            signal.alarm(0)
finally:
    os.close(fd)
print('MAPTEST DONE')
'''


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=180, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


c = connect()
sftp = c.open_sftp()
with sftp.open("/tmp/_maptest.py", "w") as f:
    f.write(MAPTEST)
sftp.close()

sh(c, "cat /root/ov5640/run_camview.sh")
sh(c, "ps -eo pid,ppid,comm,args | grep -E '[c]amview' || echo none")

print("--- stopping camview ---")
sh(c, "pkill -9 -f '[c]amview' 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; "
   "pkill -9 -f '[c]amview' 2>/dev/null; sleep 2; "
   "fuser -v /dev/pango_pci_driver 2>&1 | tail -3; "
   "ps -eo pid,comm,args | grep -E '[c]amview' || echo 'camview stopped'")

print("--- MAP test (driver healthy?) ---")
out = sh(c, "python3 /tmp/_maptest.py 2>&1")
if "MAPTEST DONE" not in out:
    print("--- driver wedged: rmmod + PCIe rescan + insmod ---")
    sh(c, "rmmod pango_pci_driver 2>&1; sleep 1; lsmod | grep -i pango || echo 'module removed'")
    sh(c, "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>&1; sleep 2; "
       "echo 1 > /sys/bus/pci/rescan 2>&1; sleep 4; "
       "insmod /root/ov5640/pango_pci_driver.ko && echo insmod-ok; sleep 1; "
       "ls -l /dev/pango_pci_driver", t=120)
    print("--- MAP test again ---")
    sh(c, "python3 /tmp/_maptest.py 2>&1")

c.close()
print("DONE")
