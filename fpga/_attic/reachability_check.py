#!/usr/bin/env python3
"""任务0 字节级可达性分析（GBK 安全版）。

要点：
- 所有 token 匹配在原始字节上做（ASCII 模块名在任何 ANSI 代码页下字节连续），
  GBK 尾字节可能造成假阳性（把注释乱码当引用），不会造成假阴性 → 归档决策保守安全。
- 对字节级判死的文件，再用去注释文本二次确认，双确认才进最终死名单。
- 扫描范围：source/**.v + ipcore/**.v,.vp（ipcore 引用 source 模块也计入）。
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

def strip_comments_bytes(raw: bytes) -> bytes:
    t = re.sub(rb"/\*.*?\*/", b" ", raw, flags=re.S)
    t = re.sub(rb"//[^\n]*", b" ", t)
    return t

def main():
    top_name = sys.argv[1] if len(sys.argv) > 1 else "top"
    files = {}                    # rel -> raw bytes
    for pat in ("source/**/*.v", "ipcore/**/*.v", "ipcore/**/*.vp"):
        for p in sorted(ROOT.glob(pat)):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            files[rel] = p.read_bytes()

    mod_def = defaultdict(set)    # module -> set(rel)
    file_mods = defaultdict(set)  # rel -> set(mod)
    for rel, raw in files.items():
        txt = strip_comments_bytes(raw)
        for m in re.finditer(rb"^\s*module\s+(\w+)", txt, flags=re.M):
            mod = m.group(1).decode()
            mod_def[mod].add(rel)
            file_mods[rel].add(mod)
    all_mods = set(mod_def)

    # 字节级引用（不去注释 → 保守）
    refs_byte = defaultdict(set)
    # 去注释引用（严格）
    refs_clean = defaultdict(set)
    tok = {m: re.compile((r"\b%s\b" % re.escape(m)).encode()) for m in all_mods}
    for rel, raw in files.items():
        clean = strip_comments_bytes(raw)
        for m, rx in tok.items():
            in_byte = bool(rx.search(raw))
            in_clean = bool(rx.search(clean))
            if rel in mod_def[m]:
                # 自文件：出现>1 次才算自引用（其他模块例化它）
                if len(rx.findall(clean)) > 1:
                    refs_clean[m].add(rel)
                if len(rx.findall(raw)) > 1:
                    refs_byte[m].add(rel)
            else:
                if in_byte:
                    refs_byte[m].add(rel)
                if in_clean:
                    refs_clean[m].add(rel)

    def forward(refs):
        seen, stack = set(), [top_name]
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in mod_def:
                continue
            seen.add(cur)
            for rel in mod_def[cur]:
                for nxt in all_mods:
                    if nxt not in seen and rel in refs[nxt]:
                        stack.append(nxt)
        return seen

    reach = forward(refs_byte)          # 保守可达
    reach_strict = forward(refs_clean)  # 严格可达
    dead_mods = sorted(all_mods - reach)
    # 死文件：字节级判死 ∩ 严格级判死（双重确认）
    dead_files = set()
    for rel, mods in file_mods.items():
        if mods and all(m not in reach and m not in reach_strict for m in mods):
            dead_files.add(rel)
    # 混合文件告警
    mixed = [rel for rel, mods in file_mods.items()
             if mods and any(m in reach for m in mods) and any(m not in reach for m in mods)]

    print(f"扫描文件: {len(files)}  模块: {len(all_mods)}")
    print(f"顶层: {top_name}  保守可达模块: {len(reach)}")
    print(f"\n[死模块 {len(dead_mods)}] (从 {top_name} 不可达):")
    for m in dead_mods:
        print(f"  {m:45s} <- {sorted(mod_def[m])}")
    print(f"\n[死文件 {len(dead_files)}] (字节级+去注释双重确认，可整文件归档):")
    for rp in sorted(dead_files):
        print(f"  {rp}")
    if mixed:
        print(f"\n[警告-混合文件 {len(mixed)}] (活死共存，禁止整文件归档):")
        for rp in sorted(mixed):
            print(f"  {rp}: {sorted(file_mods[rp])}")

    # 对照计划清单
    plan = ["axi_dma/app_width_convert", "axi_dma/axi_pipe", "axi_dma/gen_traffic",
            "axi_crossbar/axi_crossbar_7x1", "axi_crossbar/axi_crossbar_7x2",
            "ov5640/axi_lite_to_axi", "npu/conv11_16/conv11_top",
            "npu/conv11_16/conv11_mul", "npu/conv11_16/conv11_mul_ip",
            "npu/conv11_16/conv11_weight_all", "npu/conv/conv_mul",
            "npu/conv/conv_mul_ip", "npu/conv/conv_mul_logic",
            "npu/conv/conv_weight_all", "npu/cat_add/cat_add_top",
            "npu/cat_add/cat_out_buf_top11", "pcie_dma/pcie_top",
            "pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_cpld_tx_ctrl",
            "pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_mrd_tx_ctrl",
            "pcie_dma/pcie_dma_ctrl/fifo/pgs_pciex4_fifo_ctrl",
            "pcie_dma/pcie_dma_ctrl/fifo/pgs_pciex4_fifo_v1_2",
            "pcie_dma/pcie_dma_ctrl/fifo/ipm_distributed_sdpram_v1_2_distributed_fifo",
            "pcie_dma/pcie_dma_ctrl/ipm_distributed_sdpram_v1_2",
            "npu/common/fifo_ram_D", "npu/common/sync_fifo_D"]
    print("\n[与计划清单对照]")
    for p in plan:
        rp = f"source/{p}.v"
        mark = "死✓" if rp in dead_files else ("存在" if rp in files else "缺失!")
        print(f"  [{mark}] {p}.v")

if __name__ == "__main__":
    main()
