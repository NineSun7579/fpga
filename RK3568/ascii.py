import ctypes,os,fcntl,mmap,struct,signal
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/ascii.out','w')
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
 def art(d, W, H, cols=78, rows=22, title=''):
  P('=== %s (assumed %dx%d) ==='%(title,W,H))
  stepx=max(1,W//cols); stepy=max(1,H//rows)
  for ry in range(rows):
   line=''
   for rx in range(cols):
    x=rx*stepx; y=ry*stepy
    i=(y*W+x)*2
    if i+1>=len(d): line+=' '; continue
    px=d[i]|(d[i+1]<<8)
    # RGB565 -> 亮度
    r=(px>>11)&0x1F; g=(px>>5)&0x3F; b2=px&0x1F
    lum=(r*77+g*151+b2*28)>>8
    line+=CH[min(len(CH)-1, lum*len(CH)//32)]
   P(line)
 d=rdd(0x0A000000,640*480*2)
 if d is None: P('EDGE read FAIL')
 else:
  art(d,640,480,title='EDGE_A1')
  art(rdd(0x00800000,640*480*2) or b'',640,480,title='RAW_A1')
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
