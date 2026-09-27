import numpy as np
from PIL import Image

def load(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float64)
    return a

def flat_stats(a, tag):
    g = a[:,:,1]
    # 5x5 local mean/std via box filter
    k = 5
    pad = k//2
    gp = np.pad(g, pad, mode="edge")
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(gp, (k,k))
    lm = win.mean((2,3)); ls = win.std((2,3))
    flat = ls < 2.0
    print("%-9s pixels=%d  flat(ls<2)=%.1f%%  flat-region mean G8=%.2f  median=%.1f  p90=%.1f  max=%.0f" % (
        tag, g.size, 100*flat.mean(), g[flat].mean() if flat.any() else 0,
        np.median(g[flat]) if flat.any() else 0,
        np.percentile(g[flat],90) if flat.any() else 0, g.max()))
    print("           flat-region value histogram (G8):", np.bincount(np.clip(g[flat].astype(int),0,40), minlength=41)[:26].tolist())
    nz = g[g>0]
    print("           nonzero G8: %.1f%%   mean of nonzero=%.2f" % (100*(g>0).mean(), nz.mean() if nz.size else 0))

a = load(r"sim\ov5640_tb\board\cam1_kf.ppm")
b = load(r"sim\ov5640_tb\board\cam2_raw.ppm")
flat_stats(b, "cam2_RAW")
flat_stats(a, "cam1_KF")
# ratio of overall mean for reference
print("overall meanG8: raw=%.3f  kf=%.3f  ratio=%.3f" % (b[:,:,1].mean(), a[:,:,1].mean(), a[:,:,1].mean()/b[:,:,1].mean()))
