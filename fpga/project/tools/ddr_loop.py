import ctypes, os, fcntl, mmap, struct, time

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def IOWR(nr): return 0xC0000000 | (4 << 16) | (0x53 << 8) | nr
MAP = IOWR(2); DR = IOWR(4); DW = IOWR(5)


class DMA_OPERATION(ctypes.Structure):
    _fields_ = [("current_len", ctypes.c_uint32), ("offset_addr", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("ddr3_addr", ctypes.c_uint32),
                ("total_length", ctypes.c_uint32), ("read_buf", ctypes.c_void_p),
                ("write_buf", ctypes.c_void_p)]


BUF = 4 * 1024 * 1024
for c in (0, 1):
    o = DMA_OPERATION(); o.cmd = c; o.total_length = BUF
    fcntl.ioctl(FD, MAP, o, True)
TX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD, BUF, prot=mmap.PROT_READ | mmap.PROT_WRITE,
               flags=mmap.MAP_SHARED, offset=1024 * 1024)


def wr16(a, words):
    TX[0:16] = b''.join(struct.pack('<I', w) for w in words)
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    fcntl.ioctl(FD, DR, o, True)


def rd16(a):
    o = DMA_OPERATION(); o.offset_addr = 0; o.ddr3_addr = a; o.total_length = 16
    if fcntl.ioctl(FD, DW, o, True) != 0:
        return None
    return struct.unpack('<4I', RX[0:16])


TESTS = [0x0B000000, 0x00800000, 0x00A00000, 0x00100000, 0x00000000]
print('== host<->DDR round-trip (write 16B pattern, read back) ==', flush=True)
for i, a in enumerate(TESTS):
    pat = [0xA0000000 + i, 0xB0000000 + i, 0xC0000000 + i, 0xD0000000 + i]
    wr16(a, pat)
    time.sleep(0.05)
    got = rd16(a)
    ok = (got is not None and list(got) == pat)
    print('  @0x%08X wrote %s -> read %s %s' % (
        a, ['%08X' % x for x in pat],
        ['%08X' % x for x in got] if got else 'X', 'OK' if ok else 'MISMATCH'), flush=True)

print('== debug ==', flush=True)
for n, a in [('AXI_NOW', 0x200000d0), ('BEAT_CNT', 0x200000a0), ('BEAT_LAST', 0x200000f0),
             ('CAM_WORDS', 0x20000030), ('VSYNCS', 0x20000020), ('AXI_STICKY', 0x20000050)]:
    v = rd16(a)
    print('  %-10s = 0x%08X' % (n, v[0] if v else 0), flush=True)
os.close(FD)
print('DONE', flush=True)
