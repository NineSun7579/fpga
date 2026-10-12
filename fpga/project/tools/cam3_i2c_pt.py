#!/usr/bin/env python3
"""Host-writable SCCB passthrough for the OV5640 cameras (RK3568 side).

Uses the new FPGA registers in each camera's AXI-Lite segment:
    BASE + 0x100  CMD   W  {bit24 rw(0=write,1=read), [23:8] reg addr, [7:0] data}
    BASE + 0x110  RD    R  {24'b0, read byte}
    BASE + 0x120  STAT  R  {30'b0, done_latched, ack(1=NACK)}

Only CAM3 (BASE 0x2000_0400 -> regs at 0x2000_0500/10/20) is addressable: the
M01 decoder sends the whole 0x2000_0400-0x2000_07FF page to the cam3 register
block, while cam1/cam2's +0x100 fall into the prep_regs window.

Run on the board (needs /dev/pango_pci_driver; viewer may stay up):
    python3 cam3_i2c_pt.py id
    python3 cam3_i2c_pt.py flash on
    python3 cam3_i2c_pt.py testpat on
    python3 cam3_i2c_pt.py wr 0x3019 0x02
    python3 cam3_i2c_pt.py rd 0x300a
"""
import argparse
import ctypes
import fcntl
import mmap
import os
import signal
import struct
import sys
import time

DEFAULT_BASE = 0x20000400


class Timeout(Exception):
    pass


def _alarm(_s, _f):
    raise Timeout()


signal.signal(signal.SIGALRM, _alarm)


class DmaOp(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


def ioctl_code(number):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | number


MAP_CMD = ioctl_code(2)
H2F_CMD = ioctl_code(4)
F2H_CMD = ioctl_code(5)


class PciDriver:
    def __init__(self):
        self.fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
        for mapping in (0, 1):
            op = DmaOp()
            op.cmd = mapping
            op.total_length = 4 * 1024 * 1024
            signal.alarm(8)
            try:
                fcntl.ioctl(self.fd, MAP_CMD, op, True)
            finally:
                signal.alarm(0)
        # TX buffer is mapped at offset 0, RX buffer at offset 1 MiB (driver ABI).
        self.tx = mmap.mmap(self.fd, 4 * 1024 * 1024,
                            prot=mmap.PROT_READ | mmap.PROT_WRITE,
                            flags=mmap.MAP_SHARED, offset=0)
        self.rx = mmap.mmap(self.fd, 4 * 1024 * 1024,
                            prot=mmap.PROT_READ | mmap.PROT_WRITE,
                            flags=mmap.MAP_SHARED, offset=1048576)

    def write32(self, address, value):
        self.tx[0:4] = struct.pack('<I', value)
        op = DmaOp()
        op.offset_addr = 0
        op.ddr3_addr = address
        op.total_length = 16
        signal.alarm(8)
        try:
            r = fcntl.ioctl(self.fd, H2F_CMD, op, True)
        finally:
            signal.alarm(0)
        if r != 0:
            raise IOError('H2F write failed rc=%d' % r)

    def read32(self, address):
        op = DmaOp()
        op.offset_addr = 0
        op.ddr3_addr = address
        op.total_length = 16
        signal.alarm(8)
        try:
            r = fcntl.ioctl(self.fd, F2H_CMD, op, True)
        finally:
            signal.alarm(0)
        if r != 0:
            raise IOError('F2H read failed rc=%d' % r)
        return struct.unpack('<I', self.rx[0:4])[0]

    def close(self):
        try:
            self.rx.close()
        finally:
            try:
                self.tx.close()
            finally:
                os.close(self.fd)


class CamI2c:
    def __init__(self, drv, base=DEFAULT_BASE, verbose=True):
        self.drv = drv
        self.base = base
        self.verbose = verbose

    def xact(self, rw, addr, data=0, timeout_s=0.5):
        word = ((rw & 1) << 24) | ((addr & 0xFFFF) << 8) | (data & 0xFF)
        self.drv.write32(self.base + 0x100, word)
        t0 = time.time()
        stat = 0
        while time.time() - t0 < timeout_s:
            stat = self.drv.read32(self.base + 0x120)
            if stat & 0x2:
                break
            time.sleep(0.0005)
        else:
            raise Timeout('SCCB task did not complete (STAT=0x%08X)' % stat)
        rd = self.drv.read32(self.base + 0x110) & 0xFF
        nack = stat & 0x1
        if self.verbose:
            kind = 'RD' if rw else 'WR'
            extra = ('-> 0x%02X' % rd) if rw else ('<= 0x%02X' % data)
            print('  SCCB %s reg 0x%04X %s%s' % (kind, addr, extra,
                                                 '  [NACK]' if nack else ''))
        return rd, nack

    def read(self, addr):
        rd, nack = self.xact(1, addr)
        return rd

    def write(self, addr, data):
        return self.xact(0, addr, data)


FLASH_ON = [(0x3016, 0x02), (0x301c, 0x02), (0x3019, 0x02)]
FLASH_OFF = [(0x3016, 0x02), (0x301c, 0x02), (0x3019, 0x00)]


def main():
    ap = argparse.ArgumentParser(description='OV5640 host SCCB passthrough')
    ap.add_argument('--base', type=lambda s: int(s, 0), default=DEFAULT_BASE)
    ap.add_argument('--quiet', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('id', help='read OV5640 chip ID (expect 0x56,0x40)')
    p.add_argument('--addr-hi', type=lambda s: int(s, 0), default=0x300a)
    p.add_argument('--addr-lo', type=lambda s: int(s, 0), default=0x300b)

    p = sub.add_parser('rd', help='read one sensor register')
    p.add_argument('addr', type=lambda s: int(s, 0))

    p = sub.add_parser('wr', help='write one sensor register')
    p.add_argument('addr', type=lambda s: int(s, 0))
    p.add_argument('data', type=lambda s: int(s, 0))

    p = sub.add_parser('flash', help='module flash / fill-light control')
    p.add_argument('state', choices=('on', 'off'))

    p = sub.add_parser('testpat', help='OV5640 colour-bar test pattern 0x503d')
    p.add_argument('state', choices=('on', 'off'))

    args = ap.parse_args()
    drv = PciDriver()
    try:
        cam = CamI2c(drv, args.base, verbose=not args.quiet)
        if args.cmd == 'id':
            hi = cam.read(args.addr_hi)
            lo = cam.read(args.addr_lo)
            ok = (hi == 0x56 and lo == 0x40)
            print('CAM ID @0x%04X/0x%04X = 0x%02X 0x%02X  ->  %s'
                  % (args.addr_hi, args.addr_lo, hi, lo,
                     'OV5640 OK' if ok else 'unexpected (check I2C)'))
            return 0 if ok else 2
        if args.cmd == 'rd':
            v = cam.read(args.addr)
            print('0x%04X = 0x%02X (%d)' % (args.addr, v, v))
            return 0
        if args.cmd == 'wr':
            cam.write(args.addr, args.data)
            return 0
        if args.cmd == 'flash':
            seq = FLASH_ON if args.state == 'on' else FLASH_OFF
            for a, d in seq:
                cam.write(a, d)
            print('cam3 fill-light %s' % args.state)
            return 0
        if args.cmd == 'testpat':
            cam.write(0x503d, 0x80 if args.state == 'on' else 0x00)
            print('cam3 test pattern %s' % args.state)
            return 0
    finally:
        drv.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
