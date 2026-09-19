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
def p(name,addr):
    v=regr(addr); print('  %-14s 0x%08X'%(name,v) if v is not None else '  %-14s NONE'%name,flush=True); return v
print('== status regs ==',flush=True)
p('PIPE_STATUS',0x20000130); p('INJ_STATUS',0x20000120); p('BUTTON',0x20000140); p('TS0',0x20000170)
print('== toggle CAM_EN 0->1 ==',flush=True)
regw(0x20000040,0); time.sleep(0.3); regw(0x20000040,1)
print('== PIPE_STATUS x8 (every 0.6s) ==',flush=True)
for i in range(8):
    v=regr(0x20000130)
    print('  [%d] 0x%08X  frame_cnt=%d sync=%d fifo_afull=%d npu_busy=%d'%(i,v,
          (v>>8)&0xff if v is not None else -1, v&1 if v is not None else -1,
          (v>>1)&1 if v is not None else -1, (v>>2)&1 if v is not None else -1),flush=True)
    time.sleep(0.6)
print('== TS0 x3 ==',flush=True)
for i in range(3):
    print('  TS0=0x%08X'%regr(0x20000170),flush=True); time.sleep(0.4)
os.close(FD); print('DONE',flush=True)
