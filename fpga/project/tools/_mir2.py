import ctypes
import fcntl
import math
import mmap
import os
import signal


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
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(2), o, True)
    except Exception as e:
        print('alloc %d: %s' % (c, e))
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


W, H = 640, 480
FRAME = W * H * 2


def gray(d, x, y):
    o = (y * W + x) * 2
    v = d[o] | (d[o + 1] << 8)
    r = (v >> 11) & 0x1f
    g = (v >> 5) & 0x3f
    b = v & 0x1f
    return (r * 299 * 255 // 31 + g * 587 * 255 // 63 + b * 114 * 255 // 31) // 1000


def mir(x):
    return (x & ~7) | (7 - (x & 7))


def metric(name, base):
    d = rdd(base, FRAME)
    if d is None:
        print('%s READ FAIL' % name)
        return
    cr = cf = 0.0
    m = 0
    sm = sa = 0
    n = 0
    tot = 0
    for i in range(0, FRAME, 2):
        tot += (d[i] | (d[i + 1] << 8)) >> 5 & 0x3f
    for y in range(0, H, 3):
        g = [gray(d, x, y) for x in range(W)]
        for x in range(8, W - 8):
            sm += abs(g[mir(x)] - g[x])
            sa += abs(g[x + 1] - g[x])
            n += 1
        for k in range(0, W // 8):
            a = g[8 * k:8 * k + 4]
            b = g[8 * k + 4:8 * k + 8]
            ma = sum(a) / 4.0
            mb = sum(b) / 4.0
            da = sum((v - ma) ** 2 for v in a)
            db = sum((v - mb) ** 2 for v in b)
            if da < 4 or db < 4:
                continue
            br = b[::-1]
            cr += sum((a[j] - ma) * (br[j] - mb) for j in range(4)) / math.sqrt(da * db)
            cf += sum((a[j] - ma) * (b[j] - mb) for j in range(4)) / math.sqrt(da * db)
            m += 1
    print('%-11s base=0x%08X meanG6=%5.2f |g[mir]-g|=%6.3f |g[x+1]-g|=%6.3f '
          'corr_rev=%+.4f corr_fwd=%+.4f n=%d'
          % (name, base, tot / float(W * H), sm / float(n), sa / float(n), cr / m, cf / m, m))


for nm, bs in (('cam1_bankA', 0x00800000), ('cam1_bankB', 0x00A00000),
               ('cam2_bankA', 0x00C00000), ('cam2_bankB', 0x00E00000)):
    metric(nm, bs)

os.close(FD)
print('MIR2_DONE')
