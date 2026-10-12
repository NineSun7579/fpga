import ctypes, os, fcntl, mmap, struct, signal, time

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
        pass
    finally:
        signal.alarm(0)

def rd32(a):
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    except TO:
        return -1
    finally:
        signal.alarm(0)
    return struct.unpack('<I', bytes(RX[0:4]))[0]

# tag candidates: cam1@frame(640x480)=0x00896000, cam1@frame(720p)=0x009C2000,
#                 cam2@frame(640x480)=0x00C96000, cam2@frame(720p)=0x00DC2000
addrs = [('c1@96000', 0x00896000), ('c1@9C2000', 0x009C2000),
         ('c2@C96000', 0x00C96000), ('c2@DC2000', 0x00DC2000)]

for k in range(12):
    wrr(0x20000000, 3)
    wrr(0x20000200, 3)
    time.sleep(0.6)
    row = ' '.join('%s=%10d' % (n, rd32(a)) for n, a in addrs)
    print('t%02d %s' % (k, row))
os.close(FD)
print('TAGPOLL_DONE')
