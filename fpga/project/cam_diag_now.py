import ctypes, os, fcntl, mmap, struct, signal, time
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4<<16) | (0x53<<8) | nr
MAP=IOWR(2); DR=IOWR(4); DW=IOWR(5)
class DMA_OPERATION(ctypes.Structure):
    _fields_=[("current_len",ctypes.c_uint32),("offset_addr",ctypes.c_uint32),
              ("cmd",ctypes.c_uint32),("ddr3_addr",ctypes.c_uint32),
              ("total_length",ctypes.c_uint32),("read_buf",ctypes.c_void_p),
              ("write_buf",ctypes.c_void_p)]
class T(Exception): pass
def _a(s,f): raise T()
signal.signal(signal.SIGALRM,_a)
BUF=4*1024*1024
for c in (0,1):
    op=DMA_OPERATION(); op.cmd=c; op.total_length=BUF
    fcntl.ioctl(FD,MAP,op,True)
TX=mmap.mmap(FD,BUF,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
RX=mmap.mmap(FD,BUF,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1024*1024)
def dma(nr,op,tmo=4):
    signal.alarm(tmo)
    try: return fcntl.ioctl(FD,nr,op,True)
    finally: signal.alarm(0)
def regw(a,v):
    TX[0:16]=struct.pack('<I',v)+b'\x00'*12
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=a; op.total_length=16
    try: return dma(DR,op)
    except T: return 'TO'
def regr(a):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=a; op.total_length=16
    try: r=dma(DW,op)
    except T: return None
    if r!=0: return None
    return struct.unpack('<I',RX[0:4])[0]
ADD={'CAM_EN':0x20000040,'ACK':0x20000000,'ADDR1':0x20000080,
     'PREP_CTRL':0x20000100,'PIPE_STATUS':0x20000130,'TS0':0x20000170}
print('== write CAM_ADDR_1 = 0x12345678 then read back ==',flush=True)
print('  wr=',regw(0x20000080,0x12345678),flush=True)
for k in range(8):
    row=[]
    for n,a in ADD.items():
        v=regr(a)
        row.append('%s=%s'%(n,('%08X'%v) if v is not None else 'FAIL'))
    print('  [%d] %s'%(k,' '.join(row)),flush=True)
    time.sleep(0.4)

for n,a in [('WORDS',0x20000030),('VSYNCS',0x20000034),('REQ',0x20000038),('I2C',0x2000003c),('PCLK',0x20000044),('SYS',0x20000048),('CLK',0x2000004c)]:
    print(n, hex(regr(a) if regr(a) is not None else 0), flush=True)

os.close(FD); print('DONE',flush=True)
