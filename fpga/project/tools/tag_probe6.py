import ctypes,os,fcntl,mmap,struct,time,signal,sys
FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
class TMO(Exception): pass
def _h(s,f): raise TMO()
signal.signal(signal.SIGALRM,_h)
def io(cmd,o,sec):
  signal.alarm(sec)
  try:
    r=fcntl.ioctl(FD,cmd,o,True)
  finally:
    signal.alarm(0)
  return r
print('map tx',flush=True)
o=O(); o.cmd=0; o.ln=4194304
try: io(I(2),o,8); print(' map tx ok',flush=True)
except TMO: print(' map tx TIMEOUT',flush=True)
o=O(); o.cmd=1; o.ln=4194304
try: io(I(2),o,8); print(' map rx ok',flush=True)
except TMO: print(' map rx TIMEOUT',flush=True)
RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  try:
    io(I(5),o,8)
  except TMO:
    return None
  return bytes(RX[0:n])
TAGS=[('cam1',0x00896000),('cam2',0x00C96000),('cam3',0x01096000),('cam4',0x01496000),('cam5',0x01896000),('cam6',0x01C96000)]
FB=[('cam1',0x00800000),('cam2',0x00C00000),('cam3',0x01000000),('cam4',0x01400000),('cam5',0x01800000),('cam6',0x01C00000)]
for rnd in range(4):
  line=[]
  for nm,a in TAGS:
    b=rdd(a,4)
    v=struct.unpack('<I',b)[0] if b else 0xFFFFFFFF
    line.append('%s=%u'%(nm,v))
  print('T%d %s'%(rnd,' '.join(line)),flush=True)
  time.sleep(0.7)
for nm,a in FB:
  b=rdd(a,4)
  v=struct.unpack('<I',b)[0] if b else 0xFFFFFFFF
  print('PX %s %08x'%(nm,v),flush=True)
print('TAGPROBE_DONE',flush=True)
