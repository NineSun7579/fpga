#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_rw_probe.py -- DDR write/read integrity + frame-buffer small reads (board).

1) writes a known 16B pattern to the documented host scratch address and reads
   it back -> validates the host<->FPGA DMA read path;
2) reads small blocks from the frame buffer at several offsets.
"""
import ctypes
import fcntl
import mmap
import os
import struct

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)


def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr


MAP, DR, DW = IOWR(2), IOWR(4), IOWR(5)


class O(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


BUF = 4 * 1024 * 1024
for c in (0, 1):
    o = O(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)


def ioctl(nr, addr, n, tmo=8):
    o = O(); o.offset_addr = 0; o.ddr3_addr = addr; o.total_length = n
    try:
        return fcntl.ioctl(FD, nr, o, True)
    except Exception as e:  # noqa: BLE001
        return 'EXC:%s' % e


def wr16(addr, data):
    TX[0:16] = data
    return ioctl(DR, addr, 16)


def rd(addr, n):
    r = ioctl(DW, addr, n)
    if r != 0:
        return None
    return bytes(RX[0:n])


SCRATCH = 0x0B000000
pat = bytes(range(1, 17))
print('== DDR scratch integrity @0x%08X ==' % SCRATCH)
print('  write rc =', wr16(SCRATCH, pat))
got = rd(SCRATCH, 16)
print('  wrote    :', pat.hex())
print('  readback :', got.hex() if got else 'FAIL')
print('  MATCH    :', got == pat)

print('== frame buffer small blocks ==')
for name, addr in (("FB1", 0x00800000), ("FB2", 0x00A00000)):
    for off in (0, 16, 1280, 2560, 3840):
        d = rd(addr + off, 32)
        print('  %s+%-6d : %s' % (name, off, d.hex() if d else 'FAIL'))

print('== tag area ==')
for name, addr in (("TAG1", 0x00896000), ("TAG2", 0x00A96000)):
    d = rd(addr, 16)
    print('  %s : %s' % (name, d.hex() if d else 'FAIL'))

os.close(FD)
print('DONE')
