#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the WARBFIX DDR frames: per-camera ping/pong stability, cam2/cam3 vs cam1.

Reads c1_raw.ppm c2_raw.ppm c3_raw.ppm c2p_raw.ppm c3p_raw.ppm (640x480 P6)
produced by tools/dump3.py and prints quantitative evidence.
"""
import sys
import numpy as np

W, H = 640, 480


def load(path):
    d = open(path, 'rb').read()
    assert d[:2] == b'P6', path
    # header: P6\n640 480\n255\n
    parts = d.split(b'\n', 3)
    body = parts[3]
    a = np.frombuffer(body, dtype=np.uint8)[:W * H * 3].reshape(H, W, 3).astype(np.float32)
    return a


def gray(a):
    return a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def pearson(x, y):
    x = x.ravel() - x.mean()
    y = y.ravel() - y.mean()
    d = np.sqrt((x @ x) * (y @ y))
    return float(x @ y / d) if d else 0.0


def norm_mad(x, y):
    a, b = x.ravel(), y.ravel()
    return float(np.abs(a - b).mean() / (np.abs(a - b).astype(np.float64).mean() + abs(a.mean() - b.mean()) + 1e-9))


def main():
    names = ['c1', 'c2', 'c3', 'c2p', 'c3p']
    img = {n: load(n + '_raw.ppm') for n in names}
    g = {n: gray(img[n]) for n in names}

    print('== content (percent of pixels with luma>16) ==')
    for n in names:
        print(f'  {n}: {100.0 * (g[n] > 16).mean():5.1f}%')

    print('== ping vs pong stability (same camera; high = stable, no tearing) ==')
    for cam, ping, pong in (('cam1', 'c1', 'c1'), ('cam2', 'c2', 'c2p'), ('cam3', 'c3', 'c3p')):
        if ping == pong:
            print(f'  {cam}: (no pong dumped)')
            continue
        print(f'  {cam}: pearson={pearson(g[ping], g[pong]):.3f}')

    print('== cam2 / cam3 vs cam1 (same scene? high = clean copy) ==')
    for cam in ('c2', 'c3'):
        print(f'  {cam} vs c1: pearson={pearson(g[cam], g["c1"]):.3f}')

    print('== per-row hard-seam detector (max |col diff| of column-mean luma) ==')
    for n in names:
        col = g[n].mean(axis=0)
        d = np.abs(np.diff(col))
        seam = int(np.argmax(d))
        print(f'  {n}: seam_col={seam:3d} strength={d[seam]:6.2f} (mean {d.mean():5.2f})')


if __name__ == '__main__':
    main()
