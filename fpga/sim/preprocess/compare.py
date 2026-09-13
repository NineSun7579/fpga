#!/usr/bin/env python3
"""compare.py : HW 仿真输出 vs golden 期望逐位比对 + 随机抽样转换验证 (需求(3))

数据来源:
  golden/exp_*.mem      golden_gen.py 生成的期望流
  golden/hw_out_*.mem   6 个 TB 用 $fwrite 落盘的实际输出流
  golden/img.mem        激励帧 (RGB565)

比对: 每条流逐元素比对, 任何不一致即为 FAIL。
抽样: 随机抽 100 个像素做"独立实现"转换验证 (不读 golden 文件, 现场重算):
  灰度  : RGB565 -> expand8 -> Y=(77R+150G+29B)>>8   vs hw_out_gray
  往返  : gray -> RGB565 (高位截断)                   vs hw_out_top_mode2
  色化  : 全公式重算 (阈值默认)                        vs hw_out_top_mode1
  反量化: 8bit 灰度 vs 浮点亮度 (0.299/0.587/0.114)   -> 量化误差表
输出: verify_report.md (逐流比对表 + 抽样转换验证表 + 结论), 退出码=不一致数
"""
import argparse
import random
from pathlib import Path

def read_mem(path):
    p = Path(path)
    if not p.exists():
        return None
    out = []
    for line in p.read_text().split():
        line = line.strip()
        if line and not line.startswith('//'):
            out.append(int(line, 16))
    return out

def rgb565_split(px):
    return (px >> 11) & 0x1F, (px >> 5) & 0x3F, px & 0x1F

def expand8(px):
    r5, g6, b5 = rgb565_split(px)
    return (r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)

def to_gray(px):
    r8, g8, b8 = expand8(px)
    return (77 * r8 + 150 * g8 + 29 * b8) >> 8

def gray_to_565(y):
    return ((y >> 3) << 11) | ((y >> 2) << 5) | (y >> 3)

def colorize(px, thr_sat=96, thr_hue=64, thr_val=160, thr_low=160):
    r8, g8, b8 = expand8(px)
    y = to_gray(px)
    chroma = max(r8, g8, b8) - min(r8, g8, b8)
    if chroma < thr_sat:
        return gray_to_565(y)
    if (r8 - g8 >= thr_hue) and (r8 - b8 >= thr_hue):
        return 0xF800
    if (g8 - r8 >= thr_hue) and (g8 - b8 >= thr_hue):
        return 0x07E0
    if (r8 >= 32) and (g8 >= 32) and (abs(r8 - g8) < thr_hue) and (b8 <= thr_low) \
            and (r8 >= thr_val) and (g8 >= thr_val):
        return 0xFFE0
    return gray_to_565(y)

def compare_stream(name, exp, hw, width, report):
    if exp is None or hw is None:
        report.append(f"| {name} | - | - | - | MISSING({'exp' if exp is None else ''}{'hw' if hw is None else ''}) | ✗ |")
        return 1
    n = min(len(exp), len(hw))
    mism = [i for i in range(n) if exp[i] != hw[i]]
    len_ok = (len(exp) == len(hw))
    mask = (1 << width) - 1
    detail = ""
    if mism:
        i = mism[0]
        detail = f" first@{i}: got={hw[i]&mask:0{max(1,width//4)}x} exp={exp[i]&mask:0{max(1,width//4)}x}"
    elif not len_ok:
        detail = f" len hw={len(hw)} exp={len(exp)}"
    status = "✓" if (not mism and len_ok) else "✗"
    report.append(f"| {name} | {len(exp)} | {len(hw)} | {len(mism)} |{detail} | {status} |")
    return 0 if (not mism and len_ok) else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--height", type=int, default=36)
    ap.add_argument("--golden", default="golden")
    ap.add_argument("--report", default="verify_report.md")
    ap.add_argument("--samples", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    g = Path(args.golden)
    W, H = args.width, args.height
    N = W * H
    NOUT = (W - 2) * (H - 2)

    img = read_mem(g / "img.mem")
    streams = [
        ("gray   (rgb2gray 单元)",        "exp_gray.mem",       "hw_out_gray.mem",        8, N),
        ("color  (色化单元 RGB565)",      "exp_color.mem",      "hw_out_color.mem",      16, N),
        ("id     (色化单元 class id)",    "exp_id.mem",         "hw_out_id.mem",          2, N),
        ("edge   (sobel 边缘位)",         "exp_edge.mem",       "hw_out_edge.mem",        1, NOUT),
        ("center (sobel 中心灰度)",       "exp_center.mem",     "hw_out_center.mem",      8, NOUT),
        ("top mode0 (色化+白边)",         "exp_top_mode0.mem",  "hw_out_top_mode0.mem",  16, NOUT),
        ("top mode1 (仅色化)",            "exp_top_mode1.mem",  "hw_out_top_mode1.mem",  16, NOUT),
        ("top mode2 (仅灰度)",            "exp_top_mode2.mem",  "hw_out_top_mode2.mem",  16, NOUT),
        ("top mode3 (仅边缘)",            "exp_top_mode3.mem",  "hw_out_top_mode3.mem",  16, NOUT),
        ("bypass (RAW 直通)",             "exp_bypass.mem",     "hw_out_bypass.mem",     16, N),
        ("regs   (AXI-Lite 读回序列)",    None,                 "hw_out_regs.mem",       32, None),
        ("btn    (toggle 事件序列)",      None,                 "hw_out_btn.mem",        32, None),
    ]

    report = []
    report.append(f"# 预处理 IP 软硬件一致性验证报告 (compare.py)\n")
    report.append(f"- 分辨率: {W}x{H}, 激励: golden/img.mem (directed, seed=7)\n")
    report.append(f"- 逐位比对: golden/exp_*.mem vs TB 落盘 golden/hw_out_*.mem\n")

    fails = 0
    report.append("\n## 1. 逐流位精确比对\n")
    report.append("| 流 | exp 元素数 | hw 元素数 | 不一致数 | 首个不一致 | 结果 |")
    report.append("|---|---|---|---|---|---|")
    for name, expf, hwf, width, n_exp in streams:
        exp = read_mem(g / expf) if expf else None
        hw = read_mem(g / hwf)
        if name.startswith(("regs", "btn")):
            # 无 golden 文件: 记录型流, 校验非空 + 事件数即可 (位精确判定在 TB 内完成)
            if hw is None or len(hw) == 0:
                report.append(f"| {name} | - | - | - | 落盘缺失/为空 | ✗ |")
                fails += 1
            elif name.startswith("btn") and len(hw) != 2:
                report.append(f"| {name} | 2 | {len(hw)} | {abs(len(hw)-2)} | 期望恰好 2 次 toggle | ✗ |")
                fails += 1
            else:
                report.append(f"| {name} | - | {len(hw)} | 0 | 记录 {len(hw)} 项 (TB 内已逐项断言) | ✓ |")
            continue
        fails += compare_stream(name, exp, hw, width, report)

    # ---------------- 抽样转换验证 ----------------
    report.append(f"\n## 2. 随机抽样转换验证 (独立重算, 抽 {args.samples} 样本, seed={args.seed})\n")
    rng = random.Random(args.seed)
    idxs = rng.sample(range(N), min(args.samples, N))
    hw_gray = read_mem(g / "hw_out_gray.mem")
    hw_m1 = read_mem(g / "hw_out_top_mode1.mem")
    hw_m2 = read_mem(g / "hw_out_top_mode2.mem")

    tbl = []
    g_errs, rt_bad, c_bad, hw_bad = [], 0, 0, 0
    for i in idxs:
        px = img[i]
        r8, g8, b8 = expand8(px)
        y = to_gray(px)
        float_luma = 0.299 * r8 + 0.587 * g8 + 0.114 * b8
        q_err = abs(y - float_luma)
        g_errs.append(q_err)
        y565 = gray_to_565(y)
        # mode2 输出 = 内部像素流: idx -> (r,c) 需落在内部区
        r, c = divmod(i, W)
        rt_ok = c_ok = hwg_ok = True
        if 1 <= r < H - 1 and 1 <= c < W - 1:
            j = (r - 1) * (W - 2) + (c - 1)
            if hw_m2 and j < len(hw_m2):
                rt_ok = (hw_m2[j] == y565)
                if not rt_ok: rt_bad += 1
            if hw_m1 and j < len(hw_m1):
                c_ok = (hw_m1[j] == colorize(px))
                if not c_ok: c_bad += 1
        if hw_gray and i < len(hw_gray):
            hwg_ok = (hw_gray[i] == y)
            if not hwg_ok: hw_bad += 1
        tbl.append((i, px, r8, g8, b8, float_luma, y, q_err, y565, rt_ok, c_ok, hwg_ok))

    qerr_max = max(g_errs)
    qerr_avg = sum(g_errs) / len(g_errs)
    report.append("### 2.1 汇总\n")
    report.append("| 项目 | 值 |")
    report.append("|---|---|")
    report.append(f"| 灰度定点误差 max \\|Y_int − Y_float\\| | {qerr_max:.2f} (LSB, 8bit) |")
    report.append(f"| 灰度定点误差 avg | {qerr_avg:.3f} LSB |")
    report.append(f"| 抽样中 hw 灰度 ≠ 独立重算 | {hw_bad}/{len(idxs)} |")
    report.append(f"| 抽样中 mode2 输出 ≠ 灰度→RGB565 往返 | {rt_bad}/{len(idxs)} |")
    report.append(f"| 抽样中 mode1 输出 ≠ 色化独立重算 | {c_bad}/{len(idxs)} |")
    fails += hw_bad + rt_bad + c_bad

    report.append("\n### 2.2 反量化往返对照表 (前 20 行)\n")
    report.append("| idx | RGB565 | R8 G8 B8 | Y_float | Y_int | \\|err\\| | Y→565 | m2 hw=往返 | m1 hw=重算 | gray hw=重算 |")
    report.append("|---|---|---|---|---|---|---|---|---|---|")
    for (i, px, r8, g8, b8, fl, y, qe, y565, rt_ok, c_ok, hwg_ok) in tbl[:20]:
        report.append(f"| {i} | {px:04X} | {r8} {g8} {b8} | {fl:.2f} | {y} | {qe:.2f} | {y565:04X} |"
                      f" {'✓' if rt_ok else '✗'} | {'✓' if c_ok else '✗'} | {'✓' if hwg_ok else '✗'} |")

    report.append(f"\n## 3. 结论\n")
    if fails == 0:
        report.append("**ALL PASS**: 全部流逐位一致, 抽样转换验证 0 偏差 ✓\n")
    else:
        report.append(f"**FAIL**: 共 {fails} 处不一致, 详见上表 ✗\n")

    Path(args.report).write_text("\n".join(report), encoding="utf-8")
    print(f"report -> {args.report}  fails={fails}")
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
