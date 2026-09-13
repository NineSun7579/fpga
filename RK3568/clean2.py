import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/clean.out','w')
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
  signal.alarm(15)
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
 # 强制写正确模式: bypass=0 mode=3 edge_en=1 color_en=1 -> 0x1E
 P('enable cam: addr1=%s addr2=%s ack=%s en=%s'%(wrr(0x20000080,0x00800000),wrr(0x200000C0,0x00A00000),wrr(0x20000000,3),wrr(0x20000040,1)))
 time.sleep(1.5)
 P('write PREP_CTRL=0x1E -> %s'%wrr(0x20000100,0x1E))
 time.sleep(0.2)
 P('write PREP_SIZE=640|480<<16=0x01E00280 -> %s'%wrr(0x20000108,(480<<16)|640))
 time.sleep(0.5)
 N=614400
 P('fill edge buf with 0x55 ... %s'%wrd(0x0A000000,bytes([0x55])*N))
 time.sleep(4.0)
 d=rdd(0x0A000000,N)
 if d is None: P('read FAIL'); log.close(); raise SystemExit
 cc=collections.Counter(d)
 P('byte hist top6: %s'%[('%02X'%v,n) for v,n in cc.most_common(6)])
 px=[d[i]|(d[i+1]<<8) for i in range(0,N,2)]
 pc=collections.Counter(px)
 P('pixel hist top6: %s'%[('%04X'%v,n) for v,n in pc.most_common(6)])
 nbin=pc.get(0x0000,0)+pc.get(0xFFFF,0)
 P('binary pixels: %d/%d = %.1f%%'%(nbin,len(px),100.0*nbin/len(px)))
 P('leftover 0x5555: %d'%pc.get(0x5555,0))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
