import sys, ctypes, os, fcntl, mmap, struct, time, signal

variant = sys.argv[1]
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD  = IOWR(2)
PCI_DMA_READ_CMD  = IOWR(4)   # host -> FPGA
PCI_DMA_WRITE_CMD = IOWR(5)   # FPGA -> host

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32),
                ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32),
                ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32),
                ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class DmaTimeout(Exception):
    pass

def _on_alarm(s, f):
    raise DmaTimeout()

signal.signal(signal.SIGALRM, _on_alarm)

# H/I/J 用 cam_alive 实测过的分配尺寸 (TX 3MB / RX 10MB)
if variant in ('H', 'I', 'J'):
    alloc_tx, alloc_rx = 3 * 1024 * 1024, 10 * 1024 * 1024
else:
    alloc_tx = alloc_rx = 4 * 1024 * 1024

for cmd_, sz in ((0, alloc_tx), (1, alloc_rx)):
    op = DMA_OPERATION(); op.cmd = cmd_; op.total_length = sz
    fcntl.ioctl(FD, PCI_MAP_ADDR_CMD, op, True)

TX = mmap.mmap(FD, alloc_tx, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, alloc_rx, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)

# 变体矩阵: A=C库克隆寄存器写 / B=我的16B寄存器写 / C=4B offset0 / D=16B offset8
#           E=DDR读 offset0 / F=DDR读 offset1MB(cam_alive形态) / G=4B写DDR窗口
#           H=cam_alive精确克隆(3/10MB分配) / I=H但offset0 / J=C库克隆(3/10MB分配)
op = DMA_OPERATION()
cmd = None
if variant == 'A':
    TX[8:12] = struct.pack('<I', 0x0B000000)
    op.offset_addr = 8;  op.ddr3_addr = 0x20000080; op.total_length = 4;    cmd = PCI_DMA_READ_CMD
elif variant == 'B':
    TX[0:4] = struct.pack('<I', 0x0B000000)
    op.offset_addr = 0;  op.ddr3_addr = 0x20000080; op.total_length = 16;   cmd = PCI_DMA_READ_CMD
elif variant == 'C':
    TX[0:4] = struct.pack('<I', 0x0B000000)
    op.offset_addr = 0;  op.ddr3_addr = 0x20000080; op.total_length = 4;    cmd = PCI_DMA_READ_CMD
elif variant == 'D':
    TX[8:12] = struct.pack('<I', 0x0B000000)
    op.offset_addr = 8;  op.ddr3_addr = 0x20000080; op.total_length = 16;   cmd = PCI_DMA_READ_CMD
elif variant == 'E':
    op.offset_addr = 0;  op.ddr3_addr = 0x0;        op.total_length = 4096; cmd = PCI_DMA_WRITE_CMD
elif variant == 'F':
    op.offset_addr = 1024 * 1024; op.ddr3_addr = 0x0; op.total_length = 4096; cmd = PCI_DMA_WRITE_CMD
elif variant == 'G':
    TX[0:4] = struct.pack('<I', 0x12345678)
    op.offset_addr = 0;  op.ddr3_addr = 0x0B000000; op.total_length = 4;    cmd = PCI_DMA_READ_CMD
elif variant == 'H':
    op.offset_addr = 1024 * 1024; op.ddr3_addr = 0x0; op.total_length = 4096; cmd = PCI_DMA_WRITE_CMD
elif variant == 'I':
    op.offset_addr = 0;  op.ddr3_addr = 0x0;        op.total_length = 4096; cmd = PCI_DMA_WRITE_CMD
elif variant == 'J':
    TX[8:12] = struct.pack('<I', 0x0B000000)
    op.offset_addr = 8;  op.ddr3_addr = 0x20000080; op.total_length = 4;    cmd = PCI_DMA_READ_CMD
elif variant == 'K':
    # PREP 0x100 块四字打包写: [CTRL=0x1E, THR=0xA0406080, SIZE=0x00280050, LANE=0x06032828]
    block = struct.pack('<4I', 0x1E, 0xA0406080, 0x00280050, 0x06032828)
    TX[0:16] = block
    op.offset_addr = 0;  op.ddr3_addr = 0x20000100; op.total_length = 16;   cmd = PCI_DMA_READ_CMD
elif variant == 'L':
    # 4B 小写直打非对齐地址 0x104 (THR), 随后 16B 读 0x100 块看 THR 是否出现在 word1
    TX[0:4] = struct.pack('<I', 0xA0406080)
    op2 = DMA_OPERATION()
    op2.offset_addr = 0; op2.ddr3_addr = 0x20000104; op2.total_length = 4
    signal.alarm(6)
    try:
        fcntl.ioctl(FD, PCI_DMA_READ_CMD, op2, True)
        print('RESULT L-WRITE PASS', flush=True)
    except DmaTimeout:
        print('RESULT L-WRITE TIMEOUT', flush=True); sys.exit(1)
    op.offset_addr = 0;  op.ddr3_addr = 0x20000100; op.total_length = 16;   cmd = PCI_DMA_WRITE_CMD
elif variant == 'M':
    # 只读 0x100 块 (全新模块, 期望复位默认 CTRL=0x18 THR=0xA0406080)
    op.offset_addr = 0;  op.ddr3_addr = 0x20000100; op.total_length = 16;   cmd = PCI_DMA_WRITE_CMD
else:
    print(f'RESULT {variant} BAD-VARIANT'); sys.exit(1)

signal.alarm(6)
try:
    r = fcntl.ioctl(FD, cmd, op, True)
    extra = ''
    if cmd == PCI_DMA_WRITE_CMD:
        seg = bytes(RX[0:4096])
        nz = sum(1 for b in seg if b)
        uniq = len(set(seg))
        # 行周期性: 找最小周期 p 使 seg[i]==seg[i+p] 对前 512 字节成立率
        best = 0
        for p in range(2, 129):
            ok = sum(1 for i in range(0, 512 - p) if seg[i] == seg[i + p])
            if ok > 0.95 * (512 - p):
                best = p; break
        extra = f' nonzero={nz}/4096 uniq={uniq} period={best or "none"} head={seg[:24].hex()}'
    elif variant in ('K', 'L', 'M'):
        w = struct.unpack('<4I', RX[0:16])
        extra = f' CTRL=0x{w[0]:08X} THR=0x{w[1]:08X} SIZE=0x{w[2]:08X} LANE=0x{w[3]:08X}'
    print(f'RESULT {variant} PASS ret={r}{extra}', flush=True)
except DmaTimeout:
    print(f'RESULT {variant} TIMEOUT', flush=True)
except OSError as e:
    print(f'RESULT {variant} ERRNO{e.errno}', flush=True)
