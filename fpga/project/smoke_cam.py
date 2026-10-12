import ctypes, time, zlib

lib = ctypes.CDLL('/root/ov5640/libdma_rga_camera.so')
lib.init_hardware_pipeline_ex.argtypes = [ctypes.c_int]
lib.fetch_next_frame.restype = ctypes.POINTER(ctypes.c_uint8)

print('init_hardware_pipeline_ex(0)...')
r = lib.init_hardware_pipeline_ex(0)
print('init ret:', r)

W, H, BPP = 1280, 720, 2
size = W * H * BPP

for i in range(6):
    p = lib.fetch_next_frame()
    if not p:
        print(f'frame {i}: NULL')
        continue
    buf = ctypes.string_at(p, size)
    ck = zlib.crc32(buf) & 0xffffffff
    nz = sum(1 for b in buf[:65536] if b)
    print(f'frame {i}: crc={ck:08x} nonzero_first64k={nz} head={buf[:12].hex()}')
    time.sleep(0.2)

lib.cleanup_hardware()
print('SMOKE DONE')
