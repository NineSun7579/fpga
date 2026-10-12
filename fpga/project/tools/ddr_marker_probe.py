#!/usr/bin/env python3
"""Plant 16B markers in each camera's DDR frame buffers, then check which get
overwritten by live frame DMA. A surviving marker == that buffer is NOT written."""
import ctypes, fcntl, mmap, os, struct, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
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
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

def wr16(a, words):
    TX[0:16] = b''.join(struct.pack('<I', w) for w in words)
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    fcntl.ioctl(FD, DR, o, True)

def rd16(a):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<4I', RX[0:16])

# (label, address, marker)
TARGETS = [
    ('cam1 ping 0x00800000', 0x00800000, 0xAAAA0001),
    ('cam1 pong 0x00A00000', 0x00A00000, 0xAAAA0002),
    ('cam2 ping 0x00C00000', 0x00C00000, 0xAAAA0003),
    ('cam2 pong 0x00E00000', 0x00E00000, 0xAAAA0004),
    ('cam3 ping 0x01000000', 0x01000000, 0xAAAA0005),
    ('cam3 pong 0x01200000', 0x01200000, 0xAAAA0006),
]
print('== plant markers ==', flush=True)
for lab, a, m in TARGETS:
    wr16(a, [m, m ^ 0xFFFFFFFF, m + 1, m + 2])
time.sleep(0.05)
print('== immediate readback ==', flush=True)
for lab, a, m in TARGETS:
    print('  %-22s %s' % (lab, ['%08X' % x for x in rd16(a)]), flush=True)
time.sleep(1.0)
print('== after 1.0s (live DMA) ==', flush=True)
for lab, a, m in TARGETS:
    got = rd16(a)
    survived = (got is not None and got[0] == m)
    print('  %-22s %s  -> %s' % (lab, ['%08X' % x for x in got],
          'NOT WRITTEN (marker survived)' if survived else 'overwritten by DMA'), flush=True)
os.close(FD)
print('DONE', flush=True)
