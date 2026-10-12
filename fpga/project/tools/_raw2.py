import ctypes
import fcntl
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
    except Exception:
        pass
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


def words(d, y, x0, n):
    return [d[(y * W + x0 + i) * 2] | (d[(y * W + x0 + i) * 2 + 1] << 8) for i in range(n)]


for tag, base in (('cam1A', 0x00800000), ('cam2A', 0x00C00000)):
    d = rdd(base, FRAME)
    if d is None:
        print(tag, 'READ FAIL')
        continue
    best = None
    for y in range(20, 460, 1):
        for x0 in range(0, W - 64, 16):
            ws = words(d, y, x0, 64)
            lo, hi = min(ws), max(ws)
            rng = hi - lo
            g = [((w >> 11) & 31) * 299 + ((w >> 5) & 63) * 587 + (w & 31) * 114 for w in ws]
            g = [v // 1000 for v in g]
            m = sum(g) / 64.0
            if m < 30:
                continue
            score = m - 40.0 * rng
            if best is None or score > best[0]:
                best = (score, y, x0, ws, rng, m)
    if best is None:
        print(tag, 'no flat bright run')
        continue
    _, y, x0, ws, rng, m = best
    print('=== %s  FLAT bright run  y=%d x0=%d  range=%d  meanlum=%.1f ===' % (tag, y, x0, rng, m))
    print('idx  x   word   R5 G6 B5   bits15..0')
    for i, w in enumerate(ws[:40]):
        print('%3d %4d  %04X   %2d %2d %2d   %016s' % (
            i, x0 + i, w, (w >> 11) & 31, (w >> 5) & 63, w & 31,
            format(w, '016b')))
    # mod-4 residual relative to local median of 9
    med = sorted(ws)[len(ws) // 2]
    print('mode/median word = %04X' % med)
    print('delta from median: ' + ' '.join('%+d' % (w - med) for w in ws[:40]))
    for name, sh, mk in (('R5', 11, 31), ('G6', 5, 63), ('B5', 0, 31)):
        arr = [(w >> sh) & mk for w in ws]
        ph = [sum(arr[x] for x in range(64) if x % 4 == r) / 16.0 for r in range(4)]
        print('%s mod4 means: %s   (spread=%.2f)' % (name, ' '.join('%.2f' % p for p in ph), max(ph) - min(ph)))
print('RAW2_DONE')
