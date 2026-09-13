import ctypes,os,fcntl,mmap,struct,signal,time
class TO(Exception): pass
def _al(s,f): raise TO()
signal.signal(signal.SIGALRM,_al)
FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
class O(ctypes.Structure):
    _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
for c,s in ((0,4194304),(1,4194304)):
    o=O(); o.cmd=c; o.ln=s
    signal.alarm(6); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
def r1(a):
    o=O(); o.off=0; o.ddr=a; o.ln=16
    signal.alarm(6)
    try: fcntl.ioctl(FD,I(5),o,True)
    except TO: return None
    finally: signal.alarm(0)
    return struct.unpack('<I',RX[0:4])[0]
out=[]
for nm,ad in (('pp',0x20000180),('aw',0x20000184),('w',0x20000188),('b',0x2000018C)):
    a=r1(ad)
    out.append('%s=%s'%(nm, a if a is not None else 'FAIL'))
    time.sleep(0.08)
open('/tmp/rc.out','w').write(' '.join(out))
os.close(FD)
