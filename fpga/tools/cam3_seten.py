#!/usr/bin/env python3
"""cam3_seten.py <0|1> -- write cam3's REG_CAM_EN (0x20000440) through the PCIe driver."""
import ctypes
import fcntl
import os
import mmap
import signal
import struct
import sys


class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]


def I(n):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | n


val = int(sys.argv[1])
fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
for c in (0, 1):
    o = O(); o.cmd = c; o.ln = 4194304
    signal.alarm(8); fcntl.ioctl(fd, I(2), o, True); signal.alarm(0)
tx = mmap.mmap(fd, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
tx[0:4] = struct.pack('<I', val)
o = O(); o.off = 0; o.ddr = 0x20000440; o.ln = 16
signal.alarm(8); fcntl.ioctl(fd, I(4), o, True); signal.alarm(0)
print('cam3 cam_en=%d written' % val)
os.close(fd)
