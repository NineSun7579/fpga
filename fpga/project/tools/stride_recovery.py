# -*- coding: utf-8 -*-
"""Stride recovery: reslice stored stream at candidate widths, score continuity."""
import numpy as np

v = np.frombuffer(open("tp/burst_credit_evidence/cam1_bank0_0.rgb565", "rb").read(),
                 dtype=np.uint16).astype(np.int32)
r = ((v >> 11) & 31) * 255.0 / 31
g = ((v >> 5) & 63) * 255.0 / 63
b = (v & 31) * 255.0 / 31
lum = 0.299 * r + 0.587 * g + 0.114 * b
N = len(lum)
print("npix", N)
res = []
for W in list(range(600, 821, 8)) + [1280, 1344, 2688]:
    if W == 640:
        pass
    nrows = N // W
    if nrows < 8:
        continue
    m = lum[: nrows * W].reshape(nrows, W)
    score = float(np.abs(m[1:] - m[:-1]).mean())
    res.append((score, W))
res.sort()
print("top coherent widths:")
for s, W in res[:12]:
    print("  W=%d score=%.3f" % (W, s))
print("W=640 score=", [s for s, W in res if W == 640])
