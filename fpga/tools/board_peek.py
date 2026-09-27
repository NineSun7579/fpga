#!/usr/bin/env python3
"""Generic read of 32-bit words at AXI addresses through the pango driver."""
import ctypes, fcntl, mmap, os, signal, struct, sys

class TO(Exception):
    pass

def _al(s, f):
    raise TO()

signal.signal(signal.SIGALRM, _al)

class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

def I(n):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | n

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
for c in (0, 1):
    o = O(); o.cmd = c; o.ln = 4194304
    signal.alarm(8); fcntl.ioctl(FD, I(2), o, True); signal.alarm(0)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)

def rd(a):
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    finally:
        signal.alarm(0)
    return struct.unpack('<I', RX[0:4])[0]

for a in sys.argv[1:]:
    v = rd(int(a, 0))
    print('0x%08X = 0x%08X  %d' % (int(a, 0), v, v))
os.close(FD)
