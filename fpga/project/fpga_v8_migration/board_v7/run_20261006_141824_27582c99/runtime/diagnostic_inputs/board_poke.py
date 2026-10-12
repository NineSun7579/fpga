#!/usr/bin/env python3
"""Read/write a 32-bit AXI register through the pango driver.
Usage: board_poke.py r <addr> | board_poke.py w <addr> <value>"""
import ctypes, fcntl, mmap, os, signal, struct, sys, time

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
TX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=0)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)

def wr(a, v):
    TX[0:4] = struct.pack('<I', v)
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(4), o, True)
    finally:
        signal.alarm(0)

def rd(a):
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        r = fcntl.ioctl(FD, I(5), o, True)
    finally:
        signal.alarm(0)
    if r != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]

mode = sys.argv[1]
if mode == 'w':
    a = int(sys.argv[2], 0); v = int(sys.argv[3], 0)
    wr(a, v)
    time.sleep(0.05)
    print('W 0x%08X <= 0x%08X ; readback = 0x%08X' % (a, v, rd(a)))
else:
    a = int(sys.argv[2], 0)
    print('R 0x%08X = 0x%08X' % (a, rd(a)))
os.close(FD)
