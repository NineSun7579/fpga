# -*- coding: utf-8 -*-
"""Quantify + export the cam1/cam2/cam3 comparison frames."""
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\cmp"

for nm in ("c1_1", "c2_1", "c3_1", "c3_bar"):
    p = BASE + "\\" + nm + ".ppm"
    try:
        im = Image.open(p)
    except Exception as e:  # noqa: BLE001
        print(nm, "open fail", e)
        continue
    a = np.asarray(im).astype(np.int32)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    gdom = (G > 40) & (G > R + 25) & (G > B + 25)
    # horizontal-difference energy (speckle indicator)
    hd = np.abs(np.diff(G, axis=1)).mean()
    print("%-7s %s  meanRGB=(%5.1f,%5.1f,%5.1f)  green-dom=%.3f  mean|dG/dx|=%6.2f"
          % (nm, im.size, R.mean(), G.mean(), B.mean(), gdom.mean(), hd))
    im.resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST).save(BASE + "\\" + nm + ".png")

# build a side-by-side (cam1 | cam2 | cam3) strip
ims = [Image.open(BASE + "\\%s.ppm" % n) for n in ("c1_1", "c2_1", "c3_1")]
strip = Image.new("RGB", (640 * 3 + 20, 480), (0, 0, 0))
for i, im in enumerate(ims):
    strip.paste(im, (i * 660, 0))
strip.save(BASE + "\\strip.png")
print("wrote strip.png")
