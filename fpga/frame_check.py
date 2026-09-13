import ctypes, os, fcntl, mmap, struct, signal

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

MAP = IOWR(2); DR = IOWR(4); DW = IOWR(5)

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class T(Exception):
    pass

def _a(s, f):
    raise T()

signal.signal(signal.SIGALRM, _a)

for c, sz in ((0, 4 * 1024 * 1024), (1, 4 * 1024 * 1024)):
    op = DMA_OPERATION(); op.cmd = c; op.total_length = sz
    fcntl.ioctl(FD, MAP, op, True)

RX = mmap.mmap(FD, 4 * 1024 * 1024, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

W, H = 1280, 720
SZ = W * H * 2

def getframe(addr):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = SZ
    signal.alarm(10)
    try:
        fcntl.ioctl(FD, DW, op, True)
    except (T, OSError):
        return None
    finally:
        signal.alarm(0)
    return bytes(RX[0:SZ])

def rgb(v):
    return ((v >> 11) & 0x1f) * 15 // 31, ((v >> 5) & 0x3f) * 15 // 63, (v & 0x1f) * 15 // 31

f0 = getframe(0x0)
if not f0:
    print('FRAME_READ_FAIL', flush=True)
    raise SystemExit

print('FRAME_OK bytes=%d' % len(f0), flush=True)
print('=== 画面色彩图 (32x16, 每格 RGB 十六进制) ===', flush=True)
GC, GR = 32, 16
cw, ch = W // GC, H // GR
for gr in range(GR):
    cells = []
    for gc in range(GC):
        acc = [0, 0, 0]
        for dy in (ch // 4, ch // 2, ch * 3 // 4):
            for dx in (cw // 4, cw // 2, cw * 3 // 4):
                y = gr * ch + dy; x = gc * cw + dx
                o = y * W * 2 + x * 2
                v = f0[o] | (f0[o + 1] << 8)
                r, g, b = rgb(v)
                acc[0] += r; acc[1] += g; acc[2] += b
        cells.append('%x%x%x' % (acc[0] // 9, acc[1] // 9, acc[2] // 9))
    print(' '.join(cells), flush=True)

print('=== 行结构分析 ===', flush=True)
for y in (30, 180, 360, 540, 700):
    vals = [f0[y * W * 2 + i * 2] | (f0[y * W * 2 + i * 2 + 1] << 8) for i in range(W)]
    runs = 1
    for i in range(1, W):
        if vals[i] != vals[i - 1]:
            runs += 1
    # 每个条的颜色 (取 8 等分点)
    bars = ['%04x' % vals[i * W // 8 + W // 16] for i in range(8)]
    print('ROW %3d: runs=%4d uniq=%4d bars=%s' % (y, runs, len(set(vals)), ' '.join(bars)), flush=True)

f1 = getframe(0x0)
print('FROZEN: %s' % ('YES' if f0 == f1 else 'NO(数据在滚动)'), flush=True)

f2 = getframe(0x3F4800)
if f2:
    vals = [f2[360 * W * 2 + i * 2] | (f2[360 * W * 2 + i * 2 + 1] << 8) for i in range(W)]
    runs = 1
    for i in range(1, W):
        if vals[i] != vals[i - 1]:
            runs += 1
    print('BUF2 ROW360: runs=%d uniq=%d head=%s' % (runs, len(set(vals)), f2[:16].hex()), flush=True)
