# -*- coding: utf-8 -*-
"""Compare the two post-recovery screenshots to confirm cam3 is live."""
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\NineSun\Desktop\ov56401\project\tp\pclk"
a = np.asarray(Image.open(os.path.join(D, "recovered_rec1.png")).convert("RGB")).astype(np.int32)
b = np.asarray(Image.open(os.path.join(D, "recovered_rec2.png")).convert("RGB")).astype(np.int32)
print("screenshot size:", a.shape)
d = np.abs(a - b).mean(axis=2)
H, W = d.shape
print("overall mean|rec1-rec2| = %.3f" % d.mean())
# the cam3 panel is the right-most strip in the 3-up layout
third = W // 3
for i, (name, sl) in enumerate([("left(cam1)", slice(0, third)),
                                ("mid(cam2)", slice(third, 2 * third)),
                                ("right(cam3)", slice(2 * third, W))]):
    print("  %-12s mean|diff| = %.3f  (%%pixels changed>8: %.2f%%)"
          % (name, d[:, sl].mean(), 100.0 * (d[:, sl] > 8).mean()))
Image.fromarray(np.concatenate([a.astype(np.uint8), b.astype(np.uint8)], axis=0)).save(
    os.path.join(D, "png", "recovered_pair.png"))
print("saved png/recovered_pair.png")
