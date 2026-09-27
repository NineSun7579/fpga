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

for tag, base in (('cam1A', 0x00800000), ('cam2A', 0x00C00000)):
    d = rdd(base, FRAME)
    if d is None:
        print(tag, 'READ FAIL')
        continue
    best = None
    for y in range(40, 440, 2):
        row = [d[(y * W + x) * 2] | (d[(y * W + x) * 2 + 1] << 8) for x in range(W)]
        r5 = [(v >> 11) & 31 for v in row]
        g6 = [(v >> 5) & 63 for v in row]
        b5 = [v & 31 for v in row]
        g = [(r5[x] * 299 + g6[x] * 587 + b5[x] * 114) // 1000 for x in range(W)]
        m = sum(g) / W
        grad = sum(abs(g[x + 1] - g[x]) for x in range(W - 1)) / (W - 1)
        score = m - 4.0 * grad
        if m > 18 and (best is None or score > best[0]):
            best = (score, y, row, r5, g6, b5)
    if best is None:
        print(tag, 'no suitable row')
        continue
    _, y, row, r5, g6, b5 = best
    print('=== %s  row y=%d  (smooth+bright) ===' % (tag, y))
    print('words x0..47 : ' + ' '.join('%04X' % v for v in row[:48]))
    print('R5    x0..47 : ' + ' '.join('%2d' % v for v in r5[:48]))
    print('G6    x0..47 : ' + ' '.join('%2d' % v for v in g6[:48]))
    print('B5    x0..47 : ' + ' '.join('%2d' % v for v in b5[:48]))
    # period-4 phase check: mean of each residue class mod 4
    for name, arr in (('R5', r5), ('G6', g6), ('B5', b5)):
        ph = [sum(arr[x] for x in range(W) if x % 4 == r) / (W // 4) for r in range(4)]
        print('%s mod4 phase means: %s' % (name, ' '.join('%.2f' % p for p in ph)))
print('RAW_DONE')
