import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/strict.out','w')
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
 def hist(d):
  c=collections.Counter(d)
  px=[d[i]|(d[i+1]<<8) for i in range(0,len(d)-1,2)]
  pc=collections.Counter(px)
  nb=pc.get(0,0)+pc.get(0xFFFF,0)
  return ('bytes=%d 55=%d 00=%d FF=%d | px bin=%d/%d=%.1f%% top=%s'%(
    len(d), c.get(0x55,0), c.get(0,0), c.get(0xFF,0),
    nb, len(px), 100.0*nb/max(1,len(px)),
    [('%04X'%v,n) for v,n in pc.most_common(4)]))
 A=0x0A000000
 P('step1: enable camera: %s %s %s %s'%(wrr(0x20000080,0x00800000),wrr(0x200000C0,0x00A00000),wrr(0x20000000,3),wrr(0x20000040,1)))
 time.sleep(2)
 # 小区域填充 + 立即回读
 P('step2: fill 4KB with 0x55: %s'%wrd(A, bytes([0x55])*4096))
 time.sleep(0.3)
 d0=rdd(A,4096)
 P('  immediate readback: %s'%hist(d0))
 time.sleep(3.0)
 d1=rdd(A,4096)
 P('  after 3s        : %s'%hist(d1))
 P('  -> FPGA overwrote the fill? %s'%('YES' if d1.count(0x55) < 100 else 'NO (fill still there)'))
 P('step3: raw buffer check (camera alive?)')
 dr=rdd(0x00800000,4096)
 P('  RAW_A1: %s'%hist(dr))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
