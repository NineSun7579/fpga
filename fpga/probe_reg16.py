import ctypes, os, fcntl, struct, mmap, time, signal

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
MAP = 0xC0000000 | (4 << 16) | (0x53 << 8) | 2
DW  = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5   # DDR->host (snap)
DR  = 0xC0000000 | (4 << 16) | (0x53 << 8) | 4   # host->DDR (write)

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32),
                ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32),
                ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32),
                ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

BUF = 4 * 1024 * 1024
for c in (0, 1):
    op = DMA_OPERATION(); op.cmd = c; op.total_length = BUF
    fcntl.ioctl(FD, MAP, op, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED, offset=1024 * 1024)

class TO(Exception): pass
def _h(s, f): raise TO()
signal.signal(signal.SIGALRM, _h)

def dma(nr, op, tmo=4):
    signal.alarm(tmo)
    try: return fcntl.ioctl(FD, nr, op, True)
    finally: signal.alarm(0)

def regr(a):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = a; op.total_length = 16
    try:
        dma(DW, op); time.sleep(0.02)
        return struct.unpack('<I', RX[0:4])[0]
    except TO: return None

BASES = [('cam1', 0x20000000), ('cam2', 0x20000200), ('cam3', 0x20000400), ('cam4', 0x20000600)]
print('cam  words#1    words#2    stream | ack/err')
for n, b in BASES:
    w1 = regr(b + 0x30); time.sleep(0.4); w2 = regr(b + 0x30)
    e  = regr(b + 0x0C)
    st = 'STREAM' if (w1 is not None and w2 is not None and w2 != w1) else 'static'
    print('%s  %10s %10s  %-6s | %s' % (n, w1, w2, st, hex(e) if e is not None else 'TO'))
# DDR 帧区 16B 读 (对照: 六路固件上 4KB 读曾挂)
def ddrread(a):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = a; op.total_length = 16
    try:
        dma(DW, op); time.sleep(0.02)
        return RX[0:16].hex()
    except TO: return 'TIMEOUT'
for n, b in [('cam1', 0x00800000), ('cam5', 0x01800000)]:
    print(n, 'frame16:', ddrread(b))
