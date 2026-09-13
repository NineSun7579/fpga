import ctypes
lib = ctypes.CDLL('/root/ov5640/libdma_rga_camera.so')
buf = ctypes.create_string_buffer(512)
n = lib.get_connected_connectors(buf, 512)
print('connected =', n)
print(buf.value.decode('utf-8', 'replace'))
