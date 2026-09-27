import ctypes, fcntl, mmap, os, struct, sys, time
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
MAP, DR, DW = IOWR(2), IOWR(4), IOWR(5)
class O(ctypes.Structure):
    _fields_ = [('current_len', ctypes.c_uint32), ('offset_addr', ctypes.c_uint32),
                ('cmd', ctypes.c_uint32), ('ddr3_addr', ctypes.c_uint32),
                ('total_length', ctypes.c_uint32), ('read_buf', ctypes.c_void_p),
                ('write_buf', ctypes.c_void_p)]
BUF = 4*1024*1024
for c in (0, 1):
    o = O(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024*1024)

def regw(a, v):
    TX[0:16] = struct.pack('<I', v) + bytes(12)
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    return fcntl.ioctl(FD, DR, o, True)

def regr(a):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<I', RX[0:4])[0]

step = sys.argv[1] if len(sys.argv) > 1 else 'all'
print('step:', step, flush=True)
print('1. cam1 vsyncs read:', hex(regr(0x20000020) or 0), flush=True)
if step >= '2':
    print('2. cam3 vsyncs read:', hex(regr(0x20000420) or 0), flush=True)
if step >= '3':
    print('3. cam3 en write rc:', regw(0x20000440, 1), flush=True)
    print('   cam3 en read:', hex(regr(0x20000440) or 0), flush=True)
if step >= '4':
    print('4. cam3 ack write rc:', regw(0x20000400, 3), flush=True)
    b1 = None
    o = O(); o.offset_addr = 0; o.ddr3_addr = 0x01000000; o.total_length = 4096
    rc = fcntl.ioctl(FD, DW, o, True)
    b1 = bytes(RX[0:64])
    print('   cam3 bank read rc:', rc, 'first16:', b1[:16].hex(), flush=True)
print('STEP_DONE', step, flush=True)
os.close(FD)
