# -*- coding: utf-8 -*-
"""Eyeball the frozen cam3 frame numerically: is it a static colour bar?"""
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


name = sys.argv[1] if len(sys.argv) > 1 else "frz_frozen_a"
a = load(BASE + "\\" + name + ".ppm")
R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
L = (R * 299 + G * 587 + B * 114) // 1000

print("== %s ==" % name)
print("row mean (every 20 rows):")
for r in range(0, H, 20):
    print("  r%3d  L=%6.1f  R=%6.1f G=%6.1f B=%6.1f" %
          (r, L[r].mean(), R[r].mean(), G[r].mean(), B[r].mean()))

print("col mean (every 40 cols):")
print("  " + " ".join("%4d" % L[:, c].mean() for c in range(0, W, 40)))

print("row 240 samples (R) every 20 cols:")
print("  " + " ".join("%4d" % R[240, c] for c in range(0, W, 20)))
print("row 240 samples (G):")
print("  " + " ".join("%4d" % G[240, c] for c in range(0, W, 20)))

# how many rows are (near) identical to row 240 within a small tolerance?
ref = L[240]
same = [r for r in range(H) if np.abs(L[r] - ref).mean() < 6]
print("rows with mean|L-L240|<6: %d / %d (%.1f%%)" % (len(same), H, 100.0 * len(same) / H))

# edge structure: count strong vertical edges per row (bar boundaries)
edges = (np.abs(np.diff(L, axis=1)) > 60).sum(axis=1)
print("vertical-edge count per row: min=%d max=%d mean=%.1f  (clean 8-bar -> ~7)"
      % (edges.min(), edges.max(), edges.mean()))
print("histogram of edge counts:", np.bincount(edges, minlength=12)[:12].tolist())
