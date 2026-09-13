import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/addr.out','w')
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
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(12)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 # 扫描多个地址, 看谁在变(被FPGA写)以及内容类型
 def stat(a):
  d1=rdd(a,4096)
  if d1 is None: return None
  time.sleep(1.2)
  d2=rdd(a,4096)
  if d2 is None: return None
  ch=sum(1 for x,y in zip(d1,d2) if x!=y)
  c=collections.Counter(d1)
  px=[d1[i]|(d1[i+1]<<8) for i in range(0,4096,2)]
  pc=collections.Counter(px)
  nb=pc.get(0,0)+pc.get(0xFFFF,0)
  # 色彩度: 有多少像素 R,G,B 明显不等
  colored=0
  for v in px[:500]:
   r=(v>>11)&31; g=(v>>5)&63; b=v&31
   if abs(r-b)>3 or abs(g-(r+b)//2)>6: colored+=1
  return 'chg=%4d bin=%3d/500 color=%3d/500 top=%s'%(ch,nb*500//max(1,len(px)),colored,[('%04X'%v,n) for v,n in pc.most_common(3)])
 P('=== scan DDR regions (1.2s apart) ===')
 for nm,a in (('0x00000000',0x00000000),('0x00040000',0x00040000),
              ('0x00800000',0x00800000),('0x00A00000',0x00A00000),
              ('0x0A000000',0x0A000000),('0x0A100000',0x0A100000),
              ('0x0A1C2000',0x0A1C2000)):
  s=stat(a)
  P('  %-12s %s'%(nm, s if s else 'READ FAIL'))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
