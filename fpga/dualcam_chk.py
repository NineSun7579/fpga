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

RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1048576)

def rdd(a, n):
    o = O(); o.off = 0; o.ddr = a; o.ln = n
    signal.alarm(25)
    try:
        fcntl.ioctl(FD, I(5), o, True)
    except TO:
        return None
    finally:
        signal.alarm(0)
    return bytes(RX[0:n])

FRAME = 1280 * 720 * 2
TAG = 1280 * 720 * 2  # tag sits at base + frame bytes

def stat(name, base):
    d = rdd(base, 262144)
    if d is None:
        print('%s READ FAIL' % name); return
    nz = sum(1 for b in d if b)
    vals = {}
    for i in range(0, len(d), 2):
        v = d[i] | (d[i + 1] << 8)
        vals[v] = vals.get(v, 0) + 1
    s = 0
    for v, c in vals.items():
        s += v * c
    n = len(d) // 2
    # transitions across the first scanline (1280 px)
    row = [d[i] | (d[i + 1] << 8) for i in range(0, 1280 * 2, 2)]
    tr = sum(1 for a, b in zip(row, row[1:]) if a != b)
    tg = rdd(base + TAG, 16)
    tval = struct.unpack('<I', tg[:4])[0] if tg else None
    top = sorted(vals.items(), key=lambda kv: -kv[1])[:3]
    print('%-6s base=0x%08X nz=%d/%d distinct=%d mean=%d row_trans=%d/1279 tag=%s top3=%s'
          % (name, base, nz, len(d), len(vals), s // n, tr, tval,
             ['%04X:%d' % (v, c) for v, c in top]))

print('--- CAM1 ---')
stat('A1', 0x00800000)
stat('B1', 0x00A00000)
print('--- CAM2 ---')
stat('A2', 0x00C00000)
stat('B2', 0x00E00000)
os.close(FD)
print('DUALCHK_DONE')
