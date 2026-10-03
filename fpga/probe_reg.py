import ctypes, os, fcntl, struct, mmap, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

PCI_MAP_ADDR_CMD = 0xC0000000 | (4 << 16) | (0x53 << 8) | 2
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

def snap(addr, n=256):
    op = DMA_OPERATION()
    op.offset_addr = 1024 * 1024
    op.ddr3_addr = addr
    op.total_length = N
    fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op, True)
    time.sleep(0.15)
    return bytes(rx[0:n])

def u32(buf, off):
    return struct.unpack('<I', buf[off:off+4])[0]

# cam1..4 寄存器窗: BASE 0x2000_0000, 步距 0x200; +0x30=dbg_cam_words, +0x50=dbg_hsyncs
BASES = [('cam1', 0x20000000), ('cam2', 0x20000200),
         ('cam3', 0x20000400), ('cam4', 0x20000600)]
s1 = {}
for n, b in BASES:
    s1[n] = snap(b, 256)
time.sleep(0.6)
s2 = {}
for n, b in BASES:
    s2[n] = snap(b, 256)

for n, b in BASES:
    w1, w2 = u32(s1[n], 0x30), u32(s2[n], 0x30)
    h1, h2 = u32(s1[n], 0x50), u32(s2[n], 0x50)
    print('%s words %10d -> %10d %s | hsyncs %d -> %d' %
          (n, w1, w2, 'STREAM' if w2 != w1 else 'static', h1, h2))
print('cam1 reg[0:16]:', s1['cam1'][:16].hex())
