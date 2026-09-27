#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stripe_check.py <frame.ppm> -- local stripe detector for a captured frame.

Computes per-channel high-pass energy and lag autocorrelation over rows;
a periodic raster (like the known period-4 defect) shows as positive
correlation at the period lag and negative around it.
"""
import sys
import numpy as np


def read_ppm(path):
    with open(path, 'rb') as f:
        data = f.read()
    # parse P6 header (skip comments)
    parts = []
    i = 0
    while len(parts) < 4:
        while i < len(data) and data[i:i+1].isspace():
            i += 1
        if data[i:i+1] == b'#':
            while i < len(data) and data[i:i+1] != b'\n':
                i += 1
            continue
        j = i
        while j < len(data) and not data[j:j+1].isspace():
            j += 1
        parts.append(data[i:j])
        i = j
    i += 1
    magic, w, h, maxv = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
    assert magic == b'P6', magic
    img = np.frombuffer(data[i:i + w*h*3], dtype=np.uint8).reshape(h, w, 3)
    return img


def main():
    img = read_ppm(sys.argv[1])
    h, w, _ = img.shape
    print('%s: %dx%d' % (sys.argv[1], w, h))
    rowmean = img.reshape(h, w, 3).mean(axis=(0, 2))  # per-column mean over rows
    hp = rowmean - np.convolve(rowmean, np.ones(9)/9, mode='same')
    energy = float(np.sqrt((hp**2).mean()))
    print('column high-pass RMS: %.3f LSB' % energy)
    ac = np.correlate(hp - hp.mean(), hp - hp.mean(), mode='full')[len(hp)-1:]
    ac = ac / (ac[0] if ac[0] else 1)
    peaks = [(lag, float(ac[lag])) for lag in (2, 3, 4, 5, 6, 7, 8)]
    print('autocorr:', ', '.join('lag%d=%.3f' % p for p in peaks))
    strong = [p for p in peaks if p[0] >= 2 and p[1] > 0.25]
    print('STRIPE DETECTED (periodic raster)' if (strong and energy > 1.0)
          else 'no significant periodic stripes')


if __name__ == '__main__':
    main()
