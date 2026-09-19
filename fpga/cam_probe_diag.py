import ctypes, os, fcntl, mmap, struct, signal, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD  = IOWR(2)
PCI_DMA_READ_CMD  = IOWR(4)
PCI_DMA_WRITE_CMD = IOWR(5)

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class T(Exception): pass
def _a(s, f): raise T()
signal.signal(signal.SIGALRM, _a)

for c, sz in ((0, 4*1024*1024), (1, 4*1024*1024)):
    op = DMA_OPERATION(); op.cmd = c; op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)
TX = mmap.mmap(FD, 4*1024*1024, prot=mmap.PROT_READ|mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, 4*1024*1024, prot=mmap.PROT_READ|mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024*1024)

def rd(addr, n):
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = n
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, PCI_DMA_WRITE_CMD, op)
    except T:
        return None
    except OSError:
        return None
    finally:
        signal.alarm(0)
    return bytes(RX[0:n])

def wr(addr, val):
    TX[0:16] = struct.pack('<I', val) + b'\x00' * 12
    op = DMA_OPERATION(); op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16
    signal.alarm(8)
    try:
        fcntl.ioctl(FD, PCI_DMA_READ_CMD, op)
        return 0
    except (T, OSError):
        return -1
    finally:
        signal.alarm(0)

print('== 初始寄存器 ==', flush=True)
for a, t in ((0x20000040, 'CAM_EN'), (0x20000080, 'CAM_ADDR_1'), (0x200000C0, 'CAM_ADDR_2'), (0x20000000, 'ACK')):
    v = rd(a, 16)
    print(f'  {t}=0x{struct.unpack("<I", v[0:4])[0]:08X}' if v else f'  {t}=READ_FAIL', flush=True)

print('== 连续采样 0x0 (间隔 0.4s) ==', flush=True)
prev = None
for i in range(6):
    d = rd(0x0, 2048)
    if d is None:
        print(f'  [{i}] READ_FAIL', flush=True)
    else:
        h = d[:16].hex()
        changed = (d != prev) if prev else True
        print(f'  [{i}] nz={sum(1 for x in d if x)} uniq={len(set(d))} changed={changed} head={h}', flush=True)
        prev = d
    time.sleep(0.4)

def sample(tag, n=3):
    prev = None
    for i in range(n):
        d = rd(0x0, 2048)
        if d is None:
            print(f'  {tag}[{i}] READ_FAIL', flush=True)
        else:
            print(f'  {tag}[{i}] uniq={len(set(d))} changed={(d != prev) if prev else True} head={d[:12].hex()}', flush=True)
            prev = d
        time.sleep(0.35)

print('== A. 写 ACK=3 ==', flush=True)
print('  ret=', wr(0x20000000, 3), flush=True); time.sleep(0.5); sample('A')

print('== B. CAM_EN=0 -> 1 ==', flush=True)
print('  ret0=', wr(0x20000040, 0), 'ret1=', wr(0x20000040, 1), flush=True)
time.sleep(0.8); sample('B')

print('== C. 完整 init: ADDR1/ADDR2/ACK3/CAM_EN1 ==', flush=True)
wr(0x20000080, 0x00000000); wr(0x200000C0, 0x003F4800)
wr(0x20000000, 3); print('  en=', wr(0x20000040, 1), flush=True)
time.sleep(0.8); sample('C')

print('== D. CAM_EN=1 + 连续 ACK 脉冲 ==', flush=True)
for k in range(4):
    wr(0x20000000, 3); time.sleep(0.25)
sample('D')
