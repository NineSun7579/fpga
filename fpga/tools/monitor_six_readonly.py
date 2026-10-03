"""Read six camera DDR banks without changing camera controls."""
import ctypes
import fcntl
import hashlib
import json
import mmap
import os
import struct
import time

class Op(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('cur', 'off', 'cmd', 'ddr', 'ln')] + [('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

fd = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def ioctl(n, op):
    return fcntl.ioctl(fd, 0xC0045300 | n, op, True)

for cmd in (0, 1):
    op = Op(); op.cmd = cmd; op.ln = 4194304
    ioctl(2, op)
rx = mmap.mmap(fd, 4194304, flags=mmap.MAP_SHARED,
               prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=1048576)

def read(addr, size):
    op = Op(); op.ddr = addr; op.ln = size
    ioctl(5, op)
    return bytes(rx[:size])

for addr in (0x20000040, 0x20000070, 0x20000144):
    print(json.dumps({'register': hex(addr), 'value': hex(struct.unpack('<I', read(addr, 16)[:4])[0])}), flush=True)

start = time.monotonic()
for sample in range(6):
    for camera in range(1, 7):
        for bank in range(2):
            addr = 0x800000 + (camera - 1) * 0x400000 + bank * 0x200000
            tag = struct.unpack('<I', read(addr + 0x96000, 16)[:4])[0]
            data = read(addr, 640 * 480 * 2)
            filename = '/tmp/six_monitor_cam%d_bank%d.rgb565' % (camera, bank)
            if sample == 5:
                with open(filename, 'wb') as out:
                    out.write(data)
            print(json.dumps({'sample': sample, 'seconds': round(time.monotonic() - start, 3),
                              'camera': camera, 'bank': bank, 'tag': tag,
                              'sha256': hashlib.sha256(data).hexdigest(),
                              'zero_bytes': data.count(0), 'ff_bytes': data.count(255)}), flush=True)
    time.sleep(1)
rx.close()
os.close(fd)
