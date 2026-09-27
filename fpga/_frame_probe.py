#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_frame_probe.py -- dump structure of the camera frame buffers (run on board).

Reads CAM_ADDR_1/2 (640x480x2 bytes), prints a byte histogram and an ASCII
luma rendering to reveal whether the frame is a real image or a flat/pattern.
"""
import ctypes
import fcntl
import mmap
import os
import struct
import sys
import time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)


def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr


MAP, DW = IOWR(2), IOWR(5)


class O(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


BUF = 4 * 1024 * 1024
for c in (0, 1):
    o = O(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

FB1, FB2 = 0x00800000, 0x00A00000
W, H = 640, 480
N = W * H * 2


def ddrread(addr, n, tmo=10):
    o = O(); o.offset_addr = 0; o.ddr3_addr = addr; o.total_length = n
    try:
        r = fcntl.ioctl(FD, DW, o, True)
    except Exception:  # noqa: BLE001
        return None
    if r != 0:
        return None
    return bytes(RX[0:n])


which = sys.argv[1] if len(sys.argv) > 1 else '1'
addr = FB1 if which == '1' else FB2
d = ddrread(addr, N)
if d is None:
    print('READ FAIL @0x%08X' % addr); os.close(FD); sys.exit(1)

hist = {}
for x in d:
    hist[x] = hist.get(x, 0) + 1
top = sorted(hist.items(), key=lambda kv: -kv[1])[:8]
print('addr=0x%08X uniq=%d top values (byte:count):' % (addr, len(hist)))
for v, c in top:
    print('   0x%02X : %d' % (v, c))

ramp = " .:-=+*#%@"
print('--- ASCII luma (raw LE rgb565) ---')
for yy in range(0, H, 10):
    row = []
    for xx in range(0, W, 8):
        i = (yy * W + xx) * 2
        p = d[i] | (d[i + 1] << 8)
        r = (p >> 11) & 0x1F
        g = (p >> 5) & 0x3F
        b = p & 0x1F
        luma = (r * 8 + g * 4 + b * 8) // 3
        row.append(ramp[min(9, luma // 26)])
    print(''.join(row))
os.close(FD)
print('DONE')
