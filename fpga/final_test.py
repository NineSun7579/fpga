import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/ft.out','w')
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
  signal.alarm(8)
  try: r=fcntl.ioctl(FD,I(4),o,True)
  except TO: return 'TO'
  finally: signal.alarm(0)
  return r
 def wrd(a,d):
  TX[0:len(d)]=d; o=O(); o.off=0; o.ddr=a; o.ln=len(d)
  signal.alarm(10)
  try: r=fcntl.ioctl(FD,I(4),o,True)
  except TO: return 'TO'
  finally: signal.alarm(0)
  return r
 def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(10)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return bytes(RX[0:n])
 def r1(a):
  o=O(); o.off=0; o.ddr=a; o.ln=16
  signal.alarm(6)
  try: fcntl.ioctl(FD,I(5),o,True)
  except TO: return None
  finally: signal.alarm(0)
  return struct.unpack('<I',RX[0:4])[0]
 P('enable: %s %s %s %s'%(wrr(0x20000080,0x00800000),wrr(0x200000C0,0x00A00000),wrr(0x20000000,3),wrr(0x20000040,1)))
 time.sleep(1)
 N=65536
 P('fill AA: A1=%s A2=%s'%(wrd(0x0A000000,bytes([0xAA])*N), wrd(0x0A100000,bytes([0xAA])*N)))
 time.sleep(3.0)
 c=[r1(0x20000180),r1(0x20000184),r1(0x20000188),r1(0x2000018C)]
 P('counters pp=%s aw=%s w=%s b=%s'%tuple(c))
 for nm,ad in (('EDGE_A1',0x0A000000),('EDGE_A2',0x0A100000),('RAW_A1',0x00800000)):
  d=rdd(ad,N)
  if d is None: P('%s FAIL'%nm); continue
  cc=collections.Counter(d)
  P('%s: AA=%d FF=%d 00=%d /%d top4=%s'%(nm,cc.get(0xAA,0),cc.get(0xFF,0),cc.get(0x00,0),N,[('%02X'%v,n) for v,n in cc.most_common(4)]))
 P('DONE')
 os.close(FD)
except Exception as e: P('EXC '+repr(e))
log.close()
