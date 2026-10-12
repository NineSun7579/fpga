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

def stat(name, base, framebytes):
    d = rdd(base, 262144)
    if d is None:
        print('%s READ FAIL' % name); return
    vals = {}
    for i in range(0, len(d), 2):
        v = d[i] | (d[i + 1] << 8)
        vals[v] = vals.get(v, 0) + 1
    n = len(d) // 2
    s = sum(v * c for v, c in vals.items())
    row = [d[i] | (d[i + 1] << 8) for i in range(0, 1280 * 2, 2)]
    tr = sum(1 for a, b in zip(row, row[1:]) if a != b)
    tg = rdd(base + framebytes, 16)
    tv = struct.unpack('<I', tg[:4])[0] if tg else None
    print('%-4s distinct=%d mean=%d row_trans=%d/1279 tag=%s' % (name, len(vals), s // n, tr, tv))

# 使能两路 + 释放两缓冲, 让引擎自由写若干帧
for _ in range(8):
    wrr(0x20000000, 3)
    wrr(0x20000200, 3)
    time.sleep(0.7)

print('--- CAM1 (640x480 frame=0x96000 / 720p frame=0x1C2000) ---')
stat('A1-64', 0x00800000, 0x96000)
stat('A1-72', 0x00800000, 0x1C2000)
print('--- CAM2 (720p) ---')
stat('A2-72', 0x00C00000, 0x1C2000)
os.close(FD)
print('CHK2_DONE')
