import numpy as np
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view

def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)

def stats(a, tag):
    g = a[:,:,1]  # green channel (6-bit grid, brightest)
    k = 3
    gp = np.pad(g, 1, mode="edge")
    lm = sliding_window_view(gp,(k,k)).mean((2,3))
    hf = g - lm                      # high-freq residual
    # normalise HF by mean so different AEC gains are comparable
    m = g.mean()
    hfn = hf.std()/max(m,1e-9)
    print("%-14s meanG8=%7.4f  hf_std=%6.3f  hf_std/mean=%6.3f  nz%%=%.1f  p99=%.1f max=%.0f"
          % (tag, m, hf.std(), hfn, 100*(g>0).mean(), np.percentile(g,99), g.max()))
    return m, hf.std(), hfn

print("=== SAME CAMERA (cam1): no-filter baseline vs adaptive KF, matched scene (cam2 raw ~4.2-4.4) ===")
a = load(r"sim\ov5640_tb\board\cam1_base.ppm");  s1 = stats(a, "cam1 NO-KF")
b = load(r"sim\ov5640_tb\board\cam1_kf2.ppm");   s2 = stats(b, "cam1 KF(RD1)")
print("  -> mean ratio KF/no-KF = %.3f ; HF-noise ratio = %.3f" % (s2[0]/s1[0], s2[1]/s1[1]))

print()
print("=== x=0 reference: RD0 build vs KF(RD1), matched scene (cam2 raw ~4.4-4.5) ===")
c = load(r"sim\ov5640_tb\board\cam1_rd0b.ppm");  s3 = stats(c, "cam1 RD0(x=0)")
print("  -> RD1 mean / RD0 mean = %.3f  (if the read returned zeros these would match)" % (s2[0]/s3[0]))

print()
print("=== cam2 raw control frames (identical lighting, each capture) ===")
for p,t in ((r"sim\ov5640_tb\board\cam2_base.ppm","base"),(r"sim\ov5640_tb\board\cam2_kf2.ppm","kf2"),(r"sim\ov5640_tb\board\cam2_rd0b.ppm","rd0b")):
    stats(load(p), "cam2_raw_"+t)
