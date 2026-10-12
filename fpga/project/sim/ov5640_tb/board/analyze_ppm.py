import numpy as np, os
from PIL import Image
p = r"sim\ov5640_tb\board\kf_on_board.ppm"
im = Image.open(p)
print("format", im.format, "mode", im.mode, "size", im.size)
a = np.asarray(im)
print("shape", a.shape, "dtype", a.dtype)
print("mean RGB", a.reshape(-1,3).mean(0))
print("std  RGB", a.reshape(-1,3).std(0))
print("min/max", a.min(), a.max())
# unique colors (sampled)
flat = a.reshape(-1,3)
ux = np.unique(flat[::37], axis=0)
print("sampled unique colors:", len(ux))
im.convert("RGB").save(r"sim\ov5640_tb\board\kf_on_board.png")
print("saved png", os.path.getsize(r"sim\ov5640_tb\board\kf_on_board.png"))
