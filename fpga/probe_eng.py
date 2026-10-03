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

# cam1 引擎内部状态: +0x30 words, +0x20 vsyncs, +0x50 sticky, +0x60 {wd_cnt,state,cmd_cnt},
#                   +0xa0 beat_cnt, +0xf0 beat_last, +0x70 sys
regs = [('words', 0x30), ('vsyncs', 0x20), ('sticky', 0x50), ('i2c/state', 0x60),
        ('beat_cnt', 0xa0), ('beat_last', 0xf0), ('sys', 0x70)]
print('cam1 engine state:')
for n, off in regs:
    print('  %-9s %s' % (n, hex(regr(0x20000000 + off)) if regr(0x20000000 + off) is not None else 'TO'))
