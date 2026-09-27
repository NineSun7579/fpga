# -*- coding: utf-8 -*-
"""Before/after on cam3's colour-bar capture: within-frame chaos vs stability.

tp/c3tp_* + tp/frz_frozen_* = OLD bitstream (pre IODELAY port-mode rebuild)
tp/rc/rc_bar_*              = NEW bitstream
Flats in a colour bar should be constant; any frame-to-frame change there is
capture-path corruption.
"""
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp"
W, H = 640, 480


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


def metrics(name, a, b):
    d = np.abs(a - b).mean(axis=2)
    # row-mean uniformity across rows (colour bar should be vertically uniform)
    L = (a[:, :, 0] * 299 + a[:, :, 1] * 587 + a[:, :, 2] * 114) // 1000
    rownoise = np.abs(np.diff(L, axis=0)).mean()
    # strong vertical edges per row
    edges = (np.abs(np.diff(L, axis=1)) > 60).sum(axis=1).mean()
    print("  %-14s mean|A-B|=%7.3f  row-to-row|dL|=%6.3f  vert-edges/row=%5.2f"
          % (name, d.mean(), rownoise, edges))


print("OLD bitstream (colour bar):")
a, b, c = (load(BASE + r"\c3tp_ping_%s.ppm" % s) for s in "abc")
metrics("c3tp a-b", a, b)
metrics("c3tp a-c", a, c)
print("OLD bitstream (frozen frames):")
fa, fb, fc = (load(BASE + r"\frz_frozen_%s.ppm" % s) for s in "abc")
metrics("frz a-b", fa, fb)
print("NEW bitstream (colour bar):")
na, nb, nc = (load(BASE + r"\rc\rc_bar_%d.ppm" % k) for k in (1, 2, 3))
metrics("bar 1-2", na, nb)
metrics("bar 1-3", na, nc)
