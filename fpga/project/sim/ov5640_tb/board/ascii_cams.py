import numpy as np
from PIL import Image
a = np.asarray(Image.open(r"sim\ov5640_tb\board\cam1_kf.ppm").convert("L")).astype(np.float64)
b = np.asarray(Image.open(r"sim\ov5640_tb\board\cam2_raw.ppm").convert("L")).astype(np.float64)
chars=" .:-=+*#%@"
for tag,x in (("cam2_RAW",b),("cam1_KF",a)):
    h,w=x.shape; H,W=30,80
    s=x[:h//H*H,:w//W*W].reshape(H,h//H,W,w//W).mean((1,3))
    mx=s.max()
    print("--- %s  (max block mean %.1f) ---"%(tag,mx))
    for r in s:
        print("".join(chars[min(9,int(v/mx*9.999))] for v in r))
