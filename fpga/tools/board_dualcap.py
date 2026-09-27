#!/usr/bin/env python3
# Read back DDR camera frames via the bulk descriptor path (ioctl 5), the same
# path detview uses.  Reads cam1 (KF output) and cam2 (raw bypass) frames so the
# temporal filter can be compared against an identical-lighting control.
import ctypes, os, fcntl, mmap, signal, sys


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


# allocate both descriptor buffers (same as rawchk.py)
for c, s in ((0, 4194304), (1, 4194304)):
    o = O(); o.cmd = c; o.ln = s
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, I(2), o, True)
    except TO:
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


def save(base, name):
    d = rdd(base, FRAME)
    if d is None:
        print(name, 'READ FAIL')
        return
    px = bytearray()
    nz = 0
    acc = 0
    for i in range(0, FRAME, 2):
        v = d[i] | (d[i + 1] << 8)
        if v:
            nz += 1
        r = (v >> 11) & 0x1f
        g = (v >> 5) & 0x3f
        b = v & 0x1f
        acc += g
        px += bytes((((r << 3) | (r >> 2)), ((g << 2) | (g >> 4)), ((b << 3) | (b >> 2))))
    with open('/tmp/%s.ppm' % name, 'wb') as f:
        f.write(b'P6\n%d %d\n255\n' % (W, H)); f.write(bytes(px))
    print('%s base=0x%08X nz=%d/%d meanG6=%.3f' % (name, base, nz, W * H, acc / float(W * H)))


save(0x00800000, 'cam1_kf')
save(0x00C00000, 'cam2_raw')
print('DONE')
