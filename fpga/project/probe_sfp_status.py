import ctypes, os, fcntl, struct, mmap, time, signal

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
MAP = 0xC0000000 | (4 << 16) | (0x53 << 8) | 2
DW  = 0xC0000000 | (4 << 16) | (0x53 << 8) | 5

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
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED, offset=1024 * 1024)

class TO(Exception): pass
def _h(s, f): raise TO()
signal.signal(signal.SIGALRM, _h)

def regr(a):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = a; op.total_length = 16
    signal.alarm(4)
    try:
        fcntl.ioctl(FD, DW, op, True); time.sleep(0.02)
        return struct.unpack('<I', RX[0:4])[0]
    except TO: return None
    finally: signal.alarm(0)

for i in range(5):
    v = regr(0x20000144)
    if v is None:
        print('READ TIMEOUT'); break
    print('SFP_STATUS[%d] = 0x%X  (pll1=%d txdone=%d rxdone=%d pcs=%d)' %
          (i, v, v & 1, (v >> 1) & 1, (v >> 2) & 1, (v >> 3) & 1))
    time.sleep(1.5)
