"""Read-only six-camera register/tag snapshots; run with viewers stopped."""
import ctypes
import fcntl
import mmap
import os
import struct
import time

class Op(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in
                ('current_len', 'offset_addr', 'cmd', 'ddr3_addr', 'total_length')] + [
                    ('read_buf', ctypes.c_void_p), ('write_buf', ctypes.c_void_p)]

fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
for cmd in (0, 1):
    op = Op(cmd=cmd, total_length=4*1024*1024)
    fcntl.ioctl(fd, 0xc0045302, op)
rx = mmap.mmap(fd, 4*1024*1024, offset=1024*1024)
def read(address):
    op = Op(ddr3_addr=address, total_length=16)
    fcntl.ioctl(fd, 0xc0045305, op)
    return struct.unpack('<4I', rx[:16])

for sample in range(3):
    print('sample', sample, flush=True)
    for camera in range(6):
        base = 0x20000000 + camera*0x200
        print('C%d' % (camera+1), 'regs',
              [(hex(o), tuple(hex(v) for v in read(base+o)))
               for o in (0x0c, 0x30, 0x40)], 'tags',
              [tuple(hex(v) for v in read(0x00896000+camera*0x400000+b))
               for b in (0, 0x200000)], flush=True)
    print('SFP_DIAG', [(hex(o), tuple(hex(v) for v in read(0x20000000+o)))
                       for o in (0x120, 0x130, 0x140, 0x144, 0x150, 0x160, 0x170, 0x180)], flush=True)
    time.sleep(1)
rx.close()
os.close(fd)
