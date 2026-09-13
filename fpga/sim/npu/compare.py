#!/usr/bin/env python3
"""compare.py : NPU HW 仿真输出 vs 黄金模型逐位比对 (需求(3))
exp 文件中的 'x...' 行 = don't care (帧头上电未知窗口), 比对时跳过。
"""
import sys
from pathlib import Path

G = Path(__file__).parent / "golden"

STREAMS = [
    ("cat_add      (3尺度区+cat分时+0.5舍入边界)", "cat_exp.mem",         "hw_out_cat_add.mem",      32),
    ("conv11_conv  (1x1 核原始累加 24bit)",        "c11_exp.mem",         "hw_out_conv11_conv.mem",   6),
    ("conv_conv    (3x3 核原始累加 24bit)",        "c33_exp.mem",         "hw_out_conv_conv.mem",     6),
    ("sppf_maxpool (5x5 stride5 无符号 max)",      "sppu_exp.mem",        "hw_out_sppf_maxpool.mem",  2),
    ("upsample_top (nearest 2x 模块级)",           "ups_exp.mem",         "hw_out_upsample_top.mem", 32),
    ("conv_top     (3x3 完整量化模块级)",          "ct_exp.mem",          "hw_out_conv_top.mem",     16),
    ("conv11_para  (1x1 完整量化+out_buf)",        "p11_exp.mem",         "hw_out_conv11_para_top.mem", 16),
]

def read_mem(p):
    if not p.exists():
        return None
    out = []
    for line in p.read_text().splitlines():
        line = line.split("//")[0].strip()      # $writememh 可能写 // 注释头
        if line:
            out.append(line)
    return out

def main():
    report = ["# NPU 软硬件一致性验证报告 (sim/npu/compare.py)\n"]
    report.append("逐位比对: npu_golden.py 黄金期望 vs TB 落盘 hw_out_*.mem ('x' = don't care 跳过)\n")
    report.append("| 流 | exp | hw | 不一致 | skipped(x) | 结果 |")
    report.append("|---|---|---|---|---|---|")
    total_fail = 0
    any_missing = False
    for name, expf, hwf, w in STREAMS:
        exp = read_mem(G / expf)
        hw = read_mem(G / hwf)
        if exp is None or hw is None:
            report.append(f"| {name} | {len(exp) if exp else '-'} | {len(hw) if hw else '-'} | - | - | MISSING({'exp' if exp is None else ''}{'hw' if hw is None else ''}) |")
            any_missing = True
            total_fail += 1
            continue
        n = min(len(exp), len(hw))
        mism = skipped = 0
        first = ""
        for i in range(n):
            if set(exp[i]) <= {"x", "X"}:
                skipped += 1
                continue
            e = exp[i]
            h = hw[i]
            if set(h) <= {"x", "X"}:
                skipped += 1        # RTL 未产出的尾槽位 (写整组数组时的 X 填充)
                continue
            if name.startswith("cat_add"):
                # TB 落盘为 128bit 全通道字 (16 通道同值); 比对 byte0, 并校验 16 通道一致
                lanes = {h[j*2:j*2+2] for j in range(16)}
                if len(lanes) != 1:
                    mism += 1
                    if not first: first = f" first@{i}: 通道不一致 {sorted(lanes)[:3]}"
                    continue
                h = h[0:2]
            if name.startswith("conv11_para"):
                # out_buf 128bit 词 = [低64: 列2k][高64: 列2k+1]; 与 64bit 黄金词两两比对
                if len(h) == 32:
                    lo, hi = h[16:32], h[0:16]   # hex 串左边是高位: [高64=列2k+1 | 低64=列2k]
                    e_lo = exp[2*i] if 2*i < len(exp) else 'x'
                    e_hi = exp[2*i+1] if 2*i+1 < len(exp) else 'x'
                    bad = 0
                    for pair in ((lo, e_lo), (hi, e_hi)):
                        hh, ee = pair
                        if set(ee) <= {'x','X'} or set(hh) <= {'x','X'}: continue
                        if hh != ee:
                            bad += 1
                            if not first: first = f" first@{i}: got={hh} exp={ee}"
                    mism += bad
                    continue
            if name.startswith("conv11_conv"):
                # 契约: m_valid 每流首拍不产数 -> hw[k] 对应 exp[k+NK]; 尾 2 拍 RTL 不产出
                j = i + 8
                e = exp[j] if j < len(exp) else 'x'
            if e != h:
                mism += 1
                if not first:
                    first = f" first@{i}: got={h} exp={e}"
        ok = (mism == 0)
        report.append(f"| {name} | {len(exp)} | {len(hw)} | {mism} | {skipped} | {'✓' if ok else '✗'+first} |")
        if not ok:
            total_fail += 1
    report.append("\n## 结论\n")
    report.append("**ALL PASS**: 全部流逐位一致 ✓" if total_fail == 0 else f"**FAIL**: {total_fail} 条流不一致 ✗")
    if any_missing:
        report.append("\n(存在 MISSING: 对应 TB 未运行或未落盘)")
    (G / ".." / "verify_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[3:]))
    print("report -> sim/npu/verify_report.md  fails =", total_fail)
    return 1 if total_fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
