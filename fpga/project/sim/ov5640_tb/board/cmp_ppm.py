import numpy as np, os
from PIL import Image
for name, p in [("BEFORE(baseline)", r"sim\ov5640_tb\board\selftest_before.ppm"),
                ("KF(on board)",     r"sim\ov5640_tb\board\kf_on_board.ppm")]:
    im = Image.open(p).convert("RGB")
    a = np.asarray(im).astype(np.int32)
    print("%-18s size=%s mean=%s std=%s nonblack(>8)=%.1f%%" % (
        name, im.size, a.reshape(-1,3).mean(0).round(2), a.reshape(-1,3).std(0).round(2),
        100.0*(a.max(2) > 8).mean()))
    im.save(r"sim\ov5640_tb\board\%s.png" % ("before" if "before" in p else "kf"))
b = np.asarray(Image.open(r"sim\ov5640_tb\board\selftest_before.ppm").convert("RGB")).astype(np.int32)
k = np.asarray(Image.open(r"sim\ov5640_tb\board\kf_on_board.ppm").convert("RGB")).astype(np.int32)
d = np.abs(b-k)
print("diff mean=%.3f max=%d pixels>16=%.2f%%" % (d.mean(), d.max(), 100.0*(d.max(2)>16).mean()))
Image.fromarray(np.clip(d*4,0,255).astype(np.uint8)).save(r"sim\ov5640_tb\board\diff_x4.png")
Image.fromarray(np.clip(b,0,255).astype(np.uint8)).save(r"sim\ov5640_tb\board\before_view.png")
Image.fromarray(np.clip(k,0,255).astype(np.uint8)).save(r"sim\ov5640_tb\board\kf_view.png")
print("saved")
