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

CAMS = [('cam1', 0x00800000), ('cam2', 0x00C00000), ('cam3', 0x01000000),
        ('cam4', 0x01400000), ('cam5', 0x01800000), ('cam6', 0x01C00000)]
for n, b in CAMS:
    s = snap(b, 64)
    nz = sum(1 for x in s if x)
    print('%s frame@%08x nonzero=%3d/64  %s' % (n, b, nz, s[:16].hex()))
# 主机 DMA 写测试: 向 0x0300_0000 空闲区写 256B 再读回
PCI_DMA_READ_CMD = 0xC0000000 | (4 << 16) | (0x53 << 8) | 4
tx = mmap.mmap(FD, N, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=0)
pat = bytes(range(256))
tx[0:256] = pat
op = DMA_OPERATION()
op.offset_addr = 0
op.ddr3_addr = 0x03000000
op.total_length = N
try:
    fcntl.ioctl(FD, PCI_DMA_READ_CMD, op, True)
    time.sleep(0.2)
    back = snap(0x03000000, 256)
    ok = back[:256] == pat
    print('host DMA write/readback:', 'OK' if ok else 'MISMATCH %s' % back[:16].hex())
except Exception as e:
    print('host DMA write FAILED:', e)
