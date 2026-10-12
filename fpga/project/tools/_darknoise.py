# -*- coding: utf-8 -*-
"""Temporal noise (frame-to-frame) in dark flat regions only, cam1 vs cam3."""
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\cmp"


def dark_temporal(n1, n2):
    A = np.asarray(Image.open(BASE + "\\%s.ppm" % n1)).astype(np.int32)
    B = np.asarray(Image.open(BASE + "\\%s.ppm" % n2)).astype(np.int32)
    LA = (A[:, :, 0] * 299 + A[:, :, 1] * 587 + A[:, :, 2] * 114) // 1000
    LB = (B[:, :, 0] * 299 + B[:, :, 1] * 587 + B[:, :, 2] * 114) // 1000
    m = (LA < 25) & (LB < 25)
    if m.sum() < 5000:
        print(n1, n2, "too few dark pixels", m.sum())
        return
    dG = np.abs(A[:, :, 1] - B[:, :, 1])
    dAll = np.abs(A - B).mean(axis=2)
    print("%-6s vs %-6s  dark n=%7d  mean|dG|temporal=%6.2f  mean|dRGB|temporal=%6.2f"
          % (n1, n2, m.sum(), dG[m].mean(), dAll[m].mean()))


dark_temporal("c1_1", "c1_2")
dark_temporal("c2_1", "c2_1") if False else None
dark_temporal("c3_1", "c3_2")
