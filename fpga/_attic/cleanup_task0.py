#!/usr/bin/env python3
"""任务0 工程瘦身清理脚本（v4 终版执行件）。

前置条件：PDS 已关闭（本脚本不检查进程，由执行流程保证）。
动作：
  1. 备份 project/project.pds -> _attic/project.pds.bak
  2. 移动 9 个备份文件  -> _attic/backups/<原相对路径>
  3. 移动 19 个不可达文件 -> _attic/unreachable/<原相对路径>
  4. 从 project.pds 删除 19 个已登记条目（未登记的备份文件无需删条目）
  5. 打印验证摘要

清单依据（多种方法交叉验证，详见 _attic/任务0_清理报告.md）：
  - run.log 编译证据（PDS 实际只编译 162/187 个登记文件）
  - 字节级+去注释双重可达性分析（reachability_check.py）
  - 全工程 `include 交叉检查（归档目标无一被 include）
  - 计划清单中 6 个 pcie 链文件经查仍被 ips2l_pcie_dma_tx_top 等活模块
    例化，且 source/ 下副本是工程内唯一定义（ipcore example_design 副本
    未登记），故保留不归档 —— 这是与计划清单的唯一差异。
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDS = ROOT / "project" / "project.pds"
ATTIC = ROOT / "_attic"

BACKUPS = [
    "source/axi_crossbar/axis_async_fifo before.v",
    "source/npu/conv/conv_mul copy.v",
    "source/npu/conv/conv_mul_logic copy.v",
    "source/npu/conv/conv_weight copy.v",
    "source/npu/conv11_16/conv11_weight before.v",
    "source/npu/conv11_16/conv11_weight copy.v",
    "source/npu/para/out_add_switch copy.v",
    "source/npu/para/out_conv_switch copy.v",
    "source/npu/para/out_data_switch copy.v",
]
UNREACHABLE = [
    "source/axi_crossbar/axi_crossbar_7x1.v",
    "source/axi_crossbar/axi_crossbar_7x2.v",
    "source/axi_dma/app_width_convert.v",
    "source/axi_dma/axi_pipe.v",
    "source/axi_dma/gen_traffic.v",
    "source/npu/cat_add/cat_add_top.v",
    "source/npu/cat_add/cat_out_buf_top11.v",
    "source/npu/conv/conv_mul.v",
    "source/npu/conv/conv_mul_ip.v",
    "source/npu/conv/conv_mul_logic.v",
    "source/npu/conv/conv_weight_all.v",
    "source/npu/conv11_16/conv11_mul.v",
    "source/npu/conv11_16/conv11_mul_ip.v",
    "source/npu/conv11_16/conv11_top.v",
    "source/npu/conv11_16/conv11_weight_all.v",
    "source/ov5640/axi_lite_to_axi.v",
    "source/pcie_dma/pcie_top.v",
    "source/npu/common/fifo_ram_D.v",
    "source/npu/common/sync_fifo_D.v",
]
KEEP = [
    "source/npu/npu_top/config.v",
    "source/npu/reg/defines.v",
    "source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl/ips2l_pcie_dma_ram_init_param.v",
    "source/constraints/cdc.fdc",
    "source/constraints/clock.fdc",
    "source/constraints/ddr3.fdc",
    "source/constraints/ov5640.fdc",
    "source/constraints/pcie.fdc",
]

def move(rel: str, category: str):
    src = ROOT / rel
    dst = ATTIC / category / rel
    if not src.exists():
        print(f"  [跳过] {rel} (不存在，可能已归档)")
        return False
    if dst.exists():
        sys.exit(f"  [中止] 目标已存在，防覆盖: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"  [归档] {rel}")
    return True

def strip_pds_entries(text: str, rels) -> str:
    removed = 0
    for rel in rels:
        pat = re.compile(
            r'[ \t]*\(_file "\.\./%s"\s*\n[ \t]*\(_format [a-z]+\)\s*\n'
            r'[ \t]*\(_timespec "[^"]*"\)\s*\n[ \t]*\)\s*\n' % re.escape(rel))
        text, n = pat.subn("", text)
        removed += n
    print(f"project.pds 删除条目: {removed}/{len(rels)}")
    if removed != len(rels):
        sys.exit("[中止] 条目删除数与清单不符，请人工检查 project.pds")
    return text

def main():
    print("== 1. 备份 project.pds ==")
    bak = ATTIC / "project.pds.bak"
    if not bak.exists():
        shutil.copy2(PDS, bak)
        print(f"  已备份 -> {bak}")
    else:
        print("  备份已存在，跳过")

    print("== 2. 保护文件存在性检查 ==")
    for k in KEEP:
        if not (ROOT / k).exists():
            sys.exit(f"[中止] 保护文件缺失: {k}")
    print(f"  {len(KEEP)} 个保护文件全部在位")

    print("== 3. 归档备份文件 ==")
    n1 = sum(move(r, "backups") for r in BACKUPS)
    print("== 4. 归档不可达文件 ==")
    n2 = sum(move(r, "unreachable") for r in UNREACHABLE)

    print("== 5. 同步 project.pds ==")
    text = PDS.read_text(encoding="utf-8", errors="strict")
    text = strip_pds_entries(text, UNREACHABLE)
    PDS.write_text(text, encoding="utf-8")

    print(f"== 完成: 归档备份 {n1}/9, 不可达 {n2}/19, 删条目 19 ==")
    print("下一步: 运行 reachability_check.py 验证可达性闭合；")
    print("        在 PDS 重新 Compile 对比编译时间。")

if __name__ == "__main__":
    main()
