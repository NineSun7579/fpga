import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/who.out','w')
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
 def wrd(a,d):
  TX[0:len(d)]=d; o=O(); o.off=0; o.ddr=a; o.ln=len(d)
  signal.alarm(12)
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
 def chk(tag):
  da=rdd(0x0A000000,4096); db=rdd(0x0A100000,4096); dr=rdd(0x00800000,4096)
  def s(d):
   if d is None: return 'X'
   c=collections.Counter(d)
   return '55=%d 00=%d FF=%d'%(c.get(0x55,0),c.get(0,0),c.get(0xFF,0))
  P('%s  EDGE0x0A: %s | EDGE0x0A1: %s | RAW0x008: %s'%(tag,s(da),s(db),s(dr)))
 # 相机开
 wrr(0x20000080,0x00800000); wrr(0x200000C0,0x00A00000)
 wrr(0x20000000,3); wrr(0x20000040,1)
 time.sleep(2)
 # 填充三个区域
 wrd(0x0A000000, bytes([0x55])*8192)
 wrd(0x0A100000, bytes([0x55])*8192)
 wrd(0x00800000, bytes([0x55])*8192)
 P('filled 3 regions with 0x55 (camera ON)')
 time.sleep(3.0)
 chk('camera ON  :')
 # 相机关
 con=wrr(0x20000040,0)
 P('CAM_EN=0 -> %s'%con)
 time.sleep(1)
 wrd(0x0A000000, bytes([0x55])*8192)
 wrd(0x0A100000, bytes([0x55])*8192)
 wrd(0x00800000, bytes([0x55])*8192)
 P('refilled 3 regions (camera OFF)')
 time.sleep(3.0)
 chk('camera OFF :')
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
