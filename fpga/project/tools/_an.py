# -*- coding: utf-8 -*-
"""_an.py : measure the stripe period in the cam1(KF) vs cam2(raw) crop."""
import sys
import numpy as np
from PIL import Image

im = Image.open(sys.argv[1] if len(sys.argv) > 1 else 'kf_crop.jpg').convert('L')
a = np.asarray(im).astype(np.float64)
print('image shape (h,w) =', a.shape)
W = a.shape[1] // 2
L = a[:, :W]
R = a[:, W:2 * W]


def report(img, name):
    print('===', name, img.shape)
    print('  |dx| mean=%.2f   |dy| mean=%.2f' %
          (np.abs(np.diff(img, axis=1)).mean(), np.abs(np.diff(img, axis=0)).mean()))
    for axis, an in ((0, 'x'), (1, 'y')):
        p = img.mean(axis=axis)
        p = p - p.mean()
        ac = np.fft.irfft(np.abs(np.fft.rfft(p)) ** 2)
        ac = ac / ac[0]
        pk = [(lag, round(float(ac[lag]), 3)) for lag in range(2, 65)
              if ac[lag] > ac[lag - 1] and ac[lag] > ac[lag + 1] and ac[lag] > 0.2]
        print('  %s-autocorr peaks:' % an, pk[:6])
    # raw slice through a flat-ish area: print numbers so a period is obvious
    r = img.shape[0] // 2
    print('  row[%d] first 40 px:' % r, ' '.join('%3d' % v for v in img[r, :40]))
    r2 = img.shape[0] // 2 + 1
    print('  row[%d] first 40 px:' % r2, ' '.join('%3d' % v for v in img[r2, :40]))
    c = img.shape[1] // 2
    print('  col[%d] first 24 py:' % c, ' '.join('%3d' % v for v in img[:24, c]))


report(L, 'cam1 (KF)')
report(R, 'cam2 (raw)')


def zoom(img, x, y, w, h, path, k=5):
    p = np.clip(img[y:y + h, x:x + w], 0, 255).astype(np.uint8)
    Image.fromarray(p).resize((w * k, h * k), Image.NEAREST).save(path)
    print('saved', path)


zoom(L, 118, 30, 100, 100, 'zoom_cam1.png')
zoom(R, 118, 30, 100, 100, 'zoom_cam2.png')

# side-by-side zoom for direct visual comparison
zl = np.asarray(Image.open('zoom_cam1.png').convert('L'))
zr = np.asarray(Image.open('zoom_cam2.png').convert('L'))
Image.fromarray(np.hstack([zl, np.full((zl.shape[0], 8), 255, np.uint8), zr])).save('zoom_cmp.png')
print('saved zoom_cmp.png')
