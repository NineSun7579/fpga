import ctypes, os, fcntl, mmap, struct, signal, sys

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD  = IOWR(2)
PCI_DMA_READ_CMD  = IOWR(4)   # host -> FPGA
PCI_DMA_WRITE_CMD = IOWR(5)   # FPGA -> host

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32),
                ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32),
                ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32),
                ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class DmaTimeout(Exception):
    pass

def _on_alarm(s, f):
    raise DmaTimeout()

signal.signal(signal.SIGALRM, _on_alarm)

for c, sz in ((0, 4 * 1024 * 1024), (1, 4 * 1024 * 1024)):
    op = DMA_OPERATION(); op.cmd = c; op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)

TX = mmap.mmap(FD, 4 * 1024 * 1024, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, 4 * 1024 * 1024, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

def dma_read(fpga_addr, nbytes, tag):
    op = DMA_OPERATION()
    op.offset_addr = 0
    op.ddr3_addr = fpga_addr
    op.total_length = nbytes
    signal.alarm(8)
    try:
        r = fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op)
    except DmaTimeout:
        print(f'SAMPLE {tag} TIMEOUT', flush=True)
        return None
    except OSError as e:
        print(f'SAMPLE {tag} ERRNO{e.errno}', flush=True)
        return None
    finally:
        signal.alarm(0)
    seg = bytes(RX[0:nbytes])
    uniq = len(set(seg))
    best = 'none'
    for p in range(2, 257):
        ok = sum(1 for i in range(0, min(1024, len(seg)) - p) if seg[i] == seg[i + p])
        if ok > 0.95 * (min(1024, len(seg)) - p):
            best = p; break
    # 16 色统计 (RGB565 高字节)
    print(f'SAMPLE {tag} PASS nz={sum(1 for x in seg if x)}/{nbytes} uniq={uniq} period={best} head={seg[:32].hex()}', flush=True)
    return seg

for addr, tag in ((0x0, 'BUF1@0x0'), (0x003F4800, 'BUF2@0x3F4800')):
    dma_read(addr, 4096, tag)

for addr, tag in ((0x20000000, 'ACK'), (0x20000040, 'CAM_EN'),
                  (0x20000080, 'CAM_ADDR_1'), (0x200000C0, 'CAM_ADDR_2'),
                  (0x20000030, 'XDMA?0x30')):
    v = dma_read(addr, 16, tag)
    if v is not None:
        print(f'SAMPLE {tag} VALUE=0x{struct.unpack("<I", v[0:4])[0]:08X}', flush=True)
