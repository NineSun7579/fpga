import numpy as np, glob
from PIL import Image
for p in sorted(glob.glob(r"calib\*.ppm"))[:8]:
    a=np.asarray(Image.open(p).convert("RGB"))
    print(p, a.shape, "mean", a.reshape(-1,3).mean(0).round(1), "max", a.max())
