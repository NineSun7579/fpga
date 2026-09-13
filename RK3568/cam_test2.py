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
def dma(nr,op,tmo=5):
    signal.alarm(tmo)
    try: return fcntl.ioctl(FD,nr,op,True)
    finally: signal.alarm(0)
def regw(addr,val):
    TX[0:16]=struct.pack('<I',val)+b'\x00'*12
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=16
    try: return dma(DR,op)
    except T: return 'TO'
def regr(addr):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=16
    try: r=dma(DW,op)
    except T: return None
    if r!=0: return None
    return struct.unpack('<I',RX[0:4])[0]
def ddr(addr,n=4096):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=n
    try: r=dma(DW,op,6)
    except T: return None
    if r!=0: return None
    return bytes(RX[0:n])
def irqsum():
    d={}
    for l in open('/proc/interrupts'):
        if 'pango' in l:
            p=l.split(); d[p[-1]]=int(p[1])
    return d
print('== setup: ADDR1=0 ADDR2=0x3F4800 ACK=3 CAM_EN=1 ==',flush=True)
print('  r=',regw(0x20000080,0x00000000),regw(0x200000c0,0x003F4800),regw(0x20000000,3),regw(0x20000040,1),flush=True)
print('  CAM_EN rb=0x%08X'%(regr(0x20000040) or 0),flush=True)
i0=irqsum(); print('  irq after setup:',i0,flush=True)
time.sleep(2.0)
i1=irqsum(); print('  irq +2s:',i1,'delta=',{k:i1[k]-i0.get(k,0) for k in i1},flush=True)
a=ddr(0x0); time.sleep(1.0); b=ddr(0x0)
print('  frameA same=%s head=%s'%(a==b, (a[:12].hex() if a else None)),flush=True)
print('== ACK=3 ==',flush=True); print('  r=',regw(0x20000000,3),flush=True)
time.sleep(1.5); i2=irqsum(); print('  irq +1.5s:',i2,'delta=',{k:i2[k]-i1.get(k,0) for k in i2},flush=True)
c=ddr(0x0)
print('  frameA after ACK changed=%s head=%s'%(c!=b, (c[:12].hex() if c else None)),flush=True)
print('== ACK=3 again ==',flush=True); print('  r=',regw(0x20000000,3),flush=True)
time.sleep(1.5); d=ddr(0x0)
print('  frameA changed=%s head=%s'%(d!=c, (d[:12].hex() if d else None)),flush=True)
i3=irqsum(); print('  irq:',i3,flush=True)
os.close(FD); print('DONE',flush=True)
