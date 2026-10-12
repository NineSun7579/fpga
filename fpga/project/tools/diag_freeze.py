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
mapped = False
try:
    for c in (0, 1):
        o = O(); o.cmd = c; o.total_length = BUF
        fcntl.ioctl(FD, MAP, o, True)
    mapped = True
except OSError as e:
    print('MAP failed (%s) - buffers owned by viewer; trying shared mmap' % e)
try:
    RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
                   flags=mmap.MAP_SHARED, offset=1024 * 1024)
    TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE)
except OSError as e:
    print('mmap failed:', e); os.close(FD); raise SystemExit(1)

def regr(a):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]

def regw(a, v):
    TX[0:16] = struct.pack('<I', v) + bytes(12)
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    fcntl.ioctl(FD, DR, o, True)

def bank(a, n=2048):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = n
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return bytes(RX[0:n])

print('== frozen-state diagnosis ==')
print('XDMA_REQ=0x%x ACK=0x%x CAM_EN-ish(0x40)=0x%x' % (
    regr(0x200000b0) or 0, regr(0x20000000) or 0, regr(0x20000040) or 0))
print('CAM_WORDS=0x%x BEAT_CNT=0x%x VSYNCS=0x%x' % (
    regr(0x20000030) or 0, regr(0x200000a0) or 0, regr(0x20000020) or 0))
a1 = bank(0x00800000)
time.sleep(3)
a2 = bank(0x00800000)
print('bank A1 changed over 3s:', a1 != a2, 'nz=%d/%d' % (sum(1 for x in a1 if x), len(a1)))
c1 = bank(0x00C00000)
time.sleep(3)
c2 = bank(0x00C00000)
print('bank C1 changed over 3s:', c1 != c2, 'nz=%d/%d' % (sum(1 for x in c1 if x), len(c1)))
print('post XDMA_REQ=0x%x CAM_WORDS=0x%x VSYNCS=0x%x' % (
    regr(0x200000b0) or 0, regr(0x20000030) or 0, regr(0x20000020) or 0))
print('== manual ACK=3 ==')
regw(0x20000000, 3)
time.sleep(3)
b1 = bank(0x00800000); time.sleep(3); b2 = bank(0x00800000)
print('after ACK bank A1 changed:', b1 != b2)
print('post2 XDMA_REQ=0x%x CAM_WORDS=0x%x VSYNCS=0x%x' % (
    regr(0x200000b0) or 0, regr(0x20000030) or 0, regr(0x20000020) or 0))
os.close(FD)
print('DIAG_DONE')
