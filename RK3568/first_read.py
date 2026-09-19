import ctypes, os, fcntl, mmap, struct, time, signal, sys

# 每次全新驱动加载后, 首读是可靠的; 每个寄存器单独一轮
TARGET = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x2000003C

class TO(Exception): pass
def _al(s, f): raise TO()
signal.signal(signal.SIGALRM, _al)

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
I = lambda n: 0xC0000000 | (4 << 16) | (0x53 << 8) | n
class O(ctypes.Structure):
    _fields_ = [('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),
                ('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
op = O(); op.cmd=0; op.ln=4194304
signal.alarm(4)
try:
    fcntl.ioctl(FD, I(2), op, True)
finally:
    signal.alarm(0)
op = O(); op.cmd=1; op.ln=4194304
signal.alarm(4)
try:
    fcntl.ioctl(FD, I(2), op, True)
finally:
    signal.alarm(0)
TX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ|mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ|mmap.PROT_WRITE, flags=mmap.MAP_SHARED, offset=1048576)

o = O(); o.off=0; o.ddr=TARGET; o.ln=16
signal.alarm(4)
try:
    fcntl.ioctl(FD, I(5), o, True)
finally:
    signal.alarm(0)
val = struct.unpack('<I', RX[0:4])[0]
print('FIRST_READ 0x%X = 0x%08X' % (TARGET, val))
os.close(FD)
