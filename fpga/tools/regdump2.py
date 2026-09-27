import ctypes, fcntl, mmap, os, struct, time
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
MAP, DR, DW = IOWR(2), IOWR(4), IOWR(5)
class O(ctypes.Structure):
    _fields_ = [('current_len', ctypes.c_uint32), ('offset_addr', ctypes.c_uint32),
                ('cmd', ctypes.c_uint32), ('ddr3_addr', ctypes.c_uint32),
                ('total_length', ctypes.c_uint32), ('read_buf', ctypes.c_void_p),
                ('write_buf', ctypes.c_void_p)]
BUF = 4*1024*1024
for c in (0, 1):
    o = O(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024*1024)

def regw(a, v):
    TX[0:16] = struct.pack('<I', v) + bytes(12)
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    return fcntl.ioctl(FD, DR, o, True)

def regr(a):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]

NAMES = [(0x00, 'ACK   '), (0x10, 'PCLK  '), (0x20, 'VSYNCS'), (0x30, 'CAMWRD'),
         (0x50, 'ZDIN  '), (0x60, 'I2CID '), (0x70, 'SYS   '), (0x90, 'ZOUT  '),
         (0xa0, 'BEAT  '), (0xb0, 'XDMARE'), (0xd0, 'AXINOW'), (0xe0, 'VSYNC2'),
         (0xf0, 'BEATL '), (0x130,'PIPEST'), (0x170,'TS0   ')]
for base, tag in ((0x20000000, 'CAM1'), (0x20000200, 'CAM2')):
    print('== %s (0x%08x) ==' % (tag, base), flush=True)
    s1 = {}
    for off, nm in NAMES:
        s1[off] = regr(base + off)
    time.sleep(1.0)
    for off, nm in NAMES:
        v2 = regr(base + off)
        d = (v2 - s1[off]) & 0xFFFFFFFF if (v2 is not None and s1[off] is not None) else -1
        print('  %s 0x%08x -> 0x%08x  d=%d' % (nm, s1[off] or 0, v2 or 0, d), flush=True)
os.close(FD)
print('REGDUMP_DONE', flush=True)
