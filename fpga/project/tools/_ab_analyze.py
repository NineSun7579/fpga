# -*- coding: utf-8 -*-
"""Analyse the cam3 PCLK A/B dumps: temporal noise, scene stability, montage."""
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\NineSun\Desktop\ov56401\project\tp\pclk"
NAMES = ["pclk84_a", "pclk84_b", "pclk84_pong", "pclk54_a", "pclk54_b", "pclk54_pong"]


def load(n):
    return np.asarray(Image.open(os.path.join(D, n + ".ppm"))).astype(np.int32)


imgs = {n: load(n) for n in NAMES}


def mad(a, b):
    return float(np.abs(a - b).mean())


print("--- overall mean|A-B| ---")
print("84 temporal (a vs b)  : %.3f" % mad(imgs["pclk84_a"], imgs["pclk84_b"]))
print("54 temporal (a vs b)  : %.3f" % mad(imgs["pclk54_a"], imgs["pclk54_b"]))
print("84a vs 54a (scene)    : %.3f" % mad(imgs["pclk84_a"], imgs["pclk54_a"]))
print("84 pong vs 84a (scene): %.3f" % mad(imgs["pclk84_pong"], imgs["pclk84_a"]))
print("54 pong vs 54a (scene): %.3f" % mad(imgs["pclk54_pong"], imgs["pclk54_a"]))


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


print("\n--- mean luma (brightness) ---")
for n in NAMES:
    print("  %-14s %.1f" % (n, luma(imgs[n]).mean()))

# temporal noise split by brightness, using the 84a frame as reference
L = luma(imgs["pclk84_a"])
dark = L < 60
bright = L > 140
print("\n--- temporal mean|A-B| by brightness ---")
for n0, n1 in (("pclk84_a", "pclk84_b"), ("pclk54_a", "pclk54_b")):
    d = np.abs(imgs[n0] - imgs[n1]).mean(axis=2)
    print("  %s: dark %.3f  bright %.3f" % (n0[:7], d[dark].mean(), d[bright].mean()))

# green-speckle proxy: green-dominant pixel fraction in dark areas
print("\n--- green-speckle proxy (dark areas) ---")
for n in NAMES:
    a = imgs[n]
    gdom = (a[:, :, 1] - np.maximum(a[:, :, 0], a[:, :, 2])) > 24
    print("  %-14s %.3f%%" % (n, 100.0 * gdom[dark].mean()))

# save PNGs + a 2x2 montage for visual inspection
os.makedirs(os.path.join(D, "png"), exist_ok=True)
for n in NAMES:
    Image.fromarray(imgs[n].astype(np.uint8)).save(os.path.join(D, "png", n + ".png"))
tiles = [imgs["pclk84_a"], imgs["pclk84_b"], imgs["pclk54_a"], imgs["pclk54_b"]]
H, W = tiles[0].shape[:2]
mont = np.zeros((2 * H, 2 * W, 3), np.uint8)
for i, t in enumerate(tiles):
    mont[(i // 2) * H:(i // 2 + 1) * H, (i % 2) * W:(i % 2 + 1) * W] = t.astype(np.uint8)
Image.fromarray(mont).resize((W, H)).save(os.path.join(D, "png", "montage_2x2.png"))
print("\nsaved png/ (montage_2x2.png = 84a|84b / 54a|54b)")
