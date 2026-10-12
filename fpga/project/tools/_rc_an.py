# -*- coding: utf-8 -*-
"""Analyse the recheck frames: stability, shift, structure, normal-mode content."""
import itertools
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W, H = 640, 480
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp\rc"


def load(n):
    d = open(BASE + "\\" + n + ".ppm", "rb").read()
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


def shift_pair(a, b, row=240):
    A, B = a[row].mean(axis=1), b[row].mean(axis=1)
    best = min(((s, np.abs((A[s:] if s >= 0 else A[:W + s]) -
                           (B[:W - s] if s >= 0 else B[-s:])).mean())
                for s in range(-400, 401)), key=lambda t: t[1])
    return best


def report(n1, n2):
    A, B = load(n1), load(n2)
    d = np.abs(A - B).mean(axis=2)
    ca, cb = A.ravel() - A.mean(), B.ravel() - B.mean()
    corr = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
    s, r = shift_pair(A, B)
    print("  %-12s vs %-12s mean|d|=%7.3f corr=%+.4f  best row-shift=%+4d (resid %5.1f)"
          % (n1, n2, d.mean(), corr, s, r))


def structure(n):
    a = load(n)
    L = (a[:, :, 0] * 299 + a[:, :, 1] * 587 + a[:, :, 2] * 114) // 1000
    ref = L[240]
    same = [r for r in range(H) if np.abs(L[r] - ref).mean() < 6]
    edges = (np.abs(np.diff(L, axis=1)) > 60).sum(axis=1)
    print("  %-12s rows~r240=%5.1f%%  vert-edges/row=%.2f  rowmeans[0,60,..420]=%s"
          % (n, 100.0 * len(same) / H, edges.mean(),
             " ".join("%.0f" % L[r].mean() for r in range(0, H, 60))))


print("== colour bar stability ==")
for a, b in itertools.combinations(["rc_bar_1", "rc_bar_2", "rc_bar_3", "rc_bar_pong"], 2):
    report(a, b)
print("== normal mode (live scene) stability ==")
for a, b in itertools.combinations(["rc_norm_1", "rc_norm_2", "rc_norm_3"], 2):
    report(a, b)
print("== structure ==")
for n in ("rc_bar_1", "rc_norm_1", "rc_norm_2"):
    structure(n)
