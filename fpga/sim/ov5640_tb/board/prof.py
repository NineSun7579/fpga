import numpy as np
from PIL import Image
def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)
for tag,p in [("BEFORE", r"sim\ov5640_tb\board\selftest_before.ppm"),("KF", r"sim\ov5640_tb\board\kf_on_board.ppm")]:
    a=load(p); g=a.mean(2)
    print("=== %s === overall mean %.2f max %.0f" % (tag,g.mean(),g.max()))
    rows=g.mean(1); cols=g.mean(0)
    print(" rowmeans[0:12]", np.round(rows[:12],1))
    print(" rowmeans[76:88]", np.round(rows[76:88],1))
    print(" rowmeans[last12]", np.round(rows[-12:],1))
    # bounding box of pixels >20
    ys,xs=np.where(g>20)
    if len(ys): print(" bright(>20) bbox rows %d-%d cols %d-%d count %d"%(ys.min(),ys.max(),xs.min(),xs.max(),len(ys)))
    else: print(" no pixels >20")
# ASCII render of KF
a=load(r"sim\ov5640_tb\board\kf_on_board.ppm").mean(2)
b=load(r"sim\ov5640_tb\board\selftest_before.ppm").mean(2)
chars=" .:-=+*#%@"
for name,img in [("BEFORE",b),("KF",a)]:
    h,w=img.shape; H,W=32,64
    small=img[: h//H*H, : w//W*W].reshape(H,h//H,W,w//W).mean((1,3))
    mx=max(small.max(),1)
    print("--- %s (normalized to its own max %.0f) ---"%(name,small.max()))
    for r in small:
        print("".join(chars[min(9,int(v/mx*9.999))] for v in r))
