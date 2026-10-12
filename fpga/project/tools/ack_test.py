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


def regw(a, v):
    TX[0:16] = struct.pack('<I', v) + bytes(12)
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    fcntl.ioctl(FD, DR, o, True)


def regr(a):
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]


def irqs():
    d = {}
    for l in open('/proc/interrupts'):
        if 'pango' in l:
            p = l.split()
            d[p[-1]] = sum(int(x) for x in p[1:] if x.isdigit())
    return d


A1, A2 = 0x00800000, 0x00A00000
print('== ack-and-read loop (A1=0x%08X A2=0x%08X) ==' % (A1, A2), flush=True)
print('  pre: A1=%s A2=%s irq0=%s' % ((bytes(RX[0:0]) or b'').hex() or '-', '-', irqs().get('pango_pci_driver_irq0', -1)), flush=True)
prev = None
for i in range(40):
    regw(0x20000000, 3)          # ACK both buffers
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = A1; o.total_length = 4096
    fcntl.ioctl(FD, DW, o, True); a = bytes(RX[0:32])
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = A2; o.total_length = 4096
    fcntl.ioctl(FD, DW, o, True); b = bytes(RX[0:32])
    ch = (prev is not None and a != prev)
    nz = sum(1 for x in a if x)
    print('  [%2d] nzA=%3d %s A=%s | B=%s | irq0=%d' % (
        i, nz, 'CHANGED' if ch else 'same', a[:8].hex(), b[:8].hex(),
        irqs().get('pango_pci_driver_irq0', -1)), flush=True)
    prev = a
    time.sleep(0.2)
print('DEBUG axinum/beats:', hex(regr(0x200000d0) or 0), hex(regr(0x200000a0) or 0), hex(regr(0x200000f0) or 0), flush=True)
os.close(FD)
print('DONE', flush=True)
