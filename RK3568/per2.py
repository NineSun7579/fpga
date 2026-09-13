import ctypes,os,fcntl,mmap,struct,signal
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/per2.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
try:
 FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
 I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
 class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
 for c,s in ((0,4194304),(1,4194304)):
  o=O(); o.cmd=c; o.ln=s
  signal.alarm(8); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
 RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(25)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 def rreg(a):
  o=O(); o.off=0; o.ddr=a; o.ln=16
  signal.alarm(6)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return struct.unpack('<I',RX[0:4])[0]
 d=rdd(0x0A000000,640*480*2)
 if d is None: P('read FAIL'); log.close(); raise SystemExit
 def px(i): return d[i*2]|(d[i*2+1]<<8)
 # 单行水平自相关 (像素级): 用第 100 行
 row=100
 P('=== row %d horizontal autocorrelation (px) ==='%row)
 hits=[]
 for lag in range(1,321):
  n=640-lag
  m=sum(1 for x in range(n) if px(row*640+x)==px(row*640+x+lag))
  hits.append((100.0*m/n, lag))
 hits.sort(reverse=True)
 P('  top periods: %s'%[(l,round(r,1)) for r,l in hits[:8]])
 # 垂直自相关 (行级)
 P('=== vertical autocorrelation (rows) ===')
 vh=[]
 for lag in range(1,241):
  n=480-lag
  m=sum(1 for y in range(0,n,2) for x in range(0,640,16) if px(y*640+x)==px((y+lag)*640+x))
  tot=len(range(0,n,2))*len(range(0,640,16))
  vh.append((100.0*m/tot, lag))
 vh.sort(reverse=True)
 P('  top row periods: %s'%[(l,round(r,1)) for r,l in vh[:8]])
 # 寄存器: 连续读两次取第二次
 for nm,ad in (('PREP_SIZE(+0x108)',0x20000108),('PREP_CTRL(+0x100)',0x20000100)):
  a=rreg(ad); b=rreg(ad)
  P('%s: %s / %s'%(nm, hex(a) if a is not None else None, hex(b) if b is not None else None))
  P('    -> width=%s height=%s'%((b&0xFFF) if b else None, ((b>>16)&0xFFF) if b else None))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
