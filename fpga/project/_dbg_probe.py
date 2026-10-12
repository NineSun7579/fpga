#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_dbg_probe.py -- read the ov5640 debug counters (board), twice, to show deltas."""
import ctypes
import fcntl
import mmap
import os
import struct
import time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)


def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr


MAP, F2H = IOWR(2), IOWR(5)


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


def rr(addr):
    o = O(); o.offset_addr = 0; o.ddr3_addr = addr; o.total_length = 16
    try:
        r = fcntl.ioctl(FD, F2H, o, True)
    except Exception:  # noqa: BLE001
        return None
    if r != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]


REGS = [
    ("ACK   ", 0x20000000), ("PCLK_CNT", 0x20000010), ("VSYNCS  ", 0x20000020),
    ("CAM_WORDS", 0x20000030), ("ZDIN    ", 0x20000050), ("I2C_ID  ", 0x20000060),
    ("SYS(aw/b)", 0x20000070), ("ZOUT    ", 0x20000090), ("BEAT_CNT", 0x200000a0),
    ("XDMA_REQ", 0x200000b0), ("AXI_NOW ", 0x200000d0), ("VSYNC_RAW", 0x200000e0),
    ("BEAT_LAST", 0x200000f0), ("PIPE_STS", 0x20000130), ("TS0     ", 0x20000170),
]


def snap():
    d = {}
    for name, a in REGS:
        d[name] = rr(a)
    return d


s1 = snap()
time.sleep(1.2)
s2 = snap()
print("%-10s %-12s %-12s %s" % ("NAME", "t0", "t1", "delta"))
for name, _a in REGS:
    v1, v2 = s1[name], s2[name]
    if v1 is None or v2 is None:
        print("%-10s %-12s %-12s -" % (name, v1, v2))
    else:
        print("%-10s 0x%08X   0x%08X   %d" % (name, v1, v2, (v2 - v1) & 0xFFFFFFFF))
os.close(FD)
print("DONE")
