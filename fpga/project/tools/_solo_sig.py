# -*- coding: utf-8 -*-
"""Row-signature structure: is the frame one pattern with a few tears, or a chaotic mix?"""
import sys
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W, H = 640, 480


def load(p):
    d = open(p, "rb").read()
    i = 0
    toks = []
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


def run(a, name):
    L = lum(a)
    print("=== %s ===" % name)
    print("  per-row mean luma: min %.1f max %.1f" % (L.mean(axis=1).min(), L.mean(axis=1).max()))
    print("  per-col mean luma: min %.1f max %.1f" % (L.mean(axis=0).min(), L.mean(axis=0).max()))
    # signature: downsample each row to 64 bins
    sig = L.reshape(H, 64, W // 64).mean(axis=2)
    # modal signature
    ref = np.median(sig, axis=0)
    d = np.abs(sig - ref).mean(axis=1)
    print("  rows within 8 of median-signature: %.1f%%   within 24: %.1f%%" % (
        100 * (d < 8).mean(), 100 * (d < 24).mean()))
    # print a compact view of 12 evenly spaced rows: u8 per 64 bins
    for r in range(0, H, 40):
        v = sig[r]
        print("   r%03d  %s" % (r, " ".join("%3d" % int(x) for x in v[::4])))


base = r"C:\Users\NineSun\Desktop\ov56401\project\tp"
for nm in ("solo_base_ping_b", "solo_only_ping_b", "solo_only_ping_a"):
    run(load(base + "\\" + nm + ".ppm"), nm)
