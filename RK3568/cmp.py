import ctypes,os,fcntl,mmap,struct,signal,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/cmp.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
CH=' .:-=+*#%@'
try:
 FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
 I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
 class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
 for c,s in ((0,4194304),(1,4194304)):
  o=O(); o.cmd=c; o.ln=s
  signal.alarm(6); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
 RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(10)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 def px(d,i): return d[i*2]|(d[i*2+1]<<8)
 for nm,ad in (('EDGE_A1',0x0A000000),('RAW_A1',0x00800000)):
  d=rdd(ad,1600)
  if d is None: P('%s FAIL'%nm); continue
  P('=== %s first 32 pixels hex ==='%nm)
  P('  '+' '.join('%04X'%px(d,i) for i in range(32)))
  # 每个像素的 R/G/B 分解
  P('  R: '+' '.join('%2d'%((px(d,i)>>11)&31) for i in range(32)))
  P('  G: '+' '.join('%2d'%((px(d,i)>>5)&63) for i in range(32)))
  P('  B: '+' '.join('%2d'%(px(d,i)&31) for i in range(32)))
  # 全分辨率 ASCII: 32 行 x 64 列(每列1像素)
  P('  full-res ASCII (32 rows x 64 px, 1 char = 1 px):')
  for y in range(32):
   line=''
   for x in range(64):
    v=px(d,y*640+x) if (y*640+x)*2+1<len(d) else 0
    r=(v>>11)&31; g=(v>>5)&63; b=v&31
    lum=(r*77+g*151+b*28)>>8
    line+=CH[min(9,lum*10//32)]
   P('   |'+line+'|')
  # FF/00 计数
  cnt=collections.Counter(px(d,i) for i in range(min(800,len(d)//2)))
  P('  pixel hist top5: %s'%[('%04X'%v,n) for v,n in cnt.most_common(5)])
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
