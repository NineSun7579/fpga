#!/usr/bin/env python3
"""golden_gen.py : 预处理 IP 仿真 golden 数据生成器 (任务5)

与 RTL 逐位对齐的行为模型 (source/preprocess/*)：
  rgb2gray.v  : Y = (77R + 150G + 29B) >> 8, R={r5,r5[2:0]} G={g6,g6[1:0]} B={b5,b5[2:0]}
  colorize.v  : chroma<thr_sat -> 灰度; R主->F800; G主->07E0; 黄->FFE0; 其余灰度
  sobel_edge.v: 内部像素 (row 1..H-2, col 1..W-2), mag=|Gx|+|Gy|, edge=mag>=thr
  preprocess_top.v: mode0=edge?FFFF:色化  mode1=色化  mode2=灰度  mode3=edge?FFFF:0000
输出 $readmemh 文件 (sim/preprocess/golden/):
  img.mem            激励帧 RGB565
  exp_gray.mem       灰度期望 (含对齐: 前两行与首列不产生输出的填充值 0xZZ)
  exp_color.mem      色化期望 (同上)
  exp_edge.mem       边缘位流期望
  exp_top_mode{0..3}.mem  整链期望
  exp_bypass.mem     旁路期望 (=img)
用法:
  python golden_gen.py --width 640 --height 360 --seed 1 [--case directed|random]
"""
import argparse
import random
from pathlib import Path

PURE_RED = 0xF800
PURE_YELLOW = 0xFFE0
PURE_GREEN = 0x07E0
PAD = 0x0  # 保留定义 (当前期望文件均为裸序列)

def rgb565_split(px):
    r5 = (px >> 11) & 0x1F
    g6 = (px >> 5) & 0x3F
    b5 = px & 0x1F
    return r5, g6, b5

def expand8(px):
    r5, g6, b5 = rgb565_split(px)
    return (r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)

def to_gray(px):
    r8, g8, b8 = expand8(px)
    return (77 * r8 + 150 * g8 + 29 * b8) >> 8

def gray_to_565(y):
    return ((y >> 3) << 11) | ((y >> 2) << 5) | (y >> 3)

def colorize(px, y, thr_sat, thr_hue, thr_val, thr_low):
    r5, g6, b5 = rgb565_split(px)
    r8, g8, b8 = expand8(px)
    chroma = max(r8, g8, b8) - min(r8, g8, b8)
    if chroma < thr_sat:
        return gray_to_565(y), 0
    if (r8 - g8 >= thr_hue) and (r8 - b8 >= thr_hue):
        return PURE_RED, 1
    if (g8 - r8 >= thr_hue) and (g8 - b8 >= thr_hue):
        return PURE_GREEN, 3
    if (r8 >= 32) and (g8 >= 32) and (abs(r8 - g8) < thr_hue) and (b8 <= thr_low) \
            and (r8 >= thr_val) and (g8 >= thr_val):
        return PURE_YELLOW, 2
    return gray_to_565(y), 0

def sobel_frame(gray, w, h, thr):
    """返回与 RTL 输出流一一对应的 (center_list, edge_list)"""
    centers, edges = [], []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            g = lambda rr, cc: gray[rr * w + cc]
            gx = (g(r - 1, c + 1) - g(r - 1, c - 1)) + \
                 2 * (g(r, c + 1) - g(r, c - 1)) + \
                 (g(r + 1, c + 1) - g(r + 1, c - 1))
            gy = (g(r + 1, c - 1) - g(r - 1, c - 1)) + \
                 2 * (g(r + 1, c) - g(r - 1, c)) + \
                 (g(r + 1, c + 1) - g(r - 1, c + 1))
            mag = abs(gx) + abs(gy)
            centers.append(gray[r * w + c])
            edges.append(1 if mag >= thr else 0)
    return centers, edges

def gen_image(w, h, rng, case):
    px = []
    for i in range(w * h):
        r = rng.randint(0, 31)
        g = rng.randint(0, 63)
        b = rng.randint(0, 31)
        px.append((r << 11) | (g << 5) | b)
    if case == "directed":
        # 红球 / 黄球 / 绿球 (标准色命中)
        def blob(cx, cy, rad, color):
            for yy in range(max(0, cy - rad), min(h, cy + rad + 1)):
                for xx in range(max(0, cx - rad), min(w, cx + rad + 1)):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= rad * rad:
                        px[yy * w + xx] = color
        blob(w // 4, h // 3, min(h, w) // 10, PURE_RED)
        blob(w // 2, h // 3, min(h, w) // 10, PURE_YELLOW)
        blob(3 * w // 4, h // 3, min(h, w) // 10, PURE_GREEN)
        # 饱和度边界: chroma == thr_sat-1 / thr_sat (thr_sat=96, 8bit)
        # R=200,G=200,B=104 -> chroma=96;  R=200,G=200,B=105 -> chroma=95
        def put8(y8, x8, r8, g8, b8):
            r5 = r8 >> 3; g6 = g8 >> 2; b5 = b8 >> 3
            px[y8 * w + x8] = (r5 << 11) | (g6 << 5) | b5
        if h > 4 and w > 8:
            put8(h - 2, 1, 200, 200, 104)
            put8(h - 2, 2, 200, 200, 112)
            put8(h - 2, 3, 0, 0, 0)          # 纯灰度
            put8(h - 2, 4, 248, 248, 0)      # 黄边界强
            put8(h - 2, 5, 248, 0, 0)        # 红
            put8(h - 2, 6, 0, 248, 0)        # 绿
        # 边缘结构: 竖条明暗交替 (Sobel 强响应)
        for yy in range(h // 2, h):
            for xx in range(0, w):
                if (xx // 4) % 2 == 0:
                    px[yy * w + xx] = 0xFFFF
                else:
                    px[yy * w + xx] = 0x0000
    return px

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=360)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--case", choices=["directed", "random"], default="directed")
    ap.add_argument("--outdir", default="golden")
    ap.add_argument("--thr_sat", type=int, default=96)
    ap.add_argument("--thr_hue", type=int, default=64)
    ap.add_argument("--thr_val", type=int, default=160)
    ap.add_argument("--thr_low", type=int, default=160)
    ap.add_argument("--thr_edge", type=int, default=128)
    args = ap.parse_args()

    w, h = args.width, args.height
    rng = random.Random(args.seed)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    img = gen_image(w, h, rng, args.case)

    # 内部像素索引 (Sobel 有效输出顺序: row 1..h-2, col 1..w-2)
    interior_idx = [r * w + c for r in range(1, h - 1) for c in range(1, w - 1)]

    gray = [to_gray(p) for p in img]
    color = [colorize(p, y, args.thr_sat, args.thr_hue, args.thr_val, args.thr_low)
             for p, y in zip(img, gray)]
    colorize_px_map = [c[0] for c in color]
    centers, edges = sobel_frame(gray, w, h, args.thr_edge)

    # 展开为全帧流的辅助已移除 (期望文件均为裸序列)

    color_rgb = [c[0] for c in color]
    color_id = [c[1] for c in color]

    # 期望文件 = 与 DUT 输出流一一对应的裸序列:
    #   gray/color: 全像素 1:1 序列; edge/top: Sobel 有效输出(内部像素)序列
    def dump(name, data, width_bits):
        with open(out / name, "w") as f:
            for v in data:
                f.write(f"{v & ((1 << width_bits) - 1):0{max(1, width_bits // 4)}x}\n")

    dump("img.mem", img, 16)
    dump("exp_gray.mem", gray, 8)
    dump("exp_color.mem", color_rgb, 16)
    dump("exp_id.mem", color_id, 2)
    dump("exp_edge.mem", edges, 1)
    dump("exp_center.mem", centers, 8)
    for m in range(4):
        if m == 0:
            top = [0xFFFF if e else c for e, c in zip(edges, [colorize_px_map[i] for i in interior_idx])]
        elif m == 1:
            top = [colorize_px_map[i] for i in interior_idx]
        elif m == 2:
            top = [gray_to_565(y) for y in centers]
        else:
            top = [0xFFFF if e else 0x0000 for e in edges]
        dump(f"exp_top_mode{m}.mem", top, 16)
    dump("exp_bypass.mem", img, 16)

    # 覆盖统计 (标准色三命中必须非零, 否则激励有问题)
    stats = {0: 0, 1: 0, 2: 0, 3: 0}
    for _, cid in color:
        stats[cid] += 1
    print(f"图像 {w}x{h} case={args.case} seed={args.seed}")
    print(f"色化命中: gray={stats[0]} red={stats[1]} yellow={stats[2]} green={stats[3]}")
    print(f"边缘像素: {sum(edges)}/{len(edges)}")
    assert stats[1] > 0 and stats[2] > 0 and stats[3] > 0, "directed 激励缺少标准色命中!"
    print(f"golden 输出 -> {out.resolve()}")

if __name__ == "__main__":
    main()
