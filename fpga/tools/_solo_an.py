# -*- coding: utf-8 -*-
"""Analyse cam3 solo-vs-baseline tear structure.

For each PPM:
  * back-to-back diff vs its partner
  * per-row best integer horizontal shift against the per-column median row
    (valid because the colour-bar pattern is vertically near-uniform)
Then summarise: how many rows sit at shift 0 vs displaced by +/-8/16/128 etc.
"""
import sys
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W, H = 640, 480


def load(p):
    d = open(p, "rb").read()
    # skip P6 header
    i = 0
    toks = []
    while len(toks) < 4:
        # read a token
        while d[i:i + 1].isspace():
            i += 1
        if d[i:i + 1] == b"#":
            while d[i:i + 1] != b"\n":
                i += 1
            continue
        j = i
        while not d[j:j + 1].isspace():
            j += 1
        toks.append(d[i:j])
        i = j
    i += 1
    a = np.frombuffer(d[i:i + W * H * 3], dtype=np.uint8).reshape(H, W, 3).astype(np.int32)
    return a


def lum(a):
    return (a[:, :, 0] * 299 + a[:, :, 1] * 587 + a[:, :, 2] * 114) // 1000


def shift_row(row, ref, maxs=200):
    # brute-force integer shift, compare on the overlapping centre band
    best, bs = 1e18, 0
    lo, hi = maxs, W - maxs
    for s in range(-maxs, maxs + 1):
        a = row[lo:hi]
        b = ref[lo + s:hi + s]
        dd = np.abs(a - b).mean()
        if dd < best:
            best, bs = dd, s
    return bs, best


def analyse(name, p):
    a = load(p)
    L = lum(a)
    ref = np.median(L, axis=0)
    # only compare rows to ref in the interior
    shifts = []
    for r in range(H):
        s, e = shift_row(L[r], ref)
        shifts.append(s)
    sh = np.array(shifts)
    frac0 = (sh == 0).mean()
    # runs of nonzero
    runs = []
    i = 0
    while i < H:
        if sh[i] != 0:
            j = i
            while j < H and sh[j] == sh[i]:
                j += 1
            if j - i >= 2:
                runs.append((i, j - 1, int(sh[i])))
            i = j
        else:
            i += 1
    # histogram of shift values
    vals, cnts = np.unique(sh, return_counts=True)
    top = sorted(zip(cnts, vals), reverse=True)[:6]
    print("%-22s shift==0 %.1f%%  top: %s" % (
        name, 100 * frac0,
        " ".join("%d:%d" % (v, c) for c, v in top)))
    if runs:
        for r in runs[:12]:
            print("      run rows %3d-%3d  shift %+d" % r)
    return sh


def pair(a, b):
    A, B = load(a), load(b)
    la, lb = lum(A), lum(B)
    d = np.abs(la - lb)
    ca = la.flatten() - la.mean()
    cb = lb.flatten() - lb.mean()
    corr = float((ca @ cb) / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
    print("%-40s mean|diff|=%6.1f  corr=%.4f  frac>32=%.3f" % (
        "%s vs %s" % (a.split("\\")[-1], b.split("\\")[-1]),
        d.mean(), corr, (d > 32).mean()))


base = r"C:\Users\NineSun\Desktop\ov56401\project\tp"
print("===== back-to-back stability (test pattern should be static) =====")
pair(base + r"\solo_base_ping_a.ppm", base + r"\solo_base_ping_b.ppm")
pair(base + r"\solo_base_pong_a.ppm", base + r"\solo_base_pong_b.ppm")
pair(base + r"\solo_only_ping_a.ppm", base + r"\solo_only_ping_b.ppm")
pair(base + r"\solo_only_pong_a.ppm", base + r"\solo_only_pong_b.ppm")
print()
print("===== tear structure per frame =====")
for nm in ("solo_base_ping_a", "solo_base_ping_b", "solo_base_ping_c",
           "solo_only_ping_a", "solo_only_ping_b", "solo_only_ping_c"):
    analyse(nm, base + "\\" + nm + ".ppm")
