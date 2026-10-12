import ctypes, os, fcntl, mmap, signal, struct, time

class TO(Exception):
    pass

def _al(s, f):
    raise TO()

signal.signal(signal.SIGALRM, _al)
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def I(n):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | n

class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

for c, s in ((0, 4194304), (1, 4194304)):
    o = O(); o.cmd = c; o.ln = s
    signal.alarm(8); fcntl.ioctl(FD, I(2), o, True); signal.alarm(0)

TX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)

def wrr(a, v):
    TX[0:4] = struct.pack('<I', v)
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(4), o, True)
    except TO:
        return 'TO'
    finally:
        signal.alarm(0)
    return 'ok'

def rdd(a):
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    except TO:
        return None
    finally:
        signal.alarm(0)
    return struct.unpack('<I', bytes(RX[0:4]))[0]

# 使能两路
wrr(0x20000040, 1)
wrr(0x20000240, 1)
time.sleep(1.5)

offs = [0x00, 0x30, 0x34, 0x38, 0x3C, 0x40, 0x44, 0x48, 0x4C]
print('offset   CAM1(0x2000_00xx)   CAM2(0x2000_02xx)')
for off in offs:
    v1 = [rdd(0x20000000 + off) for _ in range(3)][-1]
    v2 = [rdd(0x20000200 + off) for _ in range(3)][-1]
    print('+0x%02X    0x%08X          0x%08X' % (off, v1 if v1 is not None else 0xDEAD,
                                                 v2 if v2 is not None else 0xDEAD))
os.close(FD)
print('REGCHK_DONE')
