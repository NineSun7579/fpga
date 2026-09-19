import ctypes, os, fcntl, mmap, struct, signal, time
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
def rd(addr,n=256):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=addr; op.total_length=n
    signal.alarm(6)
    try: r=fcntl.ioctl(FD,DW,op,True)
    except T: return None
    finally: signal.alarm(0)
    if r!=0: return None
    return bytes(RX[0:n])
FR=0x1C2000
addrs=[0x0,0x40000,0x80000,0xC0000,0x100000,0x140000,0x180000,0x1C0000,0x1C2000,
       0x1E0000,0x200000,0x300000,0x3C4000,0x3F4800,0x400000,0x5B6800,0x5B6800+FR-256]
print('offset        head32                                  allFF  uniq')
for a in addrs:
    d=rd(a,256)
    if d is None:
        print('  0x%08X READ_FAIL'%a,flush=True); continue
    allff = all(b==0xFF for b in d)
    print('  0x%08X %-40s %-6s %d'%(a,d[:16].hex(),allff,len(set(d))),flush=True)
print('DONE',flush=True)
os.close(FD)
