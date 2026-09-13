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
    print('map', c, fcntl.ioctl(FD,MAP,op,True),flush=True)
TX=mmap.mmap(FD,BUF,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
RX=mmap.mmap(FD,BUF,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1024*1024)
def dma(nr,op,tmo=6):
    signal.alarm(tmo)
    try: return fcntl.ioctl(FD,nr,op,True)
    finally: signal.alarm(0)
def regw(addr,val,tmo=6):
    TX[0:16]=struct.pack('<I',val)+b'\x00'*12
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=16
    try: return dma(DR,op,tmo)
    except T: return 'TIMEOUT'
def regr(addr,tmo=4):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=16
    try: r=dma(DW,op,tmo)
    except T: return None
    if r!=0: return None
    return struct.unpack('<I',RX[0:4])[0]
def ddrread(addr,n,tmo=8):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=n
    try: r=dma(DW,op,tmo)
    except T: return None
    if r!=0: return None
    return bytes(RX[0:n])
def rr(tag,addr):
    v=regr(addr); print('  %s=0x%s'%(tag,('%08X'%v) if v is not None else 'NONE'),flush=True); return v
def show(tag,addr,n=4096):
    d=ddrread(addr,n)
    if d is None: print('  %s @0x%08X READ_FAIL'%(tag,addr),flush=True); return None
    print('  %s @0x%08X nz=%d uniq=%d head=%s'%(tag,addr,sum(1 for x in d if x),len(set(d)),d[:16].hex()),flush=True)
    return d
print('== regs before ==',flush=True)
rr('ACK',0x20000000); rr('CAM_EN',0x20000040); rr('ADDR1',0x20000080); rr('ADDR2',0x200000C0)
rr('PREP_CTRL(0x100)',0x20000100); rr('TS0(0x170)',0x20000170)
print('== DDR live check (before) ==',flush=True)
a1=show('frameA',0x0); time.sleep(0.7); a2=show('frameA2',0x0)
if a1 is not None and a2 is not None:
    print('  frameA CHANGED=%s'%(a1!=a2),flush=True)
show('frameB',0x3F4800)
print('== set ADDR1=0 ADDR2=0x3F4800 ACK=3 EN=1 ==',flush=True)
print('  wr:',regw(0x20000000,3),regw(0x20000080,0),regw(0x200000c0,0x3F4800),regw(0x20000040,1),flush=True)
time.sleep(1.5)
print('== DDR live check (after) ==',flush=True)
b1=show('frameA',0x0); time.sleep(0.7); b2=show('frameA2',0x0)
if b1 is not None and b2 is not None:
    print('  frameA CHANGED=%s'%(b1!=b2),flush=True)
rr('CAM_EN',0x20000040)
os.close(FD)
print('DONE',flush=True)
