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
BASE=0x20000000
A1=0x00800000; A2=0x00A00000
print('== reg loopback ==',flush=True)
regw(BASE+0x80,A1); print('  addr1 rb=0x%08X want 0x%08X'%(regr(BASE+0x80) or 0,A1),flush=True)
regw(BASE+0xC0,A2); print('  addr2 rb=0x%08X want 0x%08X'%(regr(BASE+0xC0) or 0,A2),flush=True)
idr=regr(BASE+0x3C) or 0
print('== cam health == id=0x%04X (want 5640) nack_ops=%d'%(idr&0xFFFF,idr>>16),flush=True)
pc1=regr(BASE+0x44) or 0
time.sleep(0.2)
pc2=regr(BASE+0x44) or 0
print('   pclk delta 0.2s = %d %s'%(pc2-pc1,'(alive)' if pc2!=pc1 else '(DEAD PIN!)'),flush=True)
print('== fresh state ==',flush=True)
print('  vsyncs(+34)=%s words(+30)=%s req(+38)=0x%s'%(regr(BASE+0x34),regr(BASE+0x30),hex(regr(BASE+0x38) or 0)),flush=True)
regw(BASE+0x00,3)
regw(BASE+0x40,1)
print('== cam enabled, poll 8s ==',flush=True)
t0=time.time(); seen={0:False,1:False}; last=-1
while time.time()-t0 < 8:
    rq=regr(BASE+0x38) or 0
    if rq!=last:
        print('  t=%.2f req=0x%X vsyncs=%s words=%s'%(time.time()-t0,rq,regr(BASE+0x34),regr(BASE+0x30)),flush=True)
        last=rq
    for b in (0,1):
        if (rq>>b)&1 and not seen[b]:
            seen[b]=True
            d=ddr(A1 if b==0 else A2)
            nz=sum(1 for x in d if x) if d else -1
            print('  BUF%d READY head=%s nz=%d/256'%(b,(d[:16].hex() if d else 'X'),nz),flush=True)
            regw(BASE+0x00,1<<b)
    time.sleep(0.01)
print('== after 8s: vsyncs=%s words=%s'%(regr(BASE+0x34),regr(BASE+0x30)),flush=True)
os.close(FD); print('DONE',flush=True)
