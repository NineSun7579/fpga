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
def regr(a,tmo=4):
    op=DMA_OPERATION(); op.offset_addr=0; op.ddr3_addr=a; op.total_length=16
    signal.alarm(tmo)
    try: r=fcntl.ioctl(FD,DW,op,True)
    except T: return None
    finally: signal.alarm(0)
    if r!=0: return None
    return struct.unpack('<I',RX[0:4])[0]
print('== PREP regs (read-only) ==',flush=True)
for k in range(10):
    ps=regr(0x20000130); ts0=regr(0x20000170); ts1=regr(0x20000174); pc=regr(0x20000100)
    if None in (ps,ts0,ts1,pc):
        print('  [%d] READ_FAIL ps=%s'%(k,ps),flush=True)
    else:
        print('  [%d] PIPE_STATUS=0x%08X frame_cnt=%d sync=%d npu_busy=%d | PREP_CTRL=0x%08X | TS0=0x%08X TS1=0x%08X'%(
            k,ps,(ps>>8)&0xff,ps&1,(ps>>2)&1,pc,ts0,ts1),flush=True)
    time.sleep(0.7)
os.close(FD); print('DONE',flush=True)
