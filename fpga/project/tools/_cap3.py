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


def saveppm(base, path):
    d = rdd(base, FRAME)
    if d is None:
        print(path, 'READ FAIL')
        return None
    px = bytearray()
    for i in range(0, FRAME, 2):
        v = d[i] | (d[i + 1] << 8)
        r = (v >> 11) & 0x1f
        g = (v >> 5) & 0x3f
        b = v & 0x1f
        px += bytes((((r << 3) | (r >> 2)), ((g << 2) | (g >> 4)), ((b << 3) | (b >> 2))))
    with open(path, 'wb') as f:
        f.write(b'P6\n%d %d\n255\n' % (W, H))
        f.write(bytes(px))
    return bytes(px)


def gray3(px, x, y):
    o = (y * W + x) * 3
    return (px[o] * 299 + px[o + 1] * 587 + px[o + 2] * 114) // 1000


def mir8(x):
    return (x & ~7) | (7 - (x & 7))


def metrics(name, px):
    sm = sa = s4 = s8 = 0
    n = 0
    cr = cf = 0.0
    m = 0
    cm = [0.0] * W
    for y in range(H):
        g = [gray3(px, x, y) for x in range(W)]
        for x in range(W):
            cm[x] += g[x]
        if y % 2:
            continue
        for x in range(8, W - 8):
            sm += abs(g[mir8(x)] - g[x])
            sa += abs(g[x + 1] - g[x])
            s4 += abs(g[x + 4] - g[x])
            s8 += abs(g[x + 8] - g[x])
            n += 1
        for k in range(W // 8):
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
    cm = [v / H for v in cm]
    mu = sum(cm) / W
    cm = [v - mu for v in cm]
    var = sum(v * v for v in cm)
    ac = ['%+.3f' % (sum(cm[x] * cm[x + p] for x in range(W - p)) / var) for p in range(1, 17)]
    print('%-6s mir8=%6.3f  dx1=%6.3f  dx4=%6.3f  dx8=%6.3f  corr_rev=%+.4f corr_fwd=%+.4f n=%d'
          % (name, sm / n, sa / n, s4 / n, s8 / n, cr / m, cf / m, m))
    print('       colprof autocorr 1..16: %s' % ' '.join(ac))


for nm, base, path in (('cam1A', 0x00800000, '/tmp/c1a.ppm'), ('cam1B', 0x00A00000, '/tmp/c1b.ppm'),
                       ('cam2A', 0x00C00000, '/tmp/c2a.ppm'), ('cam2B', 0x00E00000, '/tmp/c2b.ppm')):
    px = saveppm(base, path)
    if px:
        metrics(nm, px)
print('CAP3_DONE')
