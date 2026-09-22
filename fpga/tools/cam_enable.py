#!/usr/bin/env python3
"""Set the two FPGA camera DMA enable bits through the RK3568 PCIe driver."""
import argparse, ctypes, fcntl, mmap, os, signal, struct

class Timeout(Exception):
    pass
def alarm_handler(_signum, _frame):
    raise Timeout()
signal.signal(signal.SIGALRM, alarm_handler)

class DmaOp(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]
def ioctl_code(number):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | number
MAP_CMD=ioctl_code(2)
H2F_CMD=ioctl_code(4)
F2H_CMD=ioctl_code(5)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cam1', type=int, choices=(0,1), default=1)
    ap.add_argument('--cam2', type=int, choices=(0,1), default=1)
    args=ap.parse_args()
    fd=os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
    try:
        for mapping in (0,1):
            op=DmaOp(); op.cmd=mapping; op.total_length=4*1024*1024
            signal.alarm(8); fcntl.ioctl(fd, MAP_CMD, op, True); signal.alarm(0)
        tx=mmap.mmap(fd, 4*1024*1024, prot=mmap.PROT_READ|mmap.PROT_WRITE,
                      flags=mmap.MAP_SHARED)
        def write32(address, value):
            tx[0:4]=struct.pack('<I', value)
            op=DmaOp(); op.offset_addr=0; op.ddr3_addr=address; op.total_length=16
            signal.alarm(8)
            try:
                fcntl.ioctl(fd, H2F_CMD, op, True)
            finally:
                signal.alarm(0)
        write32(0x20000040, args.cam1)
        write32(0x20000240, args.cam2)
        print('CAM_EN cam1=%d cam2=%d' % (args.cam1, args.cam2), flush=True)
    finally:
        os.close(fd)
if __name__ == '__main__':
    main()
