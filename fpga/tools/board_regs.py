import ctypes, os, fcntl, mmap, struct, time
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
MAP = IOWR(2); DR = IOWR(4); DW = IOWR(5)


class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


BUF = 4 * 1024 * 1024
for c in (0, 1):
    o = DMA_OPERATION(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)


def regr(a):
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    r = fcntl.ioctl(FD, DW, o, True)
    if r != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]


REGS = [('PCLK_CNT', 0x20000010), ('VSYNCS', 0x20000020), ('CAM_WORDS', 0x20000030),
        ('I2C_ID', 0x20000060), ('SYS', 0x20000070), ('HREF_RAW', 0x20000090),
        ('BEAT_CNT', 0x200000a0), ('XDMA_REQ', 0x200000b0), ('AXI_NOW', 0x200000d0),
        ('VSYNC_RAW', 0x200000e0), ('BEAT_LAST', 0x200000f0)]
print('--- sample 1 ---')
s1 = {}
for n, a in REGS:
    v = regr(a)
    s1[n] = v
    print('%-10s @0x%08X = %s' % (n, a, ('0x%08X (%d)' % (v, v)) if v is not None else 'X'))
time.sleep(1.5)
print('--- sample 2 (+1.5s) ---')
for n, a in REGS:
    v = regr(a)
    d = '' if (v is None or s1[n] is None) else ('  d=%+d' % (v - s1[n]))
    print('%-10s = %s%s' % (n, ('0x%08X (%d)' % (v, v)) if v is not None else 'X', d))
os.close(FD)
print('DONE')
