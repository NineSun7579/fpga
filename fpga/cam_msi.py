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
def irqs():
    out={}
    for l in open('/proc/interrupts'):
        if 'pango' in l:
            p=l.split()
            out[p[-1]]=int(p[1])
    return out
def show(tag):
    d=irqs(); print('  %-8s %s'%(tag,d),flush=True); return d
print('== irqs idle ==',flush=True); show('idle')
print('== ACK=3, CAM_EN=0 then 1 ==',flush=True)
print('  ack',regw(0x20000000,3),'en0',regw(0x20000040,0),'en1',regw(0x20000040,1),flush=True)
prev=None
for i in range(10):
    d=irqs()
    if prev is not None:
        delta={k:d[k]-prev.get(k,0) for k in d}
        print('  [%d] %s delta=%s'%(i,d,delta),flush=True)
    else:
        print('  [%d] %s'%(i,d),flush=True)
    prev=d
    time.sleep(0.5)
print('== CAM_EN readback=0x%08X =='%(regr(0x20000040) or 0),flush=True)
print('== frame bytes @0x0 ==',flush=True)
for k in range(3):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=0; op.total_length=8192
    try: r=dma(DW,op,6)
    except T: r='TO'
    if r==0:
        seg=bytes(RX[0:8192]); print('   [%d] uniq=%d head=%s'%(k,len(set(seg)),seg[:16].hex()),flush=True)
    else:
        print('   [%d] read=%s'%(k,r),flush=True)
    time.sleep(0.4)
os.close(FD); print('DONE',flush=True)
