#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_pattern_probe.py -- characterise the frame-buffer byte pattern (run on board)."""
import ctypes
import fcntl
import mmap
import os

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


def ddrread(addr, n, tmo=10):
    o = O(); o.offset_addr = 0; o.ddr3_addr = addr; o.total_length = n
    try:
        r = fcntl.ioctl(FD, DW, o, True)
    except Exception:  # noqa: BLE001
        return None
    return bytes(RX[0:n]) if r == 0 else None


W, H = 640, 480
for name, addr in (("FB1", 0x00800000), ("FB2", 0x00A00000)):
    d = ddrread(addr, W * H * 2)
    if d is None:
        print(name, "READ FAIL"); continue
    print("== %s @0x%08X ==" % (name, addr))
    print("  head :", d[:32].hex())
    # first bytes of the first 12 rows
    for r in range(12):
        off = r * W * 2
        print("  row%02d:" % r, d[off:off + 16].hex())
    # per-row count of 0xFF bytes over full width for the first 40 rows and last 20
    def ffcount(r):
        off = r * W * 2
        return sum(1 for x in d[off:off + W * 2] if x == 0xFF)
    print("  ff/row:", [ffcount(r) for r in (0, 1, 2, 3, 4, 5, 100, 200, 300, 400, 470, 475, 479)])
os.close(FD)
print("DONE")
