import numpy as np
from PIL import Image
b = np.asarray(Image.open(r"sim\ov5640_tb\board\selftest_before.ppm").convert("RGB")).astype(np.float64)
k = np.asarray(Image.open(r"sim\ov5640_tb\board\kf_on_board.ppm").convert("RGB")).astype(np.float64)
# use green channel (6-bit in RGB565) - brightest
bg, kg = b[:,:,1].ravel(), k[:,:,1].ravel()
print("bin  n     mean_before  mean_kf   ratio   (green)")
for lo in [0,1,2,3,4,6,8,12,16,24,32,48,64,96]:
    hi = lo+1 if lo<4 else (lo*2 if lo>=4 else lo+2)
    m = (bg>=lo)&(bg<hi)
    if m.sum()<20: continue
    print("%3d-%3d %6d  %8.2f %8.2f  %5.2f" % (lo,hi-1,m.sum(),bg[m].mean(),kg[m].mean(),kg[m].mean()/max(bg[m].mean(),1e-9)))
# global
print("GLOBAL  b=%.3f k=%.3f ratio=%.3f"%(bg.mean(),kg.mean(),kg.mean()/bg.mean()))
# how many dark pixels
for t in [1,2,4,8]:
    print("  pixels with before-G < %d : %.1f%% ; their mean kf=%.2f"%(t,100*(bg<t).mean(), kg[bg<t].mean() if (bg<t).any() else 0))
