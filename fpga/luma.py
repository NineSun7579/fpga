import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/luma.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
try:
 FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
 I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
 class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
 for c,s in ((0,4194304),(1,4194304)):
  o=O(); o.cmd=c; o.ln=s
  signal.alarm(8); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
 TX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
 RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
 def wrr(a,v):
  TX[0:4]=struct.pack('<I',v); o=O(); o.off=0; o.ddr=a; o.ln=16
  signal.alarm(8)
  try: r=fcntl.ioctl(FD,I(4),o,True)
  except TO: return 'TO'
  finally: signal.alarm(0)
  return r
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(20)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 wrr(0x20000080,0x00800000); wrr(0x200000C0,0x00A00000); wrr(0x20000000,3); wrr(0x20000040,1)
 time.sleep(2)
 d=rdd(0x00800000, 640*480*2)
 if d is None: P('read FAIL'); log.close(); raise SystemExit
 def px(i): return d[i*2]|(d[i*2+1]<<8)
 # 只统计被写过的行(值不全0)
 lums=[]
 for y in range(0,480,3):
  row=[px(y*640+x) for x in range(0,640,2)]
  if all(v==0 for v in row): continue
  for v in row:
   r=(v>>11)&31; g=(v>>5)&63; b=v&31
   # 扩展到8bit后按 BT.601
   r8=(r<<3)|(r>>2); g8=(g<<2)|(g>>4); b8=(b<<3)|(b>>2)
   lums.append((77*r8+150*g8+29*b8)>>8)
 P('non-blank luma samples: %d'%len(lums))
 if lums:
  lums.sort()
  n=len(lums)
  P('  min=%d p10=%d p25=%d median=%d p75=%d p90=%d max=%d mean=%d'%(
    lums[0],lums[n//10],lums[n//4],lums[n//2],lums[3*n//4],lums[9*n//10],lums[-1],sum(lums)//n))
  # 估计相邻梯度: 用水平相邻差
  diffs=[]
  for y in range(0,480,3):
   prev=None
   for x in range(0,640,2):
    v=px(y*640+x)
    r=(v>>11)&31; g=(v>>5)&63; b=v&31
    r8=(r<<3)|(r>>2); g8=(g<<2)|(g>>4); b8=(b<<3)|(b>>2)
    l=(77*r8+150*g8+29*b8)>>8
    if prev is not None: diffs.append(abs(l-prev))
    prev=l
  diffs.sort(); m=len(diffs)
  P('  |dLuma| per 2px: median=%d p75=%d p90=%d max=%d mean=%d'%(diffs[m//2],diffs[3*m//4],diffs[9*m//10],diffs[-1],sum(diffs)//m))
  P('  => Sobel mag ~ 4x |dLuma| at step edges; median mag ~ %d'%(4*diffs[m//2]))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
