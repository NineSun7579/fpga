import ctypes, os, fcntl, mmap, struct, signal
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4<<16) | (0x53<<8) | nr
MAP=IOWR(2); DW=IOWR(5)
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
RX=mmap.mmap(FD,BUF,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1024*1024)
def rd(addr,n,tmo=3):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=n
    signal.alarm(tmo)
    try: r=fcntl.ioctl(FD,DW,op,True)
    except T: return 'TIMEOUT'
    finally: signal.alarm(0)
    if r!=0: return 'ret=%d'%r
    return bytes(RX[0:n]).hex()
print('NPU reg 0x40000000:', rd(0x40000000,16,3), flush=True)
print('PREP reg 0x20000100:', rd(0x20000100,16,3), flush=True)
print('DDR 0x0:', rd(0x0,16,3), flush=True)
print('DONE',flush=True)
os.close(FD)
