import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/dma.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
try:
 FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
 I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
 class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
 for c,s in ((0,4194304),(1,4194304)):
  o=O(); o.cmd=c; o.ln=s
  signal.alarm(6); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
 TX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
 RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
 def wrr(a,v):
  TX[0:4]=struct.pack('<I',v); o=O(); o.off=0; o.ddr=a; o.ln=16
  signal.alarm(6)
  try: r=fcntl.ioctl(FD,I(4),o,True)
  except TO: return 'TO'
  finally: signal.alarm(0)
  return r
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(12)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 # 使能相机
 P('addr1=%s addr2=%s ack=%s en=%s' % (wrr(0x20000080,0x00800000),wrr(0x200000C0,0x00A00000),wrr(0x20000000,3),wrr(0x20000040,1)))
 time.sleep(2.5)
 d1=rdd(0x00800000,4096)
 time.sleep(1.2)
 d2=rdd(0x00800000,4096)
 if d1 is None or d2 is None:
  P('DDR READ FAIL (DMA 楔死)')
 else:
  ch=sum(1 for x,y in zip(d1,d2) if x!=y)
  nz=sum(1 for b in d1 if b)
  c=collections.Counter(d1)
  P('RAW_A1: changed=%d/4096 nonzero=%d top3=%s' % (ch,nz,[('%02X'%v,n) for v,n in c.most_common(3)]))
  P('判定: ' + ('DMA 正常, 画面在刷新' if ch>50 else 'DDR 无更新 (可能无画面)'))
 os.close(FD)
except Exception as e: P('EXC '+repr(e))
log.close()
