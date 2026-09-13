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

# map TX(3MB, cmd0) + RX(10MB, cmd1)
for cmd, sz in ((0, 3 * 1024 * 1024), (1, 10 * 1024 * 1024)):
    op = DMA_OPERATION()
    op.cmd = cmd
    op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)

N = 4096
rx = mmap.mmap(FD, N, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

def snap(addr):
    op = DMA_OPERATION()
    op.offset_addr = 1024 * 1024
    op.ddr3_addr = addr
    op.total_length = N
    fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op, True)
    time.sleep(0.2)
    return bytes(rx[0:256])

s1 = snap(0x0)
time.sleep(0.5)
s2 = snap(0x0)
print('snap1 head:', s1[:32].hex())
print('snap2 head:', s2[:32].hex())
print('changed:', s1 != s2)
print('nonzero bytes:', sum(1 for b in s1 if b), '/', len(s1))
