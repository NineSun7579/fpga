# -*- coding: utf-8 -*-
"""Analyse the new-bitstream verification frames."""
import itertools
import os
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


def pair(a, b):
    A, B = load(BASE + "\\" + a + ".ppm").astype(np.float64), load(BASE + "\\" + b + ".ppm").astype(np.float64)
    d = np.abs(A - B).mean(axis=2)
    ca, cb = A.ravel() - A.mean(), B.ravel() - B.mean()
    corr = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
    print("  %-12s vs %-12s  mean|d|=%6.3f max=%3d corr=%+.4f frac>8=%.5f"
          % (a, b, d.mean(), d.max(), corr, (d > 8).mean()))


print("== colour-bar frames (NEW bitstream) ==")
for a, b in itertools.combinations(["bar_ping_1", "bar_ping_2", "bar_ping_3", "bar_pong_1",
                                    "bar_pong_2"], 2):
    pair(a, b)

print("== frozen dumps (read-path identity) ==")
for a, b in itertools.combinations(["frz2_a", "frz2_b", "frz2_c"], 2):
    pair(a, b)


def structure(name, path):
    a = load(path)
    L = (a[:, :, 0] * 299 + a[:, :, 1] * 587 + a[:, :, 2] * 114) // 1000
    ref = L[240]
    same = [r for r in range(H) if np.abs(L[r] - ref).mean() < 6]
    edges = (np.abs(np.diff(L, axis=1)) > 60).sum(axis=1)
    print("  %-22s  rows like r240: %5.1f%%   vert-edges/row mean=%.2f  hist=%s"
          % (name, 100.0 * len(same) / H, edges.mean(),
             np.bincount(edges, minlength=10)[:10].tolist()))
    print("      row means every 60 rows: %s"
          % " ".join("%.0f" % L[r].mean() for r in range(0, H, 60)))


print("== structure: NEW vs OLD frozen frame ==")
structure("NEW frz2_a", BASE + "\\frz2_a.ppm")
structure("NEW bar_ping_1", BASE + "\\bar_ping_1.ppm")
try:
    structure("OLD frz_frozen_a", OLD + "\\frz_frozen_a.ppm")
except Exception as e:  # noqa: BLE001
    print("  (old missing)", e)
