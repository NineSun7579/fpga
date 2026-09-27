#!/usr/bin/env python3
"""Dump one cam3 DDR frame (RGB565 640x480) to a PPM for inspection."""
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

W, H = 640, 480
FRAME = W * H * 2

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
for c in (0, 1):
    o = O(); o.cmd = c; o.ln = 4194304
    signal.alarm(8); fcntl.ioctl(FD, I(2), o, True); signal.alarm(0)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)

def rd(a, n):
    o = O(); o.off = 0; o.ddr = a; o.ln = n
    signal.alarm(20)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    finally:
        signal.alarm(0)
    return bytes(RX[0:n])

base = int(sys.argv[1], 0)
out = sys.argv[2]
img = bytearray()
CH = W * 2 * 8
for off in range(0, FRAME, CH):
    img += rd(base + off, CH)

# BGR565 -> PPM
ppm = bytearray(b'P6\n%d %d\n255\n' % (W, H))
for i in range(W * H):
    v = img[2 * i] | (img[2 * i + 1] << 8)
    r = ((v >> 11) & 0x1F) << 3
    g = ((v >> 5) & 0x3F) << 2
    b = (v & 0x1F) << 3
    ppm += bytes((r, g, b))
open(out, 'wb').write(ppm)
os.close(FD)
print('wrote', out, len(ppm))
