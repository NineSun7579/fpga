import ctypes,os,fcntl,mmap,struct,signal,collections
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
log=open('/tmp/per.out','w')
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
 d=rdd(0x0A000000,8192)
 if d is None: P('FAIL'); log.close(); raise SystemExit
 P('=== first 192 bytes hex ===')
 for r in range(12):
  P('  %04X: %s'%(r*16, d[r*16:r*16+16].hex()))
 P('=== byte autocorrelation (match ratio vs lag) ===')
 best=[]
 for lag in range(1,2049):
  n=len(d)-lag
  m=sum(1 for i in range(0,n,3) if d[i]==d[i+lag])
  tot=len(range(0,n,3))
  r=100.0*m/tot
  if r>60: best.append((lag,r))
 best.sort(key=lambda t:-t[1])
 P('  top lags: %s'%[(l,round(rr,1)) for l,rr in best[:8]])
 P('=== 16-byte word repeat: word[i] == word[i+k] ===')
 words=[d[i:i+16] for i in range(0,len(d),16)]
 for k in (1,2,4,8,16,32,40,80,160):
  m=sum(1 for i in range(len(words)-k) if words[i]==words[i+k])
  P('  k=%3d (=%4d B, %4d px): identical %.1f%%'%(k,k*16,k*8,100.0*m/(len(words)-k)))
 P('=== run-length of identical consecutive words ===')
 runs=[]; c=1
 for i in range(1,len(words)):
  if words[i]==words[i-1]: c+=1
  else: runs.append(c); c=1
 runs.append(c)
 P('  max run=%d  avg=%.2f  runs>1: %d'%(max(runs),sum(runs)/len(runs),sum(1 for r in runs if r>1)))
 log.close()
except Exception as e:
 P('EXC '+repr(e)); log.close()
