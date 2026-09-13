import ctypes, os, fcntl, mmap, time, signal, struct

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
ERRS = []

REG_BASE  = 0x2000_0000          # M01 寄存器窗 (相机/PREP)
DDR_LB    = 0x0B000000           # 回环自检 DDR 地址 (相机乒乓 buf1)
DDR_LB2   = 0x0B1C2000           # 回环自检 DDR 地址 (相机乒乓 buf2)
FRAME_SZ  = 1280 * 720 * 2       # 0x1C2000
BUF_SIZE  = 4 * 1024 * 1024

def IOWR(nr):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr

PCI_MAP_ADDR_CMD  = IOWR(2)
PCI_DMA_READ_CMD  = IOWR(4)      # host -> FPGA (op_type=0)
PCI_DMA_WRITE_CMD = IOWR(5)      # FPGA -> host (op_type=1)
GPIO_CTRL         = IOWR(13)
PWM_CTRL          = IOWR(14)

class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32),
                ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32),
                ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32),
                ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]

class C_GPIO(ctypes.Structure):
    _fields_ = [("gpio_num", ctypes.c_uint32),
                ("level", ctypes.c_uint32),
                ("pwm_enable", ctypes.c_uint32),
                ("pwm_period", ctypes.c_uint32),
                ("pwm_duty", ctypes.c_uint32)]

def check(name, ok, detail=''):
    tag = 'PASS' if ok else 'FAIL'
    print(f'[{tag}] {name} {detail}', flush=True)
    if not ok:
        ERRS.append(name)

class DmaTimeout(Exception):
    pass

def _on_alarm(sig, frm):
    raise DmaTimeout()

signal.signal(signal.SIGALRM, _on_alarm)

def dma(nr, op, tmo=6):
    signal.alarm(tmo)
    try:
        return fcntl.ioctl(FD, nr, op, True)
    except TimeoutError:
        raise DmaTimeout()
    finally:
        signal.alarm(0)

TX = RX = None

def setup_buffers():
    global TX, RX
    op = DMA_OPERATION(); op.cmd = 0; op.total_length = BUF_SIZE
    r = dma(PCI_MAP_ADDR_CMD, op, 10)
    check('alloc TX 4MB', r == 0, f'ret={r}')
    op = DMA_OPERATION(); op.cmd = 1; op.total_length = BUF_SIZE
    r = dma(PCI_MAP_ADDR_CMD, op, 10)
    check('alloc RX 4MB', r == 0, f'ret={r}')
    TX = mmap.mmap(FD, BUF_SIZE, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
    RX = mmap.mmap(FD, BUF_SIZE, prot=mmap.PROT_READ | mmap.PROT_WRITE,
                   flags=mmap.MAP_SHARED, offset=1024 * 1024)
    print('buffers mapped', flush=True)

def reg_write32(fpga_addr, value, tag):
    """寄存器写入: 值放 16B DMA 传输 byte0~3 小端, 经 op_type=0 写 M01 窗"""
    TX[0:16] = struct.pack('<I', value) + b'\x00' * 12
    op = DMA_OPERATION()
    op.offset_addr = 0
    op.ddr3_addr = fpga_addr
    op.total_length = 16
    try:
        r = dma(PCI_DMA_READ_CMD, op)
        check(f'{tag} 写 0x{fpga_addr:08X}<=0x{value:08X}', r == 0, f'ret={r}')
        return True
    except DmaTimeout:
        check(f'{tag} 写 0x{fpga_addr:08X}', False, '超时')
        return False

def reg_read32(fpga_addr, tag):
    """寄存器读回: op_type=1 从 M01 窗读 16B, 值在 byte0~3"""
    op = DMA_OPERATION()
    op.offset_addr = 0
    op.ddr3_addr = fpga_addr
    op.total_length = 16
    try:
        r = dma(PCI_DMA_WRITE_CMD, op)
    except DmaTimeout:
        check(f'{tag} 读 0x{fpga_addr:08X}', False, '超时')
        return None
    if r != 0:
        check(f'{tag} 读 0x{fpga_addr:08X}', False, f'ret={r}')
        return None
    return struct.unpack('<I', RX[0:4])[0]

def ddr_read32(fpga_addr, nbytes, tag):
    """DDR -> host 读 (op_type=1), 返回数据"""
    op = DMA_OPERATION()
    op.offset_addr = 0
    op.ddr3_addr = fpga_addr
    op.total_length = nbytes
    try:
        r = dma(PCI_DMA_WRITE_CMD, op)
    except DmaTimeout:
        check(f'{tag} DDR 读 0x{fpga_addr:08X}', False, '超时')
        return None
    if r != 0:
        check(f'{tag} DDR 读 0x{fpga_addr:08X}', False, f'ret={r}')
        return None
    return RX[0:nbytes]

# ============ T1: 相机直写 DDR 数据面回环 (绕开 op0->M00 已知缺陷) ============
def test_cam_ddr_loopback():
    N = 4096
    # 1) 配置相机乒乓缓冲到回环地址 + 启动
    if not reg_write32(REG_BASE + 0x80, DDR_LB,  'CAM_ADDR_1'): return
    if not reg_write32(REG_BASE + 0xC0, DDR_LB2, 'CAM_ADDR_2'): return
    if not reg_write32(REG_BASE + 0x40, 1,       'CAM_EN'):    return
    time.sleep(1.5)   # 收集 ~45 帧
    d1 = ddr_read32(DDR_LB, N, '帧数据1')
    if d1 is None: return
    nz1 = sum(1 for b in d1 if b)
    check('DDR@0x0B000000 非全零(有帧数据)', nz1 > 256, f'非零字节={nz1}/{N}')
    time.sleep(0.5)
    d2 = ddr_read32(DDR_LB, N, '帧数据2')
    if d2 is None: return
    check('DDR 两读数据在变(流水中)', d1 != d2, '')
    reg_write32(REG_BASE + 0x40, 0, 'CAM_EN关')

# ============ T2: PREP 寄存器读写回环 (prep_regs 新集成验证) ============
def test_prep_regs():
    v = reg_read32(REG_BASE + 0x140, 'BUTTON_STATUS(RO)')
    if v is None:
        check('PREP 寄存器读通路', False, 'op1<-M01 不通, 跳过其余')
        return
    check('PREP 寄存器读通路(op1<-M01)', True, f'BUTTON=0x{v:08X}')
    # 读写回环: CTRL/THR/LED
    for off, name, val in [(0x100, 'PREP_CTRL', 0x0000001E),
                           (0x104, 'PREP_THR',  0xA0406080),
                           (0x150, 'LED_CTRL',  0x00000005)]:
        if not reg_write32(REG_BASE + off, val, name): continue
        rb = reg_read32(REG_BASE + off, name)
        check(f'{name} 写读回环', rb == val, f'写=0x{val:08X} 读=0x{rb:08X}' if rb is not None else '读失败')
    # TS0 节拍计数器应自增
    t1 = reg_read32(REG_BASE + 0x170, 'TS0-1')
    t2 = reg_read32(REG_BASE + 0x170, 'TS0-2')
    if t1 is not None and t2 is not None:
        check('TS0 打点计数器走动', t2 != t1, f'{t1} -> {t2}')
    # LED_CTRL 恢复 0
    reg_write32(REG_BASE + 0x150, 0, 'LED_CTRL复位')

# ============ T3/T4: GPIO / PWM ============
def test_gpio():
    g = C_GPIO(); g.gpio_num = 0; g.level = 1
    try:
        r = dma(GPIO_CTRL, g, 10)
        check('GPIO_CTRL 调用', r == 0, f'ret={r}')
    except (OSError, DmaTimeout) as e:
        check('GPIO_CTRL 调用', False, f'{type(e).__name__}')

def test_pwm():
    p = C_GPIO(); p.gpio_num = 0; p.pwm_enable = 1
    p.pwm_period = 1000000; p.pwm_duty = 500000
    try:
        r = dma(PWM_CTRL, p, 10)
        check('PWM_CTRL 调用', r == 0, f'ret={r}')
    except (OSError, DmaTimeout) as e:
        check('PWM_CTRL 调用', False, f'{type(e).__name__}')

# ================= main =================
print('=== FPGA<->RK3568 通信协议测试套件 v3 ===', flush=True)
setup_buffers()
test_cam_ddr_loopback()
test_prep_regs()
test_gpio()
test_pwm()
print(f'=== 结果: {len(ERRS)} 失败 ===', flush=True)
print('ALL PASS' if not ERRS else '失败项: ' + ', '.join(ERRS), flush=True)
os.close(FD)
