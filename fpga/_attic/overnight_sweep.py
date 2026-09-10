#!/usr/bin/env python3
"""overnight_sweep.py : 任务6 通宵性能穷举扫描 (单变量原则, 自动恢复)

每个变体: 字节级修改 config.v -> pds_shell 全流程编译 -> 提取指标 -> 恢复 config.v
前置: 无其他 pds_shell 实例 (脚本自动等待)。
输出: DOC/扫描结果.csv + 每变体独立日志 _attic/sweep_logs/
"""
import csv
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDS = r"C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe"
CONFIG = ROOT / "source" / "npu" / "npu_top" / "config.v"
LOGDIR = ROOT / "_attic" / "sweep_logs"
CSV = ROOT / "DOC" / "扫描结果.csv"

# 变体定义: (名称, [(旧字节串, 新字节串)...])
# 注意 config.v 为 GBK 编码, 全部用字节串替换 (ASCII 参数名无编码冲突)
VARIANTS = [
    ("v1_conv11_par_out_4", [
        (b"`define CONV11_CHA_PAR_OUT          2",
         b"`define CONV11_CHA_PAR_OUT          4")]),
    ("v2_max_in_416", [
        (b"`define MAX_IN_COL             640",
         b"`define MAX_IN_COL             416"),
        (b"`define MAX_IN_ROW             640",
         b"`define MAX_IN_ROW             416")]),
    ("v3_conv33_par_out_16", [
        (b"`define CONV33_CHA_PAR_OUT          8",
         b"`define CONV33_CHA_PAR_OUT          16")]),
    ("v4_conv_par_out_4", [
        (b"`define CONV_CHA_PAR_OUT          2",
         b"`define CONV_CHA_PAR_OUT          4")]),
    ("v5_combo_416_par4", [
        (b"`define MAX_IN_COL             640",
         b"`define MAX_IN_COL             416"),
        (b"`define MAX_IN_ROW             640",
         b"`define MAX_IN_ROW             416"),
        (b"`define CONV11_CHA_PAR_OUT          2",
         b"`define CONV11_CHA_PAR_OUT          4")]),
]


def wait_pds_idle():
    while True:
        r = subprocess.run(["tasklist"], capture_output=True)
        out = r.stdout.decode("gbk", errors="replace")
        if "pds_shell.exe" not in out and "pds.exe" not in out:
            return
        print(f"[{datetime.now():%H:%M:%S}] 等待 PDS 空闲...")
        time.sleep(60)


def apply_edit(edits):
    raw = CONFIG.read_bytes()
    for old, new in edits:
        if old not in raw:
            raise RuntimeError(f"未找到待替换串: {old}")
        raw = raw.replace(old, new, 1)
    CONFIG.write_bytes(raw)


def clean_run_dirs():
    # 防增量流程相位冲突 (Flow-0013): 编译前清空上次产物 (已有备份)
    for d in ("compile", "synthesize", "device_map", "place_route", "constraint_check"):
        p = ROOT / "project" / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def run_compile(tag):
    clean_run_dirs()
    LOGDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / f"{tag}.log"
    t0 = time.time()
    with open(log, "w") as f:
        f.write(f"START {datetime.now()}\n")
        f.flush()
        subprocess.run([PDS, "-project", str(ROOT / "project" / "project.pds"),
                        "-run", "pnr", "-work_dir", str(ROOT / "project")],
                       stdout=f, stderr=subprocess.STDOUT, cwd=str(ROOT / "project"))
    return time.time() - t0, log


def extract(log, proj_dir=None):
    text = log.read_text(errors="replace")
    row = {}
    # 各动作用时
    for act in ("compile", "synthesize", "dev_map", "pnr"):
        m = re.findall(rf"Action {act}: Real time elapsed is (\d+)h:(\d+)m:(\d+)s", text)
        if m:
            h, mi, s = map(int, m[-1])
            row[f"{act}_min"] = round(h * 60 + mi + s / 60, 1)
    # 错误检查
    import re as _re
    row["has_error"] = bool(_re.search(r"^E:", text, _re.M)) or "Program Error Out" in text

    # 项目内再生成的报告 (批量模式产物, 可能与 stdout 不同)
    if proj_dir:
        for rel in ("synthesize/run.log", "device_map/run.log", "place_route/run.log"):
            f = proj_dir / rel
            if f.exists():
                t2 = f.read_text(errors="replace")
                for m in re.finditer(r"Action (\w+): Real time elapsed is (\d+)h:(\d+)m:(\d+)s", t2):
                    act = m.group(1)
                    row[f"{act}_min"] = round(int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 60, 1)
                # 原语计数: GTP_XXX_E2  196 uses
                for m in re.finditer(r"(GTP_[A-Z0-9_]+)\s+(\d+)\s+uses", t2):
                    key = m.group(1).lower()
                    row[key] = m.group(2)
        # 每时钟 WNS (时序摘要若生成)
        for f in (proj_dir / "place_route").glob("top_timing_summary*.txt"):
            t3 = f.read_text(errors="replace")
            sec = re.search(r"Setup Summary\(Slow Corner\):(.*?)Hold Summary", t3, re.S)
            if sec:
                m = re.search(r"clk_150m\s+clk_150m\s+([-\d.]+)", sec.group(1))
                if m:
                    row["wns_clk150m"] = m.group(1)
            m = re.search(r"Design Summary\s*:\s*(.*)", t3)
            if m:
                row["timing_status"] = m.group(1).strip()
    return row


def main():
    wait_pds_idle()
    backup = CONFIG.with_suffix(".v.sweep_backup")
    shutil.copy2(CONFIG, backup)
    rows = []
    try:
        for name, edits in VARIANTS:
            print(f"===== 变体 {name} =====")
            shutil.copy2(backup, CONFIG)   # 单变量原则: 每个变体从原始配置出发
            apply_edit(edits)
            elapsed, log = run_compile(name)
            row = {"variant": name, "wall_min": round(elapsed / 60, 1),
                   "done": datetime.now().isoformat(timespec="seconds")}
            row.update(extract(log, ROOT / "project"))
            rows.append(row)
            # 立即落盘, 断电不丢
            with open(CSV, "w", newline="", encoding="utf-8-sig") as f:
                wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                wtr.writeheader()
                wtr.writerows(rows)
            print(f"  完成: wall={row['wall_min']}min error={row['has_error']}")
    finally:
        shutil.copy2(backup, CONFIG)          # 恢复原始 config.v
        print("config.v 已恢复原始状态")
    print("扫描完成 ->", CSV)


if __name__ == "__main__":
    main()
