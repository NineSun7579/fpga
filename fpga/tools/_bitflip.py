# -*- coding: utf-8 -*-
"""Are cam3's frame-to-frame pixel changes bit-flip quantised (open DVP lane)
or continuous (analog noise)?

RGB565 -> RGB888 expansion multiplies each channel by a power of two, so a
single-bit error appears as a delta of exactly 8/16/32/64...  Analog noise
gives a smooth delta distribution.
"""
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\cmp"


def pair(n1, n2):
    A = np.asarray(Image.open(BASE + "\\" + n1 + ".ppm")).astype(np.int32)
    B = np.asarray(Image.open(BASE + "\\" + n2 + ".ppm")).astype(np.int32)
    print("== %s vs %s ==" % (n1, n2))
    for ch, idx in (("R", 0), ("G", 1), ("B", 2)):
        d = np.abs(A[:, :, idx] - B[:, :, idx]).ravel()
        nz = d[d > 0]
        if nz.size == 0:
            print("   %s: no change" % ch)
            continue
        vals, cnts = np.unique(nz, return_counts=True)
        top = sorted(zip(cnts, vals), reverse=True)[:8]
        frac0 = 1.0 - nz.size / d.size
        print("   %s: unchanged=%.3f  nonzero=%d  top deltas=%s"
              % (ch, frac0, nz.size,
                 " ".join("%d:%d" % (v, c) for c, v in top)))


pair("c1_1", "c1_2")
pair("c3_1", "c3_2")
