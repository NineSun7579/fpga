import ctypes, time, sys

lib = ctypes.CDLL('/root/ov5640/libdma_rga_camera.so')
lib.init_hardware_pipeline_ex.argtypes = [ctypes.c_int]
lib.sync_to_screen.argtypes = [ctypes.c_void_p]
lib.fetch_next_frame.restype = ctypes.c_void_p
lib.cleanup_hardware.restype = None

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 3600   # 默认 1 小时
YOLO_SIZE = 640 * 640 * 3

print('init_hardware_pipeline_ex(0)...', flush=True)
r = lib.init_hardware_pipeline_ex(0)
print('init ret:', r, flush=True)

n = 0
t0 = time.time()
try:
    while time.time() - t0 < DURATION:
        p = lib.fetch_next_frame()
        if not p:
            continue
        # fetch_next_frame returns one [YOLO][HD] block; display only the HD payload.
        lib.sync_to_screen(ctypes.c_void_p(p + YOLO_SIZE))
        n += 1
        if n % 30 == 0:
            print(f'[viewer] frames={n} fps={n/(time.time()-t0):.1f}', flush=True)
except KeyboardInterrupt:
    pass
print(f'[viewer] total frames={n}', flush=True)
lib.cleanup_hardware()
