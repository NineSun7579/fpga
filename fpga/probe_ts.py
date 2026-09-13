import ctypes, os, fcntl, mmap, struct, signal, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD  = IOWR(2)
PCI_DMA_WRITE_CMD = IOWR(5)

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class T(Exception): pass
def _a(s, f): raise T()
signal.signal(signal.SIGALRM, _a)

for c, sz in ((0, 4 * 1024 * 1024), (1, 4 * 1024 * 1024)):
    op = DMA_OPERATION(); op.cmd = c; op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)

RX = mmap.mmap(FD, 4 * 1024 * 1024, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

def rd(a, n=16):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = a; op.total_length = n
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op)
    except (T, OSError):
        return None
    finally:
        signal.alarm(0)
    return bytes(RX[0:n])

regs = [('PREP_CTRL', 0x20000100), ('PREP_THR', 0x20000104), ('PREP_SIZE', 0x20000108),
        ('PIPE_STATUS', 0x20000130), ('BUTTON', 0x20000140),
        ('TS0_cap', 0x20000170), ('TS1_prep', 0x20000174),
        ('TS2_npu', 0x20000178), ('TS3_dma', 0x2000017C),
        ('CAM_EN', 0x20000040), ('ACK', 0x20000000)]

r1 = {n: rd(a) for n, a in regs}
time.sleep(1.5)
r2 = {n: rd(a) for n, a in regs}

print('=== prep_regs 状态 (间隔1.5s 两次读) ===', flush=True)
for n, a in regs:
    v1 = struct.unpack('<I', r1[n][0:4])[0] if r1[n] else None
    v2 = struct.unpack('<I', r2[n][0:4])[0] if r2[n] else None
    s1 = 'READFAIL' if v1 is None else f'0x{v1:08X}'
    s2 = 'READFAIL' if v2 is None else f'0x{v2:08X}'
    flag = '  <== CHANGED' if (v1 is not None and v2 is not None and v1 != v2) else ''
    print(f'  {n:12s}  r1={s1}  r2={s2}{flag}', flush=True)

# DDR 数据是否滚动
d1 = rd(0x0, 2048); time.sleep(1.0); d2 = rd(0x0, 2048)
print('=== DDR 0x0 滚动检查 ===', flush=True)
print(f'  r1_head={d1[:16].hex() if d1 else None}', flush=True)
print(f'  r2_head={d2[:16].hex() if d2 else None}', flush=True)
print(f'  rolling={"YES" if (d1 and d2 and d1 != d2) else "NO (frozen)"}', flush=True)
