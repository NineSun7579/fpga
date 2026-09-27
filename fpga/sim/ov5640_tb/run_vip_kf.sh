#!/usr/bin/env bash
#=============================================================================
# run_vip_kf.sh -- vip_kf 时域卡尔曼/IIR 滤波器回归
#
#   1) ModelSim 编译 vip_kf.v + tb_vip_kf.v 并运行 (生成 kf_in.mem / kf_hw_out.mem)
#   2) Python 黄金模型逐位比对 (vip_kf_compare.py)
#
# 运行 (工程根目录):  bash sim/ov5640_tb/run_vip_kf.sh
# ModelSim 目录可用 MODELSIM_BIN 覆盖 (默认 C:/modeltech64_10.6e/win64).
#=============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MS="${MODELSIM_BIN:-C:/modeltech64_10.6e/win64}"
cd "$ROOT"

echo "[1/3] vlib"
"$MS/vlib.exe" sim/ov5640_tb/work_vipkf >/dev/null 2>&1 || true

echo "[2/3] vlog + vsim"
"$MS/vlog.exe" -quiet -work sim/ov5640_tb/work_vipkf source/ov5640/vip_kf.v
"$MS/vlog.exe" -quiet -work sim/ov5640_tb/work_vipkf sim/ov5640_tb/tb_vip_kf.v
"$MS/vsim.exe" -c -lib sim/ov5640_tb/work_vipkf tb_vip_kf \
    -do "run -all; quit -f" -l sim/ov5640_tb/kf_sim.log

echo "[3/3] python golden compare"
python sim/ov5640_tb/vip_kf_compare.py
