import ctypes, fcntl, mmap, os, struct, time
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

def bank(a, n=4096):
    o = O(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = n
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return bytes(RX[0:n])

regw(0x20000080, 0x00800000); regw(0x200000c0, 0x00A00000)
regw(0x20000000, 3)
regw(0x20000040, 0); regw(0x20000040, 1)
addrs = {'A1': 0x00800000, 'A2': 0x00A00000, 'C1': 0x00C00000, 'C2': 0x00E00000}
prev = {}
for i in range(12):
    regw(0x20000000, 3)
    line = '[%2d]' % i
    for k, a in addrs.items():
        cur = bank(a)
        if k in prev and prev[k] is not None and cur is not None and cur != prev[k]:
            ch = 'CHG'
        elif cur is not None and sum(1 for x in cur if x) > 100 and k not in prev:
            ch = 'NEW'
        else:
            ch = '...'
        nz = sum(1 for x in (cur or b'') if x)
        line += ' %s:%s nz=%4d' % (k, ch, nz)
        prev[k] = cur
    print(line, flush=True)
    time.sleep(1)
os.close(FD)
print('ALLBANK_DONE', flush=True)
