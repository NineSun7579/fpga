"""Run on RK3568 only after stopping camview. No register writes or ACKs."""
import ctypes
import fcntl
import mmap
import os
import struct
import time

class Op(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint32) for n in ('current_len','offset_addr','cmd','ddr3_addr','total_length')]+[('read_buf',ctypes.c_void_p),('write_buf',ctypes.c_void_p)]

fd=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
cmd=lambda n: 0xC0000000|(4<<16)|(0x53<<8)|n
for direction in (0,1):
    op=Op(); op.cmd=direction; op.total_length=4*1024*1024
    fcntl.ioctl(fd,cmd(2),op,True)
rx=mmap.mmap(fd,4*1024*1024,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE,offset=1024*1024)

def read(addr):
    op=Op(); op.ddr3_addr=addr; op.total_length=16
    fcntl.ioctl(fd,cmd(5),op,True)
    return struct.unpack('<I',rx[:4])[0]

for sample in range(3):
    print('SAMPLE',sample,flush=True)
    for camera,base in ((1,0x20000000),(2,0x20000200),(3,0x20000400)):
        for label,offset in [('PCLK',0x10),('VSYNC',0x20),('WORDS',0x30),('EN',0x40),('STATE',0x60),('AW_B',0x70),('BEAT',0xa0),('DONE',0xf0)]:
            print(camera,label,hex(read(base+offset)),flush=True)
    for base in (0x00896000,0x00a96000,0x00c96000,0x00e96000,0x01096000,0x01296000):
        print('TAG',hex(base),hex(read(base)),flush=True)
    if sample<2: time.sleep(2)
rx.close(); os.close(fd)
