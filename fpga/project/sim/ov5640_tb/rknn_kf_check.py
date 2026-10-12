#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rknn_kf_check.py -- Stage-2 (真模型侧) 验证, 在 WSL 里用 rknn-toolkit2 模拟器运行
                    由 yolo26n_std.onnx 构建的 RK3568 模型, 比较:
                      干净帧 / 加噪帧 / vip_kf 时域滤波帧 的检测行为.

依据工程自带配方 wsl_tools/convert_std.py:
    rknn.config(mean_values=[[0,0,0]], std_values=[[255,255,255]], target_platform='rk3568')
    rknn.load_onnx(...) ; rknn.build(do_quantization=<...>)

用法 (WSL):
  python3 rknn_kf_check.py [--img PATH] [--nframes 6] [--sigma 6] [--gain auto|0|1|2|3]
                           [--quant]     # 加 --quant 走 int8 量化(需 calib dataset)
"""
import argparse
import os
import numpy as np
import cv2

ROOT = "/mnt/c/Users/NineSun/Desktop/ov56401/project"
ONNX = ROOT + "/control_model/yolo26n_std.onnx"
DS = ROOT + "/calib_png/dataset_linux.txt"
DEF_IMG = ROOT + "/migration/RK3568_PG100H-release/VS_C++/Yolov5/img/000001.jpg"

T0, T1, T2 = 3, 8, 20
FIXED = None


def kf_ch(z, x):
    if FIXED is not None:
        if FIXED == 0:
            return (3 * x + z) >> 2
        if FIXED == 1:
            return (x + z) >> 1
        if FIXED == 2:
            return (x + 3 * z) >> 2
        return z
    d = np.abs(z - x)
    out = np.empty_like(z)
    out[d < T0] = (3 * x[d < T0] + z[d < T0]) >> 2
    m = (d >= T0) & (d < T1)
    out[m] = (x[m] + z[m]) >> 1
    m = (d >= T1) & (d < T2)
    out[m] = (x[m] + 3 * z[m]) >> 2
    out[d >= T2] = z[d >= T2]
    return out


def kf_px(z, x):
    z = z.astype(np.int32)
    x = x.astype(np.int32)
    r = kf_ch((z >> 11) & 31, (x >> 11) & 31)
    g = kf_ch((z >> 5) & 63, (x >> 5) & 63)
    b = kf_ch(z & 31, x & 31)
    return ((r & 31) << 11) | ((g & 63) << 5) | (b & 31)


def kf_seq(frames):
    out = [frames[0].copy()]
    st = frames[0].copy()
    for f in range(1, len(frames)):
        st = kf_px(frames[f], st).astype(np.uint16)
        out.append(st.copy())
    return out


def to565(rgb):
    r = rgb[..., 0].astype(np.uint16)
    g = rgb[..., 1].astype(np.uint16)
    b = rgb[..., 2].astype(np.uint16)
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def to888(px):
    px = px.astype(np.uint16)
    r5 = (px >> 11) & 31
    g6 = (px >> 5) & 63
    b5 = px & 31
    return np.stack([(r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4),
                     (b5 << 3) | (b5 >> 2)], -1).astype(np.uint8)


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    ub = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (ua + ub - inter) if ua + ub - inter > 0 else 0.0


def nms(dets, thr=0.45):
    dets = sorted(dets, key=lambda d: -d[4])
    keep, sup = [], [False] * len(dets)
    for i in range(len(dets)):
        if sup[i]:
            continue
        keep.append(dets[i])
        for j in range(i + 1, len(dets)):
            if not sup[j] and dets[j][5] == dets[i][5] and iou(dets[i], dets[j]) > thr:
                sup[j] = True
    return keep


def letterbox(img, m=640):
    h, w = img.shape[:2]
    s = min(m / w, m / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    c = np.zeros((m, m, 3), np.uint8)
    ox, oy = (m - nw) // 2, (m - nh) // 2
    c[oy:oy + nh, ox:ox + nw] = cv2.resize(img, (nw, nh))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=DEF_IMG)
    ap.add_argument("--nframes", type=int, default=6)
    ap.add_argument("--sigma", type=float, default=6.0)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--gain", default="auto")
    ap.add_argument("--quant", action="store_true")
    args = ap.parse_args()

    global FIXED
    FIXED = None if args.gain == "auto" else int(args.gain)

    from rknn.api import RKNN
    print("build model from onnx (quant=%s) ..." % args.quant)
    r = RKNN(verbose=False)
    r.config(mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]],
             target_platform="rk3568")
    assert r.load_onnx(model=ONNX) == 0
    if args.quant:
        assert r.build(do_quantization=True, dataset=DS) == 0
    else:
        assert r.build(do_quantization=False) == 0
    assert r.init_runtime() == 0

    img = cv2.cvtColor(cv2.imread(args.img), cv2.COLOR_BGR2RGB)
    clean = letterbox(img)
    print("image %s -> %s  gain=%s" % (args.img, clean.shape, args.gain))

    rng = np.random.default_rng(1234)
    c565 = to565(clean)
    frames = []
    for f in range(args.nframes):
        n = rng.normal(0, args.sigma, c565.shape)
        frames.append(np.clip(c565.astype(np.int32) + np.round(n), 0, 65535).astype(np.uint16))
    filt = kf_seq(frames)

    outs = r.inference(inputs=[clean[np.newaxis, ...]])
    o = np.asarray(outs[0])
    print("out shape", o.shape, "min %.3f max %.3f" % (o.min(), o.max()))
    y = o[0] if o.ndim == 3 else o
    if y.shape[0] < y.shape[1]:
        nc = y.shape[0] - 4
    else:
        nc = y.shape[1] - 4
    print("assumed nc=%d  (raw y shape %s)" % (nc, y.shape))

    def infer(a):
        oo = np.asarray(r.inference(inputs=[a[np.newaxis, ...]])[0])
        yy = oo[0] if oo.ndim == 3 else oo
        if yy.shape[0] < yy.shape[1]:
            cx, cy, w, h = yy[0], yy[1], yy[2], yy[3]
            sc = yy[4:4 + nc]
        else:
            sc = yy[:, 4:].T
            cx, cy, w, h = yy[:, 0], yy[:, 1], yy[:, 2], yy[:, 3]
        best = np.argmax(sc, 0)
        bs = sc[best, np.arange(sc.shape[1])]
        k = bs >= args.conf
        cand = [(cx[a] - w[a] / 2, cy[a] - h[a] / 2, cx[a] + w[a] / 2,
                 cy[a] + h[a] / 2, float(bs[a]), int(best[a])) for a in np.nonzero(k)[0]]
        return nms(cand), float(bs.max())

    d0, s0 = infer(clean)
    print("clean  boxes=%d maxScore=%.3f" % (len(d0), s0))
    dn, df = [], []
    for m in [to888(f) for f in frames]:
        d, s = infer(m)
        dn.append(d)
    for m in [to888(f) for f in filt]:
        d, s = infer(m)
        df.append(d)
    print("noisy  boxes/frame: %s (mean %.1f)" % ([len(d) for d in dn], np.mean([len(d) for d in dn])))
    print("filt   boxes/frame: %s (mean %.1f)" % ([len(d) for d in df], np.mean([len(d) for d in df])))

    def stab(seq):
        v = [max([iou(a, b) for a in seq[i - 1] for b in seq[i] if a[5] == b[5]] or [0])
             for i in range(1, len(seq))]
        return np.mean(v)
    print("adjacent-frame best same-class IoU: noisy=%.3f filt=%.3f" % (stab(dn), stab(df)))


if __name__ == "__main__":
    main()
