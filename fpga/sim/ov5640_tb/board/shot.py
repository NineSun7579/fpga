import numpy as np
from PIL import Image
for p in [r"sim\ov5640_tb\board\rk_desktop.png", r"sim\ov5640_tb\board\rk_detview.png"]:
    im=Image.open(p).convert("RGB"); a=np.asarray(im).astype(float)
    print(p.split("\\")[-1], im.size, "mean", a.reshape(-1,3).mean(0).round(1), "std", a.reshape(-1,3).std(0).round(1))
    # 24x48 ascii
    g=a.mean(2); H,W=24,48
    s=g[:g.shape[0]//H*H,:g.shape[1]//W*W].reshape(H,g.shape[0]//H,W,g.shape[1]//W).mean((1,3))
    chars=" .:-=+*#%@"; mx=max(s.max(),1)
    for r in s: print("".join(chars[min(9,int(v/mx*9.999))] for v in r))
    print()
