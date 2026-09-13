import ctypes,os,fcntl,mmap,struct,signal
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/look.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
CH=' .:-=+*#%@'
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
 for nm,ad in (('EDGE_A1',0x0A000000),('RAW_A1',0x00800000)):
  d=rdd(ad,640*480*2)
  if d is None: P('%s FAIL'%nm); continue
  def px(i): 
   if i*2+1>=len(d): return 0
   return d[i*2]|(d[i*2+1]<<8)
  P('=== %s : pixels 0..159 of rows 0..39 (1 char = 1 px) ==='%nm)
  for y in range(0,40):
   line=''
   for x in range(0,160):
    v=px(y*640+x)
    r=(v>>11)&31; g=(v>>5)&63; b=v&31
    lum=(r*77+g*151+b*28)>>8
    line+=CH[min(9,lum*10//32)]
   P('r%02d|%s|'%(y,line))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
