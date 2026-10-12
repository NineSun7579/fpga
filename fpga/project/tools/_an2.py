# -*- coding: utf-8 -*-
"""_an2.py : exact stripe period on a source-resolution cam frame."""
import sys
import numpy as np
from PIL import Image

im = Image.open(sys.argv[1]).convert('L')
a = np.asarray(im).astype(np.float64)
h, w = a.shape
print('shape (h,w) =', a.shape)

# 1) mean |d| vs horizontal shift p
print('--- mean|G(x+p)-G(x)| (all rows) ---')
for p in range(1, 17):
    d = np.abs(a[:, p:] - a[:, :-p]).mean()
    print('   p=%2d : %7.4f' % (p, d))

# 2) column-average profile (the stripe pattern is column-periodic)
col = a.mean(axis=0)
c0 = col - col.mean()
ac = np.fft.irfft(np.abs(np.fft.rfft(c0)) ** 2)
ac = ac / ac[0]
pk = [(lag, round(float(ac[lag]), 3)) for lag in range(2, 40)
      if ac[lag] > ac[lag - 1] and ac[lag] > ac[lag + 1] and ac[lag] > 0.2]
print('--- column-profile autocorr peaks ---')
print('  ', pk[:8])

# 3) dominant horizontal frequency via 2D FFT (row-averaged spectrum)
F = np.fft.rfft(c0)
mag = np.abs(F)
mag[0:2] = 0
top = np.argsort(mag)[::-1][:6]
print('--- top horizontal frequencies of the column profile ---')
for k in sorted(top):
    print('   k=%3d  period=%6.2f px  mag=%.1f' % (k, w / k if k else 0, mag[k]))

# 4) print the column profile so the pattern is visible
print('--- column profile G[0:80] ---')
print('  ', ' '.join('%5.1f' % v for v in col[:80]))

# 5) which rows are worst (stripe strength per row): mean|d1| / mean|d4|
r1 = np.abs(a[:, 1:] - a[:, :-1]).mean(axis=1)
r4 = np.abs(a[:, 4:] - a[:, :-4]).mean(axis=1)
ratio = (r1 - r4)
print('--- per-row (mean|d1|-mean|d4|): min/median/max ---')
print('   %.3f / %.3f / %.3f' % (ratio.min(), np.median(ratio), ratio.max()))
