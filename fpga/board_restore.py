import ctypes,os,fcntl,mmap,struct
F=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
class O(ctypes.Structure):
 _fields_=[('current_len',ctypes.c_uint32),('offset_addr',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr3_addr',ctypes.c_uint32),('total_length',ctypes.c_uint32),('read_buf',ctypes.c_void_p),('write_buf',ctypes.c_void_p)]
for c in (0,1):
 o=O();o.cmd=c;o.total_length=4*1024*1024;fcntl.ioctl(F,I(2),o,True)
T=mmap.mmap(F,4*1024*1024,prot=3,flags=mmap.MAP_SHARED)
def w(a,v):
 T[0:16]=struct.pack('<I',v)+bytes(12)
 o=O();o.ddr3_addr=a;o.total_length=16;fcntl.ioctl(F,I(4),o,True)
for a,v in ((0x20000080,0x00800000),(0x200000c0,0x00A00000),(0x20000000,3),(0x20000040,1)): w(a,v)
print('RESTORED')
os.close(F)
