#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_tag_probe.py -- READ-ONLY probe of the camera frame path (run on RK3568).

Reads the prep frame tags (TAG_ADDR_1/2) over time and samples two frame
buffers, reporting whether counters advance and whether frame data changes.
Performs no register writes and no CAM_EN changes.
"""
import ctypes
import fcntl
import mmap
import os
import struct
import time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)


def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr


MAP, DW = IOWR(2), IOWR(5)


class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


BUF = 4 * 1024 * 1024
for _c in (0, 1):            # 0 = TX buffer, 1 = RX buffer
    op = DMA_OPERATION(); op.cmd = _c; op.total_length = BUF
    fcntl.ioctl(FD, MAP, op, True)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

TAG1, TAG2 = 0x00896000, 0x00A96000
FB1, FB2 = 0x00800000, 0x00A00000
FRAME_BYTES = 640 * 480 * 2


def ddrread(addr, n, tmo=8):
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = addr; o.total_length = n
    try:
        r = fcntl.ioctl(FD, DW, o, True)
    except Exception as e:  # noqa: BLE001
        return None
    if r != 0:
        return None
    return bytes(RX[0:n])


def tag(addr):
    d = ddrread(addr, 4)
    return struct.unpack('<I', d)[0] if d else None


print('== tags over time ==', flush=True)
prev = None
for i in range(10):
    t1, t2 = tag(TAG1), tag(TAG2)
    print('  [%d] TAG1=%s TAG2=%s' % (i, t1, t2), flush=True)
    time.sleep(0.6)

print('== frame buffer samples ==', flush=True)
a1 = ddrread(FB1, FRAME_BYTES)
time.sleep(0.7)
a2 = ddrread(FB1, FRAME_BYTES)
if a1 and a2:
    nz = sum(1 for x in a1 if x)
    print('  FB1 nz=%d uniq=%d head=%s' % (nz, len(set(a1)), a1[:16].hex()), flush=True)
    diff = sum(1 for x, y in zip(a1, a2) if x != y)
    print('  FB1 vs FB1(later): differing bytes = %d / %d' % (diff, len(a1)), flush=True)
else:
    print('  FB1 read failed', flush=True)
b1 = ddrread(FB2, FRAME_BYTES)
print('  FB2 head=%s' % (b1[:16].hex() if b1 else 'FAIL'), flush=True)
os.close(FD)
print('DONE', flush=True)
