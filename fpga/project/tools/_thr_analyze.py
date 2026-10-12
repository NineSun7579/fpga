# -*- coding: utf-8 -*-
"""Diff the two throughput screenshots (liveness check)."""
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\NineSun\Desktop\ov56401\project\tp\pclk48"
a = np.asarray(Image.open(os.path.join(D, "throughput_th1.png")).convert("RGB")).astype(np.int32)
b = np.asarray(Image.open(os.path.join(D, "throughput_th2.png")).convert("RGB")).astype(np.int32)
d = np.abs(a - b).mean(axis=2)
H, W = d.shape
print("size:", a.shape, "overall mean|diff| = %.3f" % d.mean())
third = W // 3
for name, sl in (("left(cam1)", slice(0, third)),
                 ("mid(cam2)", slice(third, 2 * third)),
                 ("right(cam3)", slice(2 * third, W))):
    print("  %-12s mean|diff| = %.3f" % (name, d[:, sl].mean()))
