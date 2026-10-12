#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vip_kf_yolo_check.py -- Stage-2 验证: 滤波后的图像喂给真实 YOLO26 ONNX 模型,
                       与原始(未滤波)图像比较检测行为.

依据:
  * vip_kf.v 的位精确黄金模型 (与 ModelSim 仿真逐位一致, 见 vip_kf_compare.py).
  * host/detview 的模型契约: 输入 640x640 RGB(f32, 模型内 mean0/std255),
    输出 [1,84,8400] (cx,cy,w,h + 80类), std 头 + class-aware NMS.

流程:
  1) 取一张真实标定帧 (calib/*.ppm, 已 letterbox 到 640x640).
  2) 转 RGB565 (相机线格式) 作为"干净帧".
  3) 造 N 帧序列: 干净帧 + 逐帧独立噪声 (模拟传感器噪声) —— 相当于相机连续输出.
  4) 用位精确 KF 逐帧时域滤波 (首帧 passthrough), 得到"滤波帧".
  5) 分别对 干净帧 / 每帧噪声帧 / 滤波帧 跑 ONNX 检测, 比较:
        - PSNR(相对干净帧): 噪声 vs 滤波
        - 检测框数量/类别/置信度
        - 时域稳定性: 相邻帧同目标框的 IoU 抖动

用法:
  python sim/ov5640_tb/vip_kf_yolo_check.py [--img calib/img00.ppm]
         [--nframes 8] [--sigma 8] [--conf 0.25] [--nms 0.45]
"""
import argparse
import os
import sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

MODEL = os.path.join(ROOT, "control_model", "yolo26n_std.onnx")

# ------------------------------------------------------------------ KF 黄金
T0, T1, T2 = 3, 8, 20
FIXED_GAIN = None   # None=自适应; 0..3=固定档位


def _kf_ch(z, x):
    """逐通道: 返回 (out, band). band 0..3 对应 K=1/4,1/2,3/4,1."""
    if FIXED_GAIN is not None:
        if FIXED_GAIN == 0:
            return ((3 * x + z) >> 2).astype(np.uint16), np.zeros(z.shape, np.uint8)
        if FIXED_GAIN == 1:
            return ((x + z) >> 1).astype(np.uint16), np.ones(z.shape, np.uint8)
        if FIXED_GAIN == 2:
            return ((x + 3 * z) >> 2).astype(np.uint16), np.full(z.shape, 2, np.uint8)
        return z.astype(np.uint16), np.full(z.shape, 3, np.uint8)
    d = np.abs(z - x)
    out = np.empty_like(z)
    band = np.empty(z.shape, dtype=np.uint8)
    m = d < T0
    out[m] = (3 * x[m] + z[m]) >> 2
    band[m] = 0
    m = (d >= T0) & (d < T1)
    out[m] = (x[m] + z[m]) >> 1
    band[m] = 1
    m = (d >= T1) & (d < T2)
    out[m] = (x[m] + 3 * z[m]) >> 2
    band[m] = 2
    m = d >= T2
    out[m] = z[m]
    band[m] = 3
    return out.astype(np.uint16), band


def kf_px(z, x):
    """z,x: uint16 RGB565 数组 (H,W). 返回 (out565, bands(H,W,3))."""
    z = z.astype(np.uint16)
    x = x.astype(np.uint16)
    zr = (z >> 11) & 0x1F
    zg = (z >> 5) & 0x3F
    zb = z & 0x1F
    xr = (x >> 11) & 0x1F
    xg = (x >> 5) & 0x3F
    xb = x & 0x1F
    r, br = _kf_ch(zr.astype(np.int32), xr.astype(np.int32))
    g, bg = _kf_ch(zg.astype(np.int32), xg.astype(np.int32))
    b, bb = _kf_ch(zb.astype(np.int32), xb.astype(np.int32))
    out = ((r.astype(np.uint16) & 0x1F) << 11) | \
          ((g.astype(np.uint16) & 0x3F) << 5) | (b.astype(np.uint16) & 0x1F)
    return out, np.stack([br, bg, bb], axis=-1)


def kf_sequence(frames565):
    """帧序列时域滤波 (首帧 passthrough). 返回 (out_frames, band_hist[4])."""
    out = [frames565[0].copy()]
    state = frames565[0].copy()
    hist = np.zeros(4, dtype=np.int64)
    for f in range(1, len(frames565)):
        o, bands = kf_px(frames565[f], state)
        out.append(o)
        state = o
        hist += np.bincount(bands.ravel(), minlength=4)
    return out, hist


# ------------------------------------------------------------- RGB565 <-> 888
def rgb888_to_565(rgb):
    r = rgb[..., 0].astype(np.uint16)
    g = rgb[..., 1].astype(np.uint16)
    b = rgb[..., 2].astype(np.uint16)
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def rgb565_to_888(px):
    px = px.astype(np.uint16)
    r5 = (px >> 11) & 0x1F
    g6 = (px >> 5) & 0x3F
    b5 = px & 0x1F
    r8 = (r5 << 3) | (r5 >> 2)
    g8 = (g6 << 2) | (g6 >> 4)
    b8 = (b5 << 3) | (b5 >> 2)
    return np.stack([r8, g8, b8], axis=-1).astype(np.uint8)


def psnr(a, b):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mse = np.mean((a - b) ** 2)
    if mse <= 1e-12:
        return 99.0
    return 10.0 * np.log10(255.0 * 255.0 / mse)


def letterbox_to_model(rgb, model=640):
    """保持宽高比缩放并居中填充黑边到 model x model (与常见 YOLO 预处理一致)."""
    h, w = rgb.shape[:2]
    s = min(model / w, model / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    resized = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR))
    canvas = np.zeros((model, model, 3), dtype=np.uint8)
    ox, oy = (model - nw) // 2, (model - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas


# ---------------------------------------------------------------- YOLO ONNX
class Yolo:
    def __init__(self, path, conf=0.25, nms=0.45):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name
        self.out = self.sess.get_outputs()[0].name
        self.conf = conf
        self.nms = nms
        shp = self.sess.get_outputs()[0].shape
        self.nc = int(shp[1]) - 4
        self.an = int(shp[2])

    def infer(self, rgb888):
        """rgb888: HxWx3 uint8. 返回 list[(x1,y1,x2,y2,score,cls)] (模型坐标).

        归一化: 该 ONNX 导出期望 [0,1] 浮点输入 (工程 RKNN 配方用
        std_values=[[255,255,255]] 提供同一缩放), 故此处 /255.
        """
        x = rgb888.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None, ...]
        y = self.sess.run([self.out], {self.inp: x})[0][0]  # [4+nc, AN]
        cx, cy, w, h = y[0], y[1], y[2], y[3]
        scores = y[4:4 + self.nc]  # [nc, AN]
        best = np.argmax(scores, axis=0)
        bs = scores[best, np.arange(scores.shape[1])]
        keep = bs >= self.conf
        cand = []
        for a in np.nonzero(keep)[0]:
            cxv, cyv, wv, hv = cx[a], cy[a], w[a], h[a]
            cand.append((cxv - wv / 2, cyv - hv / 2, cxv + wv / 2, cyv + hv / 2,
                         float(bs[a]), int(best[a])))
        return nms_class_aware(cand, self.nms), float(bs.max())


def _iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    ub = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    uni = ua + ub - inter
    return inter / uni if uni > 0 else 0.0


def nms_class_aware(dets, thr):
    dets = sorted(dets, key=lambda d: -d[4])
    keep = []
    sup = [False] * len(dets)
    for i in range(len(dets)):
        if sup[i]:
            continue
        keep.append(dets[i])
        for j in range(i + 1, len(dets)):
            if sup[j] or dets[j][5] != dets[i][5]:
                continue
            if _iou(dets[i], dets[j]) > thr:
                sup[j] = True
    return keep


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="calib/img00.ppm")
    ap.add_argument("--nframes", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--nms", type=float, default=0.45)
    ap.add_argument("--motion", type=int, default=0,
                    help=">0: 叠加一个每帧平移的亮块(像素/帧), 测试运动区跟随")
    ap.add_argument("--gain", default="auto",
                    help="auto | 0(K=1/4) | 1(K=1/2) | 2(K=3/4) | 3(K=1) 固定增益对比")
    args = ap.parse_args()

    global FIXED_GAIN
    FIXED_GAIN = None if args.gain == "auto" else int(args.gain)

    img_path = args.img if os.path.isabs(args.img) else os.path.join(ROOT, args.img)
    raw = np.asarray(Image.open(img_path).convert("RGB"))
    clean = raw if raw.shape[:2] == (640, 640) else letterbox_to_model(raw)
    print("image: %s  raw=%s  model=%s  gain=%s"
          % (img_path, raw.shape, clean.shape, args.gain))

    rng = np.random.default_rng(args.seed)
    H, W = clean.shape[:2]
    clean565 = rgb888_to_565(clean)

    # 逐帧噪声帧 (RGB565 域), 以及一个可选的运动亮块
    frames = []
    for f in range(args.nframes):
        n = rng.normal(0.0, args.sigma, size=clean565.shape)
        noisy = clean565.astype(np.int32) + np.round(n).astype(np.int32)
        noisy = np.clip(noisy, 0, 65535).astype(np.uint16)
        if args.motion > 0:
            y0 = 100 + (f * args.motion) % (H - 120)
            noisy[y0:y0 + 40, 100:180] = 0xFFFF
        frames.append(noisy)

    filt565, band_hist = kf_sequence(frames)
    print("gain-band hits (all pixels/frames): K1/4=%d K1/2=%d K3/4=%d K1=%d"
          % tuple(band_hist))

    # 转回 888 供模型
    clean_m = rgb565_to_888(clean565)
    noisy_m = [rgb565_to_888(f) for f in frames]
    filt_m = [rgb565_to_888(f) for f in filt565]

    # ---- PSNR (相对干净帧, 888 域) ----
    np_ps = [psnr(clean_m, m) for m in noisy_m]
    fp_ps = [psnr(clean_m, m) for m in filt_m]
    print("PSNR(dB) noisy : mean=%.2f min=%.2f" % (np.mean(np_ps), np.min(np_ps)))
    print("PSNR(dB) filt  : mean=%.2f min=%.2f" % (np.mean(fp_ps), np.min(fp_ps)))
    print("PSNR gain      : +%.2f dB" % (np.mean(fp_ps) - np.mean(np_ps)))

    # ---- 检测 ----
    yolo = Yolo(MODEL, args.conf, args.nms)
    print("model: %s  nc=%d  anchors=%d" % (os.path.basename(MODEL), yolo.nc, yolo.an))

    def summarize(tag, dets, smax):
        print("  %-8s boxes=%2d scoreMax=%.3f  %s" % (
            tag, len(dets), smax,
            " ".join("[c%d %.2f]" % (d[5], d[4]) for d in dets[:6])))

    print("-- detection on clean frame --")
    dc, sc = yolo.infer(clean_m)
    summarize("clean", dc, sc)

    print("-- detection per noisy frame --")
    dn = []
    for i, m in enumerate(noisy_m):
        d, s = yolo.infer(m)
        dn.append(d)
        summarize("noisy%d" % i, d, s)

    print("-- detection per filtered frame --")
    df = []
    for i, m in enumerate(filt_m):
        d, s = yolo.infer(m)
        df.append(d)
        summarize("filt%d" % i, d, s)

    # ---- 时域稳定性: 相邻帧同类别最好匹配框的 IoU ----
    def stability(tag, seq):
        vals = []
        for i in range(1, len(seq)):
            best = 0.0
            for a in seq[i - 1]:
                for b in seq[i]:
                    if a[5] == b[5]:
                        best = max(best, _iou(a, b))
            vals.append(best)
        print("  %-8s mean best-IoU(adjacent)=%.3f  min=%.3f" % (tag, np.mean(vals), np.min(vals)))

    print("-- temporal stability (adjacent-frame best same-class IoU) --")
    stability("noisy", dn)
    stability("filt", df)

    n_box_noisy = np.mean([len(d) for d in dn])
    n_box_filt = np.mean([len(d) for d in df])
    print("mean boxes: noisy=%.2f filt=%.2f clean=%d" % (n_box_noisy, n_box_filt, len(dc)))
    print("check done.")


if __name__ == "__main__":
    sys.exit(main())
