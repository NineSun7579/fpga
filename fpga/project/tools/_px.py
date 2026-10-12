# -*- coding: utf-8 -*-
"""Pixel-level look + best-shift between two frames."""
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W, H = 640, 480
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\vrfy"
OLD = r"C:\Users\NineSun\Desktop\ov56401\project\tp"


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


def row240(name, path):
    a = load(path)
    R, G, B = a[240, :, 0], a[240, :, 1], a[240, :, 2]
    L = (R * 299 + G * 587 + B * 114) // 1000
    print("%-14s R: %s" % (name, " ".join("%3d" % R[c] for c in range(0, W, 32))))
    print("%-14s G: %s" % ("", " ".join("%3d" % G[c] for c in range(0, W, 32))))
    e = np.where(np.abs(np.diff(L)) > 60)[0]
    print("%-14s strong vertical edge cols (row240): %s" % ("", e[:20].tolist()))


print("== row 240 pixel samples ==")
row240("bar_ping_1", BASE + "\\bar_ping_1.ppm")
row240("bar_ping_2", BASE + "\\bar_ping_2.ppm")
row240("bar_ping_3", BASE + "\\bar_ping_3.ppm")
row240("frz2_a", BASE + "\\frz2_a.ppm")
try:
    row240("OLD frz", OLD + "\\frz_frozen_a.ppm")
except Exception as e:  # noqa: BLE001
    print("old missing", e)


def best_shift(n1, n2):
    A = load(BASE + "\\" + n1 + ".ppm").astype(np.float64)
    B = load(BASE + "\\" + n2 + ".ppm").astype(np.float64)
    # use row 240 only, search whole-pixel shifts, report best residual
    a = A[240].mean(axis=1)
    b = B[240].mean(axis=1)
    best = None
    for s in range(-200, 201):
        if s >= 0:
            x, y = a[s:], b[:W - s]
        else:
            x, y = a[:W + s], b[-s:]
        r = np.abs(x - y).mean()
        if best is None or r < best[1]:
            best = (s, r)
    r0 = np.abs(a - b).mean()
    print("best shift %s->%s : %+d px (residual %.1f)  ; shift0 residual %.1f"
          % (n1, n2, best[0], best[1], r0))


print("== best horizontal shift (row 240) ==")
best_shift("bar_ping_1", "bar_ping_2")
best_shift("bar_ping_1", "bar_ping_3")
best_shift("bar_ping_1", "frz2_a")
