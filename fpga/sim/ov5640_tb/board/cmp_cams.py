import numpy as np
from PIL import Image
a = np.asarray(Image.open(r"sim\ov5640_tb\board\cam1_kf.ppm").convert("RGB")).astype(np.float64)
b = np.asarray(Image.open(r"sim\ov5640_tb\board\cam2_raw.ppm").convert("RGB")).astype(np.float64)
print("shape", a.shape, b.shape)
for tag,x in (("cam1_KF",a),("cam2_RAW",b)):
    print("%-9s meanRGB=%s  max=%s  nonzero(>0)=%.1f%%" % (tag, x.reshape(-1,3).mean(0).round(2), x.max(0), 100*(x.max(2)>0).mean()))
g1,g2 = a[:,:,1].ravel(), b[:,:,1].ravel()
print("G mean: cam1=%.3f cam2=%.3f ratio=%.3f" % (g1.mean(), g2.mean(), g1.mean()/max(g2.mean(),1e-9)))
print("G nonzero: cam1=%.1f%% cam2=%.1f%%" % (100*(g1>0).mean(), 100*(g2>0).mean()))
# spatial: are the two cameras looking at the same scene? correlate downsampled
d1 = np.asarray(Image.open(r"sim\ov5640_tb\board\cam1_kf.ppm").convert("L")).astype(np.float64)[::8,::8]
d2 = np.asarray(Image.open(r"sim\ov5640_tb\board\cam2_raw.ppm").convert("L")).astype(np.float64)[::8,::8]
print("downsampled corr( cam1, cam2 ) = %.3f" % np.corrcoef(d1.ravel(), d2.ravel())[0,1])
for tag,x in (("cam1_KF",a),("cam2_RAW",b)):
    Image.fromarray(x.astype(np.uint8)).save(r"sim\ov5640_tb\board\%s.png"%tag)
print("saved png")
