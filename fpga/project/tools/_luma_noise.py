# -*- coding: utf-8 -*-
"""Noise vs local luminance: is cam3's speckle just darkness-driven gain noise?

For cam1 and cam3, bin pixels by local luma and report mean |dG/dx| per bin.
If cam3's noise at matched luma is much larger than cam1's, it is a defect;
if comparable, the speckle is simply normal sensor noise in a darker scene.
"""
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\cmp"


def analyse(nm):
    a = np.asarray(Image.open(BASE + "\\" + nm + ".ppm")).astype(np.int32)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    L = (R * 299 + G * 587 + B * 114) // 1000
    dG = np.abs(np.diff(G, axis=1))
    Lm = np.minimum(L[:, :-1], L[:, 1:])
    loc = Lm.ravel()
    d = dG.ravel()
    print("== %s ==" % nm)
    for lo in range(0, 160, 20):
        m = (loc >= lo) & (loc < lo + 20)
        if m.sum() > 2000:
            print("   luma[%3d-%3d): n=%7d  mean|dG/dx|=%6.2f" % (lo, lo + 20, m.sum(), d[m].mean()))
    print("   overall mean|dG/dx|=%.2f  meanL=%.1f" % (d.mean(), L.mean()))


for nm in ("c1_1", "c2_1", "c3_1"):
    analyse(nm)
