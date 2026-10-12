#!/usr/bin/env python3
"""npu_golden.py : NPU 算子位精确黄金模型 + 激励/期望生成 (需求(1))

与 RTL 逐位对齐 (source/npu/*):
  cat_add.v                        : x=max(d-z,0); A=(x1*s1 + x2*s2) mod 2^25;
                                     q=A*s3; out = ([56:30]>=255)?255:([36:30]+[29])
  conv11_conv.v / conv_conv.v      : 原始累加 acc=SUM s8(w)*u8(d) (24bit 符号)
  conv_add.v                       : acc26 -> 25bit 打包(丢 bit24) -> *scale3(16b) + bias + z3<<16 (42bit)
                                     -> 负=0; [40:16]>=255=255; round-half-up; relu=max(q,z3)
  conv11_add.v                     : 同上但 0.5 银行家舍入
  sppf_maxpool.v                   : 5x5 stride-5 无符号 max
  upsample_top.v                   : nearest 2x: out[r][c]=in[r>>1][c>>1]
激励含定向: 饱和/负clamp/relu边界/舍入边界 (0.5 上下两侧)/极值权重。
"""
import random
from pathlib import Path

G = Path(__file__).parent / "golden"

def s8(v):
    v &= 0xFF
    return v - 256 if v & 0x80 else v
def wrap(v, bits):
    m = (1 << bits) - 1
    v &= m
    return v - (1 << bits) if v & (1 << (bits - 1)) else v
def pack128(bts):
    v = 0
    for i, b in enumerate(bts):
        v |= (b & 0xFF) << (8 * i)
    return v

# ---------------- 量化模型 ----------------
def cat_quantize(A, s3):
    q = (A & 0x1FFFFFF) * (s3 & 0xFFFFFFFF)
    if (q >> 30) >= 255:
        return 255
    return ((q >> 30) & 0xFF) + ((q >> 29) & 1)

def cat_sub(d, z):
    return 0 if d < z else (d - z) & 0xFF

def conv_wdata(acc):
    a26 = wrap(acc, 26)
    return wrap((((a26 >> 25) & 1) << 24) | (a26 & 0xFFFFFF), 25)

def _conv_common(acc, scale3, bias, zero3):
    return wrap(conv_wdata(acc) * scale3 + bias + (zero3 << 16), 42)

def conv33_quantize(acc, scale3, bias, zero3, en_relu):
    v = _conv_common(acc, scale3, bias, zero3)
    if v < 0:
        q = 0
    elif ((v >> 16) & 0x1FFFFFF) >= 255:
        q = 255
    else:
        q = ((v >> 16) & 0xFF) + ((v >> 15) & 1)
    return zero3 if (en_relu and q < zero3) else q

def conv11_quantize(acc, scale3, bias, zero3, en_relu):
    v = _conv_common(acc, scale3, bias, zero3)
    if v < 0:
        q = 0
    elif ((v >> 16) & 0x1FFFFFF) >= 255:
        q = 255
    else:
        integer, frac = (v >> 16) & 0xFF, v & 0xFFFF
        if frac > 0x8000:
            q = integer + 1
        elif frac == 0x8000:
            q = integer + (integer & 1)
        else:
            q = integer
    return zero3 if (en_relu and q < zero3) else q

def dump(name, data, width_hex):
    with open(G / name, "w") as f:
        for v in data:
            f.write("x\n" if v is None else f"{v & ((1 << (4 * width_hex)) - 1):0{width_hex}x}\n")

# ---------------- 1) cat_add (多区域: 真实scale/0.5舍入边界/饱和/cat分时) ----------------
# 区域结构同时硬编码在 tb_cat_add.v (REGION_N / beat 计数一致)
REGIONS = [
    # (n_add, n_dir, n_cat0, n_cat1, S1,     S2,     S3,        Z1, Z2)
    (30, 5, 15, 15, 0x8000, 0x8000, 0x0000_8000, 5, 9),   # 真实尺度: out~x1/2+x2/2
    (12, 6, 0, 0,  0x0001, 0x0001, 0x2000_0000, 0, 0),   # S3=2^29: A 奇->恰0.5进位/偶->截断
    (10, 0, 0, 0,  0xFFFF, 0xFFFF, 0xFFFF_FFFF, 2, 3),   # 大尺度: 饱和 255
]

def gen_cat_add():
    rng = random.Random(101)
    d0, d1, mode, exp, regs = [], [], [], [], []
    for rid, (na, nd, nc0, nc1, S1, S2, S3, Z1, Z2) in enumerate(REGIONS):
        regs += [S1, S2, S3, (Z2 << 8) | Z1]
        def q(a, b):
            return cat_quantize(cat_sub(a, Z1) * S1 + cat_sub(b, Z2) * S2, S3)
        if rid == 0:   # 定向: d<z clamp / 全零 / 饱和 / 接近 relu 边界
            for a, b in [(200, 3), (0, 0), (255, 255), (4, 8), (128, 200)]:
                d0.append(pack128([a] * 16)); d1.append(pack128([b] * 16))
                mode.append(rid * 4 + 0); exp.append(q(a, b))
        if rid == 1:   # 定向: A=1..6 覆盖 0.5 进位(A奇)与截断(A偶)
            for a, b in [(1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (5, 0)]:
                d0.append(pack128([a] * 16)); d1.append(pack128([b] * 16))
                mode.append(rid * 4 + 0); exp.append(q(a, b))
        for _ in range(na):
            a, b = rng.randint(0, 255), rng.randint(0, 255)
            d0.append(pack128([a] * 16)); d1.append(pack128([b] * 16))
            mode.append(rid * 4 + 0); exp.append(q(a, b))
        for _ in range(nc0):
            a = rng.randint(0, 255)
            d0.append(pack128([a] * 16)); d1.append(pack128([0] * 16))
            mode.append(rid * 4 + 1); exp.append(cat_quantize(cat_sub(a, Z1) * S1, S3))
        for _ in range(nc1):
            b = rng.randint(0, 255)
            d0.append(pack128([0] * 16)); d1.append(pack128([b] * 16))
            mode.append(rid * 4 + 2); exp.append(cat_quantize(cat_sub(b, Z2) * S2, S3))
    dump("cat_d0.mem", d0, 32); dump("cat_d1.mem", d1, 32)
    dump("cat_mode.mem", mode, 2); dump("cat_exp.mem", exp, 2)
    dump("cat_regs.mem", regs, 8)
    with open(G / "cat_regs.txt", "w") as f:
        for i, (na, nd, nc0, nc1, S1, S2, S3, Z1, Z2) in enumerate(REGIONS):
            f.write("region%d: s1=%08x s2=%08x s3=%08x z1=%d z2=%d beats=%d" % (i, S1, S2, S3, Z1, Z2, na+nd+nc0+nc1) + chr(10))
    return len(exp)

# ---------------- 2) conv11_conv (单元) ----------------
def gen_conv11_conv():
    rng = random.Random(202)
    N = 40
    w = []
    for k in range(8):
        if k == 0:   ch = [1] * 16
        elif k == 1: ch = [-1] * 16
        elif k == 2: ch = [127] * 16
        elif k == 3: ch = [-128] * 16
        else:         ch = [rng.randint(-128, 127) for _ in range(16)]
        w.append(pack128([c & 0xFF for c in ch]))
    d, exp = [], []
    for j in range(N):
        px = ([0] * 16) if j % 9 == 0 else ([255] * 16 if j % 7 == 0 else [rng.randint(0, 255) for _ in range(16)])
        d.append(pack128(px))
    for j in range(N):
        beat = []
        for k in range(8):
            a = sum(s8((w[k] >> (8 * i)) & 0xFF) * ((d[j] >> (8 * i)) & 0xFF) for i in range(16))
            beat.append(wrap(a, 24) & 0xFFFFFF)
        exp.append(beat)
    dump("c11_w.mem", w, 32); dump("c11_d.mem", d, 32)
    dump("c11_exp.mem", [v for beat in exp for v in beat], 6)
    return {"conv11_conv": N}

# ---------------- 3) conv_conv (单元, 2 组权重乒乓) ----------------
def gen_conv_conv():
    rng = random.Random(303)
    W = 8
    Z1 = 5
    groups = []
    for g in range(2):
        taps = []
        for t in range(9):
            ks = []
            for k in range(8):
                if g == 0 and k == 3:   ch = [-128] * 16
                elif g == 0 and k == 4: ch = [127] * 16
                elif g == 1 and k == 0: ch = [1] * 16
                else:                    ch = [rng.randint(-16, 15) for _ in range(16)]
                ks.append(pack128([c & 0xFF for c in ch]))
            taps.append(ks)
        groups.append(taps)
    rows = []
    for r in range(3):
        row = []
        for c in range(W + 2):
            if c == 0 or c == W + 1:
                px = [Z1] * 16                       # 模拟 in_ctrl padding
            elif r == 1 and c in (3, 4):
                px = [255] * 16
            else:
                px = [rng.randint(0, 255) for _ in range(16)]
            row.append(pack128(px))
        rows.append(row)
    # 解码契约 (tb_c33_decode 实验): out#k 窗口 = 流列 [k, k+1, k+2],
    # tap t=(行 t/3, 列 t%3), weight 端口 t = tap t; 每行 W 个窗口 (流含首尾 pad)
    exp = []
    for g in range(2):
        for k in range(W):
            for kk in range(8):
                a = 0
                for t in range(9):
                    rr, cc = t // 3, t % 3
                    for i in range(16):
                        a += s8((groups[g][t][kk] >> (8 * i)) & 0xFF) * ((rows[rr][k + cc] >> (8 * i)) & 0xFF)
                exp.append(wrap(a, 24) & 0xFFFFFF)
    dump("c33_d0.mem", rows[0], 32); dump("c33_d1.mem", rows[1], 32); dump("c33_d2.mem", rows[2], 32)
    dump("c33_w.mem", [groups[g][t][k] for g in range(2) for t in range(9) for k in range(8)], 32)
    dump("c33_exp.mem", exp, 6)
    return {"conv_conv": 2 * W}

# ---------------- 4) sppf (单元: sppf_maxpool 直驱, 5x5 stride-1 p=2) ----------------
def gen_sppf_unit():
    rng = random.Random(404)
    W = 10
    rows = []
    for r in range(5):
        row = []
        for c in range(W):
            if (r, c) == (2, 3):   px = [255] * 16
            elif (r, c) == (4, 9): px = [1] * 16
            else:                   px = [rng.randint(0, 255) for _ in range(16)]
            row.append(pack128(px))
        rows.append(row)
    exp = []
    for w in range(W):                       # 每拍一个滑窗输出 (stride-1, pad=0)
        for i in range(16):
            m = 0
            for r in range(5):
                for c in range(max(w - 2, 0), min(w + 2, W - 1) + 1):
                    m = max(m, (rows[r][c] >> (8 * i)) & 0xFF)
            exp.append(m)
    for r in range(5):
        dump(f"sppu_row{r}.mem", rows[r], 32)
    dump("sppu_exp.mem", exp, 2)
    return W

# ---------------- 5) upsample_top (模块级) ----------------
def gen_upsample():
    rng = random.Random(505)
    H, Wd = 6, 8
    frame = [[pack128([rng.randint(0, 255) for _ in range(16)]) for _ in range(Wd)] for _ in range(H)]
    frame[0][0] = pack128([0xAB] * 16); frame[H - 1][Wd - 1] = pack128([0x5A] * 16)
    exp = []
    for r in range(2 * H):
        for c in range(2 * Wd):
            exp.append(frame[r >> 1][c >> 1])
    dump("ups_in.mem", [w for row in frame for w in row], 32)
    dump("ups_exp.mem", exp, 32)
    (G / "ups_info.txt").write_text(
        f"H={H} W={Wd} rowbytes={Wd*16}" + chr(10))
    return {"upsample_top": len(exp)}

# ---------------- 6) conv_top (模块级: 完整量化, 移位寄存器逐拍建模) ----------------
def gen_conv_top():
    rng = random.Random(606)
    H, Wd, COUT = 6, 8, 8
    SCALE3, Z1, Z3 = 0x4000, 3, 5
    BIAS = [rng.randint(-1 << 20, 1 << 20) for _ in range(COUT)]
    BIAS[0] = -1 << 24
    frame = []
    for r in range(H):
        row = []
        for c in range(Wd):
            if (r, c) == (1, 1):   px = [255] * 16
            elif (r, c) == (3, 5): px = [0] * 16
            else:                   px = [rng.randint(0, 255) for _ in range(16)]
            row.append(pack128(px))
        frame.append(row)
    wt = [[pack128([(rng.randint(-16, 15)) & 0xFF for _ in range(16)]) for _ in range(COUT)] for _ in range(9)]

    PAD = pack128([Z1] * 16)
    def row_stream(r):
        """in_ctrl 输出流: [pad] + W 字 + [pad]"""
        return [PAD] + frame[r] + [PAD]

    # 逐拍滑窗建模 (每流历史跨行连续), 帧头 2 拍窗口含上电未知值 -> None 不比对
    seq_top, seq_mid, seq_bot = [], [], []
    for r in range(H):
        top = [PAD] * (Wd + 2) if r == 0 else row_stream(r - 1)
        mid = row_stream(r)
        bot = [PAD] * (Wd + 2) if r == H - 1 else row_stream(r + 1)
        seq_top += top; seq_mid += mid; seq_bot += bot
    # 解码契约: out#k 窗口 = 流列 [k, k+1, k+2]; 每行 W 个输出 (含 padding 数据列)
    exp = []
    for r in range(H):
        top = [PAD] * (Wd + 2) if r == 0 else row_stream(r - 1)     # R_FIRST: top 恒 zero_1
        mid = row_stream(r)
        bot = [PAD] * (Wd + 2) if r == H - 1 else row_stream(r + 1) # R_LAST: bot 恒 zero_1
        for k in range(Wd):
            ks = []
            for cout in range(COUT):
                acc = 0
                for t in range(9):
                    rr, cc = t // 3, t % 3
                    src_stream = (top, mid, bot)[rr]
                    for i in range(16):
                        acc += s8((wt[t][cout] >> (8 * i)) & 0xFF) * ((src_stream[k + cc] >> (8 * i)) & 0xFF)
                ks.append(conv33_quantize(acc, SCALE3, BIAS[cout], Z3, 1))
            v = 0
            for cout in range(COUT):
                v |= ks[cout] << (8 * cout)
            exp.append(v)
    in_words = [w for row in frame for w in row]
    bias_words = [pack128([BIAS[k] & 0xFF, (BIAS[k] >> 8) & 0xFF, (BIAS[k] >> 16) & 0xFF,
                           (BIAS[k] >> 24) & 0xFF] + [0] * 12) for k in range(COUT)]
    grp_words = [wt[t][k] for t in range(9) for k in range(COUT)]
    dump("ct_in.mem", in_words, 32)
    dump("ct_bias.mem", bias_words, 32)
    dump("ct_grp.mem", grp_words, 32)
    dump("ct_exp.mem", exp, 16)
    (G / "ct_info.txt").write_text(
        f"H={H} W={Wd} CIN=16 COUT={COUT} scale3={SCALE3:x} z1={Z1} z3={Z3} "
        f"bias_words={COUT} group_words={9*COUT} rowbytes={Wd*16}\n")
    return {"conv_top": H * Wd}


# ---------------- 7) conv11_para_top (模块级: 1x1 完整量化, 银行家舍入) ----------------
def gen_conv11_para():
    rng = random.Random(707)
    H, Wd, COUT = 6, 8, 8
    SCALE3, Z1, Z3 = 0x6000, 1, 2
    BIAS = [rng.randint(-1 << 18, 1 << 18) for _ in range(COUT)]
    BIAS[1] = -(1 << 22)
    frame = []
    for r in range(H):
        row = []
        for c in range(Wd):
            if (r, c) == (0, 0):   px = [255] * 16
            elif (r, c) == (5, 7): px = [0] * 16
            else:                   px = [rng.randint(0, 255) for _ in range(16)]
            row.append(pack128(px))
        frame.append(row)
    # 1x1 权重: 每 kernel 一个 16B 字 (tap0)
    wt = [pack128([(rng.randint(-32, 31)) & 0xFF for _ in range(16)]) for _ in range(COUT)]
    exp = []
    for r in range(H):
        for c in range(Wd):
            ks = []
            for cout in range(COUT):
                acc = 0
                for i in range(16):
                    acc += s8((wt[cout] >> (8 * i)) & 0xFF) * ((frame[r][c] >> (8 * i)) & 0xFF)
                ks.append(conv11_quantize(acc, SCALE3, BIAS[cout], Z3, 1))
            v = 0
            for cout in range(COUT):
                v |= ks[cout] << (8 * cout)
            exp.append(v)
    bias_words = [pack128([BIAS[k] & 0xFF, (BIAS[k] >> 8) & 0xFF, (BIAS[k] >> 16) & 0xFF,
                           (BIAS[k] >> 24) & 0xFF] + [0] * 12) for k in range(COUT)]
    dump("p11_in.mem", [w for row in frame for w in row], 32)
    dump("p11_bias.mem", bias_words, 32)
    dump("p11_w.mem", wt, 32)
    dump("p11_exp.mem", exp, 16)
    (G / "p11_info.txt").write_text(
        f"H={H} W={Wd} COUT={COUT} scale3={SCALE3:x} z1={Z1} z3={Z3} "
        f"bias_words={COUT} group_words={COUT} rowbytes={Wd*16}" + chr(10))
    return H * Wd

def main():
    import shutil
    if G.exists():
        shutil.rmtree(G)
    G.mkdir(parents=True)
    man = {}
    man["cat_add"] = gen_cat_add()
    man["conv11_conv"] = gen_conv11_conv()
    man["conv_conv"] = gen_conv_conv()
    man["sppf_maxpool"] = gen_sppf_unit()
    man["upsample_top"] = gen_upsample()
    man["conv_top"] = gen_conv_top()
    man["conv11_para_top"] = gen_conv11_para()
    lines = [f"{k}: expect {v}" for k, v in man.items()]
    (G / "MANIFEST.txt").write_text("\n".join(lines) + "\n")
    print("golden ->", G)
    for l in lines:
        print(" ", l)

if __name__ == "__main__":
    main()
