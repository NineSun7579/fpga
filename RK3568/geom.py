import ctypes,os,fcntl,mmap,struct,signal,time,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/geom.out','w')
def P(s): log.write(str(s)+'\n'); log.flush()
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
 N=32768
 d=rdd(0x0A000000,N)
 if d is None:
  P('read FAIL'); log.close(); raise SystemExit
 P('bytes=%d'%len(d))
 cc=collections.Counter(d)
 P('byte hist top6: %s'%[('%02X'%v,n) for v,n in cc.most_common(6)])
 # 词级(16字节)统计
 words=[d[i:i+16] for i in range(0,len(d),16)]
 wc=collections.Counter(words)
 P('distinct 16B words=%d/%d  top3=%s'%(len(wc),len(words),[('%s'%w.hex(),n) for w,n in wc.most_common(3)]))
 # 行相似度: 找正确步长
 def rowsim(stride, rev_pix=False, rev_all=False):
  nrow=len(d)//stride
  if nrow<3: return 0
  good=0; tot=0
  for r in range(nrow-1):
   a=d[r*stride:(r+1)*stride]; b=d[(r+1)*stride:(r+2)*stride]
   if rev_all:
    a=a[::-1]; b=b[::-1]
   elif rev_pix:
    a=b''.join(a[i:i+2][::-1] for i in range(0,len(a),2))
    b=b''.join(b[i:i+2][::-1] for i in range(0,len(b),2))
   good+=sum(1 for x,y in zip(a,b) if x==y); tot+=len(a)
  return 100.0*good/max(tot,1)
 P('--- row similarity by stride ---')
 for st in (1280,640,2560,320,5120,3840,1920):
  P('  stride=%5d  sim=%.1f%%  (as-is)'%(st, rowsim(st)))
 P('--- stride 1280 variants ---')
 P('  as-is      %.1f%%'%rowsim(1280))
 P('  rev 2B/pix %.1f%%'%rowsim(1280, rev_pix=True))
 P('  rev all    %.1f%%'%rowsim(1280, rev_all=True))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
