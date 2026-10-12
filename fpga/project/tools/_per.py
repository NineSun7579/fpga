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


def chan(d, x, y, sh):
    o = (y * W + x) * 2
    v = d[o] | (d[o + 1] << 8)
    return (v >> sh) & (0x1f if sh in (0, 11) else 0x3f)


def analyse(name, base):
    d = rdd(base, FRAME)
    if d is None:
        print(name, 'READ FAIL')
        return
    for ch, sh in (('R', 11), ('G', 5), ('B', 0)):
        acc = [0.0] * 21
        cnt = 0
        for y in range(0, H, 4):
            g = [chan(d, x, y, sh) for x in range(W)]
            # high-pass: remove an 11-tap box so only fine detail remains
            hp = [0.0] * W
            for x in range(5, W - 5):
                s = 0
                for k in range(-5, 6):
                    s += g[x + k]
                hp[x] = g[x] - s / 11.0
            for p in range(1, 21):
                s = 0.0
                n = 0
                for x in range(5, W - 5 - p):
                    s += hp[x] * hp[x + p]
                    n += 1
                acc[p] += s / n
            cnt += 1
        print('%-6s %s high-pass autocorr 1..20: %s'
              % (name, ch, ' '.join('%+.2f' % (acc[p] / cnt) for p in range(1, 21))))


for nm, base in (('cam1A', 0x00800000), ('cam1B', 0x00A00000),
                 ('cam2A', 0x00C00000), ('cam2B', 0x00E00000)):
    analyse(nm, base)
print('PER_DONE')
