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
def ddr(a,n=256):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=a; op.total_length=n
    try: r=dma(DW,op,6)
    except T: return None
    if r!=0: return None
    return bytes(RX[0:n])
def irqs():
    d={}
    for l in open('/proc/interrupts'):
        if 'pango' in l:
            p=l.split(); d[p[-1]]=int(p[1])
    return d
A1=0x00800000; A2=0x00A00000
print('== fresh addrs A1=0x%08X A2=0x%08X =='%(A1,A2),flush=True)
print('  pre A1=',(ddr(A1+0x100000) or b'')[:8].hex(),'A2=',(ddr(A2+0x100000) or b'')[:8].hex(),flush=True)
print('  wr addr1',regw(0x20000080,A1),'addr2',regw(0x200000c0,A2),'ack',regw(0x20000000,3),flush=True)
print('  rb addr1=0x%08X addr2=0x%08X'%(regr(0x20000080) or 0, regr(0x200000c0) or 0),flush=True)
print('  en',regw(0x20000040,0),regw(0x20000040,1),'rb=0x%08X'%(regr(0x20000040) or 0),flush=True)
prev=None
for i in range(14):
    d=ddr(A1); e=ddr(A2)
    nz_a=sum(1 for b in d if b) if d else -1
    ch=(prev is not None and d is not None and d!=prev)
    print('  [%2d] A=%s nz=%3d %s | B=%s | irq0=%d'%(i,(d[:8].hex() if d else 'X'),nz_a,
          'CHANGED' if ch else 'same',(e[:8].hex() if e else 'X'),irqs().get('pango_pci_driver_irq0',-1)),flush=True)
    prev=d
    time.sleep(0.6)
os.close(FD); print('DONE',flush=True)
