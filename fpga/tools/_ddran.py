import ctypes, fcntl, mmap, signal, struct, os

DEV = '/dev/pango_pci_driver'
FULL = 0x96000          # 640*480*2
W, H = 640, 480
ROW = W * 2

class TO(Exception):
    pass

def _al(s, f):
    raise TO()

signal.signal(signal.SIGALRM, _al)
FD = os.open(DEV, os.O_RDWR | os.O_SYNC)

def I(n):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | n

class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

for c, s in ((0, 4194304), (1, 4194304)):
    o = O(); o.cmd = c; o.ln = s
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(2), o, True)
    except OSError as e:
        print('alloc %d: %s (reuse existing buffer)' % (c, e))
    except TO:
        print('alloc %d: timeout (reuse existing buffer)' % c)
    finally:
        signal.alarm(0)

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

def g6(v):
    return (v >> 5) & 0x3F

def analyze(name, base):
    row0, nrows = 200, 8
    d = rdd(base + row0 * ROW, ROW * nrows)
    if d is None:
        print('%s READ FAIL' % name); return
    t1 = rdd(base + FULL, 16)
    t2 = rdd(base + FULL, 16)
    tag1 = struct.unpack('<I', t1[:4])[0] if t1 else -1
    tag2 = struct.unpack('<I', t2[:4])[0] if t2 else -1
    rows = [[d[r * ROW + 2 * i] | (d[r * ROW + 2 * i + 1] << 8) for i in range(W)]
            for r in range(nrows)]
    print('%s base=0x%08X tag=%d/%d' % (name, base, tag1, tag2))
    mid = rows[nrows // 2]
    print('  raw16 first 48 :', ' '.join('%5d' % v for v in mid[:24]))
    print('  G6    first 72 :', ' '.join('%3d' % g6(v) for v in mid[:72]))
    print('  G6 row+1 first72:', ' '.join('%3d' % g6(v) for v in rows[nrows // 2 + 1][:72]))
    for p in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16):
        s = 0; c = 0
        for vals in rows:
            g = [g6(v) for v in vals]
            for i in range(W - p):
                s += abs(g[i + p] - g[i]); c += 1
        print('  shift %2d : mean|dG6| = %6.3f' % (p, s / c))
    # column-average of G6 across all 8 rows -> look for a repeating column pattern
    colavg = [sum(g6(rows[r][i]) for r in range(nrows)) / nrows for i in range(64)]
    print('  colavg G6[0:64]:', ' '.join('%4.1f' % v for v in colavg))

analyze('CAM1(KF) ', 0x00800000)
analyze('CAM2(raw)', 0x00C00000)
os.close(FD)
print('AN_DONE')
