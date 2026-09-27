# -*- coding: utf-8 -*-
"""Compare frozen-repeated dumps vs running dumps."""
import itertools
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W, H = 640, 480
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp"


def load(p):
    d = open(p, "rb").read()
    i, toks = 0, []
    while len(toks) < 4:
        while d[i:i + 1].isspace():
            i += 1
        j = i
        while not d[j:j + 1].isspace():
            j += 1
        toks.append(d[i:j])
        i = j
    i += 1
    return np.frombuffer(d[i:i + W * H * 3], dtype=np.uint8).reshape(H, W, 3).astype(np.int32)


def lum(a):
    return (a[:, :, 0] * 299 + a[:, :, 1] * 587 + a[:, :, 2] * 114) // 1000


def pair(a, b):
    la, lb = lum(load(BASE + "\\" + a + ".ppm")), lum(load(BASE + "\\" + b + ".ppm"))
    d = np.abs(la - lb)
    ca, cb = la.flatten() - la.mean(), lb.flatten() - lb.mean()
    corr = float((ca @ cb) / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
    print("  %-16s vs %-16s  mean|diff|=%6.2f  max=%4d  corr=%+.4f  frac>8=%.4f"
          % (a, b, d.mean(), d.max(), corr, (d > 8).mean()))


print("=== RUNNING dumps (frame advancing during dump) ===")
for a, b in itertools.combinations(["frz_run_a", "frz_run_b", "frz_run_c"], 2):
    pair(a, b)
print()
print("=== FROZEN dumps (same DDR bytes, camera stopped) ===")
for a, b in itertools.combinations(["frz_frozen_a", "frz_frozen_b", "frz_frozen_c"], 2):
    pair(a, b)
print()
for nm in ("frz_run_a", "frz_frozen_a"):
    a = load(BASE + "\\" + nm + ".ppm")
    L = lum(a)
    print("%s: rowmean min/max %.1f/%.1f  colmean min/max %.1f/%.1f"
          % (nm, L.mean(axis=1).min(), L.mean(axis=1).max(),
             L.mean(axis=0).min(), L.mean(axis=0).max()))
