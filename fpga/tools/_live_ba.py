# -*- coding: utf-8 -*-
"""Did the rebuild also improve cam3's LIVE image?  old (frz_run_*) vs new (c3_*)."""
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\tp"
W, H = 640, 480


def load(rel):
    d = open(BASE + "\\" + rel, "rb").read()
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


def stats(name, A, B):
    d = np.abs(A - B).mean(axis=2)
    LA = (A[:, :, 0] * 299 + A[:, :, 1] * 587 + A[:, :, 2] * 114) // 1000
    LB = (B[:, :, 0] * 299 + B[:, :, 1] * 587 + B[:, :, 2] * 114) // 1000
    m = (LA < 30) & (LB < 30)
    dG = np.abs(A[:, :, 1] - B[:, :, 1])
    print("  %-18s meanL=%5.1f  mean|A-B|=%6.2f  dark-flat |dG|=%6.2f (n=%d)"
          % (name, LA.mean(), d.mean(), dG[m].mean() if m.sum() else -1, m.sum()))


o1, o2, o3 = (load("frz_run_%s.ppm" % s) for s in "abc")
n1, n2 = load(r"cmp\c3_1.ppm"), load(r"cmp\c3_2.ppm")
print("OLD bitstream, live (no test pattern):")
stats("frz_run a-b", o1, o2)
stats("frz_run a-c", o1, o3)
print("NEW bitstream, live (no test pattern):")
stats("c3_1 - c3_2", n1, n2)
