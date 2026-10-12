import ctypes, fcntl, mmap, os, struct, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
MAP, DR, DW = IOWR(2), IOWR(4), IOWR(5)

class O(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

BUF = 4 * 1024 * 1024
for c in (0, 1):
    o = O(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

def regw(a, v):
    TX[0:16] = struct.pack('<I', v) + bytes(12)
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    return fcntl.ioctl(FD, DR, o, True)

def regr(a):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]

def bank(a, n=4096):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = n
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return bytes(RX[0:n])

print('== init cameras (no viewer) ==', flush=True)
A1, A2 = 0x00800000, 0x00A00000
print(' wr: addr1=%s addr2=%s ack=%s' % (
    regw(0x20000080, A1), regw(0x200000c0, A2), regw(0x20000000, 3)), flush=True)
print(' rb: addr1=0x%x addr2=0x%x' % (regr(0x20000080) or 0, regr(0x200000c0) or 0), flush=True)
regw(0x20000040, 0); regw(0x20000040, 1)
print(' rb: cam_en=0x%x' % (regr(0x20000040) or 0), flush=True)

print('== watch banks 30 x 1s (ACK each second) ==', flush=True)
prev = None
for i in range(30):
    regw(0x20000000, 3)  # ACK both
    cur = bank(A1)
    ch = 'CHANGED' if (prev is not None and cur != prev) else 'same'
    nz = sum(1 for x in (cur or b'') if x)
    print(' [%2d] A1 %s nz=%4d XDMA_REQ=0x%x CAM_WORDS=0x%x VSYNCS=0x%x' % (
        i, ch, nz, regr(0x200000b0) or 0, regr(0x20000030) or 0,
        regr(0x20000020) or 0), flush=True)
    prev = cur
    time.sleep(1)
os.close(FD)
print('WATCH_DONE', flush=True)
