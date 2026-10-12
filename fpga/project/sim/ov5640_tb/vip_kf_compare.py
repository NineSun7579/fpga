#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vip_kf_compare.py -- Python 位精确黄金模型 vs vip_kf RTL 仿真输出比对.

黄金模型 = vip_kf.v 的逐通道定点时域递归 (稳态卡尔曼/IIR, 4 档增益):
    d = |z - x|
    d < thr0 -> (3x+z)>>2 ;  d < thr1 -> (x+z)>>1
    d < thr2 -> (x+3z)>>2 ;  else -> z
首帧 passthrough 并写回状态. 所有运算为无符号整数/逻辑右移, 与 RTL 逐位一致.

用法 (在工程根目录):
    python sim/ov5640_tb/vip_kf_compare.py
退出码: 0 = 位精确 PASS, 1 = FAIL.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IN_MEM = os.path.join(HERE, "kf_in.mem")
HW_MEM = os.path.join(HERE, "kf_hw_out.mem")

THR0, THR1, THR2 = 3, 8, 20


def parse_mem(path):
    """返回 frames: list[list[int]]."""
    frames = []
    cur = None
    with open(path, "r") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                cur = []
                frames.append(cur)
                continue
            if cur is None:
                cur = []
                frames.append(cur)
            cur.append(int(s, 16) & 0xFFFF)
    return frames


def kf_ch(z, x):
    d = abs(z - x)
    if d < THR0:
        return (3 * x + z) >> 2
    if d < THR1:
        return (x + z) >> 1
    if d < THR2:
        return (x + 3 * z) >> 2
    return z


def kf_px(z, x):
    r = kf_ch((z >> 11) & 0x1F, (x >> 11) & 0x1F)
    g = kf_ch((z >> 5) & 0x3F, (x >> 5) & 0x3F)
    b = kf_ch(z & 0x1F, x & 0x1F)
    return ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)


def golden(frames):
    """首帧 passthrough, 其后逐像素时域递归."""
    if not frames:
        return []
    outp = []
    state = list(frames[0])  # 首帧滤波结果 = 输入
    outp.append(list(state))
    for f in range(1, len(frames)):
        cur = frames[f]
        new = []
        for p in range(len(cur)):
            o = kf_px(cur[p], state[p])
            new.append(o)
        outp.append(new)
        state = new
    return outp


def band_stats(inp):
    """统计各增益档命中次数 (按通道), 验证激励覆盖."""
    bands = [0, 0, 0, 0]
    if len(inp) < 2:
        return bands
    state = list(inp[0])
    for f in range(1, len(inp)):
        cur = inp[f]
        new = []
        for p in range(len(cur)):
            z, x = cur[p], state[p]
            for (zv, xv) in (((z >> 11) & 31, (x >> 11) & 31),
                             ((z >> 5) & 63, (x >> 5) & 63),
                             (z & 31, x & 31)):
                d = abs(zv - xv)
                if d < THR0:
                    bands[0] += 1
                elif d < THR1:
                    bands[1] += 1
                elif d < THR2:
                    bands[2] += 1
                else:
                    bands[3] += 1
            new.append(kf_px(z, x))
        state = new
    return bands


def main():
    for p in (IN_MEM, HW_MEM):
        if not os.path.exists(p):
            print("FAIL: missing %s" % p)
            return 1

    inp = parse_mem(IN_MEM)
    hw = parse_mem(HW_MEM)
    print("frames: input=%d hw=%d" % (len(inp), len(hw)))

    exp = golden(inp)

    n = min(len(exp), len(hw))
    total = 0
    bad = 0
    first_bad = None
    for f in range(n):
        m = min(len(exp[f]), len(hw[f]))
        for p in range(m):
            total += 1
            if exp[f][p] != hw[f][p]:
                bad += 1
                if first_bad is None:
                    first_bad = (f, p, exp[f][p], hw[f][p])
        if len(exp[f]) != len(hw[f]):
            print("FAIL: frame %d length mismatch exp=%d hw=%d"
                  % (f, len(exp[f]), len(hw[f])))
            bad += 1

    bands = band_stats(inp)
    print("gain-band hits (per channel): K=1/4:%d  K=1/2:%d  K=3/4:%d  K=1:%d"
          % tuple(bands))
    print("compared pixels: %d, mismatches: %d" % (total, bad))
    if first_bad:
        print("first mismatch: frame=%d pix=%d exp=0x%04X hw=0x%04X" % first_bad)

    if bad == 0 and n >= 2 and total > 0:
        print("VIPKF_COMPARE_PASS (bit-exact, %d pixels)" % total)
        return 0
    print("VIPKF_COMPARE_FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
