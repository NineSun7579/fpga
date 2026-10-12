# -*- coding: utf-8 -*-
"""Compare cam3 84 MHz vs 48 MHz dumps."""
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\NineSun\Desktop\ov56401\project\tp\pclk48"
NAMES = ["p48_base_a", "p48_base_b", "p48_48_a", "p48_48_b", "p48_rest_a"]


def load(n):
    return np.asarray(Image.open(os.path.join(D, n + ".ppm"))).astype(np.int32)


imgs = {n: load(n) for n in NAMES}


def mad(a, b):
    return float(np.abs(a - b).mean())


print("--- mean|A-B| ---")
print("84 temporal (base_a vs base_b) : %.3f" % mad(imgs["p48_base_a"], imgs["p48_base_b"]))
print("48 temporal (48_a vs 48_b)     : %.3f" % mad(imgs["p48_48_a"], imgs["p48_48_b"]))
print("base_a vs 48_a                 : %.3f" % mad(imgs["p48_base_a"], imgs["p48_48_a"]))
print("base_a vs rest_a               : %.3f" % mad(imgs["p48_base_a"], imgs["p48_rest_a"]))


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


print("\n--- mean luma ---")
for n in NAMES:
    print("  %-14s %.1f" % (n, luma(imgs[n]).mean()))

L = luma(imgs["p48_base_a"])
dark = L < 60
bright = L > 140
print("\n--- temporal 暗区/亮区 ---")
for n0, n1 in (("p48_base_a", "p48_base_b"), ("p48_48_a", "p48_48_b")):
    d = np.abs(imgs[n0] - imgs[n1]).mean(axis=2)
    print("  %s: dark %.3f  bright %.3f" % (n0, d[dark].mean(), d[bright].mean()))

os.makedirs(os.path.join(D, "png"), exist_ok=True)
for n in NAMES:
    Image.fromarray(imgs[n].astype(np.uint8)).save(os.path.join(D, "png", n + ".png"))
# 3-up: 84 base | 48 | restored 84
tiles = [imgs["p48_base_a"], imgs["p48_48_a"], imgs["p48_rest_a"]]
H, W = tiles[0].shape[:2]
mont = np.zeros((H, 3 * W, 3), np.uint8)
for i, t in enumerate(tiles):
    mont[:, i * W:(i + 1) * W] = t.astype(np.uint8)
Image.fromarray(mont).save(os.path.join(D, "png", "montage_84_48_84.png"))
print("\nsaved png/ (montage_84_48_84.png)")
