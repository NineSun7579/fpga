#!/usr/bin/env python3
"""Board-side: sweep cam3's IODELAY step and measure normal-scene noise.

For each delay, read a set of rows from the ping frame and compute the mean
absolute horizontal gradient of G (speckle/noise indicator).  The scene is
dark and static, so a lower value = cleaner capture.
"""
import ctypes
import fcntl
import mmap
import os
import signal
import struct
import sys
import time

REG = 0x20000400
DLY = REG + 0x30
FRAME = 0x01000000
ROWS = [120, 180, 240, 300, 360, 420]


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


def w32(a, v):
    o = O()
    o.off = 0
    o.ddr = a
    o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(4), o, True)
    finally:
        signal.alarm(0)


def reg(a):
    return struct.unpack('<I', rd(a, 4))[0]


def measure():
    tot, n = 0.0, 0
    for r in ROWS:
        b = rd(FRAME + r * 1280, 1280)
        W = struct.unpack('<640H', b)
        G = [(v >> 5) & 0x3F for v in W]          # RGB565 G field
        for i in range(1, 640):
            tot += abs(G[i] - G[i - 1])
            n += 1
    return tot / n


print('cam_en=%d frames=%d' % (reg(REG + 0x40), reg(REG + 0xF0)))
results = []
for v in list(range(0, 256, 8)):
    w32(DLY, v)
    time.sleep(0.30)
    m = measure()
    results.append((v, m))
    print('dly=%3d  noise(mean|dG/dx|)=%6.2f' % (v, m))
w32(DLY, 40)
time.sleep(0.30)
print('reset dly=40  noise=%6.2f' % measure())
print('BEST:', min(results, key=lambda t: t[1]))
os.close(FD)
