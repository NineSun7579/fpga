#!/usr/bin/env python3
"""Board-side: characterise cam3's frame-to-frame horizontal shift.

Repeatedly reads row 240 of the ping frame (RGB565), and reports, for each
sample, the integer pixel shift that best aligns the row against the first
sample's row profile (search -400..+400).
"""
import ctypes
import fcntl
import mmap
import os
import signal
import struct
import sys
import time


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
    o = O()
    o.cmd = c
    o.ln = 4194304
    signal.alarm(8)
    fcntl.ioctl(FD, I(2), o, True)
    signal.alarm(0)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)


def rd(a, n):
    o = O()
    o.off = 0
    o.ddr = a
    o.ln = n
    signal.alarm(20)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    finally:
        signal.alarm(0)
    return bytes(RX[0:n])


def reg(a):
    return struct.unpack('<I', rd(a, 4))[0]


frame_base = int(sys.argv[1], 0)
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
ROW = 240
rowaddr = frame_base + ROW * 640 * 2
REG = 0x20000400

print('cam3 frames(0xF0) = %d   cam_en(0x40)=%d' % (reg(REG + 0xF0), reg(REG + 0x40)))


def profile():
    b = rd(rowaddr, 1280)
    w = struct.unpack('<640H', b)
    return [(v >> 11) & 0x1F for v in w]          # R channel 0..31


ref = profile()
print('row240 max R5 = %d (24+=bright)' % max(ref))
best_hist = {}
for k in range(n):
    cur = profile()
    best = None
    for s in range(-400, 401):
        if s >= 0:
            x, y = ref[s:], cur[:640 - s]
        else:
            x, y = ref[:640 + s], cur[-s:]
        if len(x) < 400:
            continue
        d = sum(abs(a - b) for a, b in zip(x, y)) / len(x)
        if best is None or d < best[1]:
            best = (s, d)
    fr = reg(REG + 0xF0)
    best_hist[best[0]] = best_hist.get(best[0], 0) + 1
    print('sample %2d  shift=%+4d (resid %4.1f)  frame=%d' % (k, best[0], best[1], fr))
    time.sleep(gap)

print('shift histogram:', best_hist)
os.close(FD)
