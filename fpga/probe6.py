import ctypes, os, fcntl, struct, mmap, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD = 0xC0000000 | (4 << 16) | (0x53 << 8) | 2
PCI_DMA_READ_CMD = 0xC0000000 | (4 << 16) | (0x53 << 8) | 4
PCI_DMA_WRITE_CMD = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32),
                ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32),
                ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32),
                ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

for cmd, sz in ((0, 3 * 1024 * 1024), (1, 10 * 1024 * 1024)):
    op = DMA_OPERATION()
    op.cmd = cmd
    op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)

N = 4096
rx = mmap.mmap(FD, N, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

CAMS = [('cam1', 0x00800000), ('cam2', 0x00C00000), ('cam3', 0x01000000),
        ('cam4', 0x01400000), ('cam5', 0x01800000), ('cam6', 0x01C00000)]
TAG_OFF = 0x96000

def tag(base):
    op = DMA_OPERATION()
    op.offset_addr = 1024 * 1024
    op.ddr3_addr = base + TAG_OFF
    op.total_length = N
    fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op, True)
    time.sleep(0.15)
    return struct.unpack('<I', bytes(rx[0:4]))[0]

t1 = {n: tag(b) for n, b in CAMS}
time.sleep(1.0)
t2 = {n: tag(b) for n, b in CAMS}
print('tag     snap1     snap2   live')
for n, b in CAMS:
    print('%-5s  %08x  %08x  %s' % (n, t1[n], t2[n], 'YES' if t1[n] != t2[n] else 'no'))
