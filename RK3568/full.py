import ctypes,os,fcntl,mmap,struct,signal
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/full.out','w')
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
 W,H=640,480
 d=rdd(0x0A000000,W*H*2)
 if d is None: P('EDGE read FAIL'); log.close(); raise SystemExit
 P('read %d bytes'%len(d))
 def px(i): return d[i*2]|(d[i*2+1]<<8)
 P('=== EDGE_A1 full-frame ASCII (sampled every 8px x every 14 rows) ===')
 for y in range(0,H,14):
  line=''
  for x in range(0,W,8):
   v=px(y*W+x)
   r=(v>>11)&31; g=(v>>5)&63; b=v&31
   lum=(r*77+g*151+b*28)>>8
   line+=CH[min(9,lum*10//32)]
  P('r%03d|%s|'%(y,line))
 open('/tmp/edge_full.raw','wb').write(d)
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
