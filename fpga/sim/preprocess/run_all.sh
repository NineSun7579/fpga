#!/bin/bash
# run_all.sh : 预处理 IP 回归脚本 (ModelSim 命令行)
# 用法: ./run_all.sh [W H]   (默认 64x36 快速回归; 640x360 完整回归)
set -e
cd "$(dirname "$0")"

MSBIN="${MODELSIM_BIN:-/c/modeltech64_10.6e/win64}"
W=${1:-64}; H=${2:-36}

echo "== 1. 生成 golden (${W}x${H}, directed) =="
python golden_gen.py --width "$W" --height "$H" --seed 7 --case directed --outdir golden

echo "== 2. 编译 =="
rm -rf work transcript
"$MSBIN/vlib" work >/dev/null
SRC=../../source/preprocess
"$MSBIN/vlog" -quiet "$SRC/rgb2gray.v" "$SRC/colorize.v" "$SRC/sobel_edge.v" \
    "$SRC/align16.v" "$SRC/prep_sync_fifo.v" "$SRC/preprocess_top.v" \
    "$SRC/button_debounce.v" "$SRC/prep_regs.v" "$SRC/lane_detect.v" ../../source/ov5640/ov5640_reg.v ../../source/ov5640/ovreg_axil_decode.v tb_ovreg_axil_decode.v \
    tb_rgb2gray.v tb_colorize.v tb_sobel_edge.v tb_preprocess_top.v \
    tb_prep_regs.v tb_button_debounce.v

echo "== 3. 回归 =="
PASS=0; FAIL=0
run_tb () {
    local tb=$1; local tag=$2; shift 2
    echo "--- ${tb} ${tag} ---"
    if "$MSBIN/vsim" -c -quiet -do "run -all; quit -f" "work.$tb" $* 2>&1 | tee "log_${tb}_${tag}.txt" | grep -qE "TB_PASS"; then
        echo ">>> PASS: ${tb} ${tag}"
        PASS=$((PASS+1))
    else
        echo ">>> FAIL: ${tb} ${tag} (见 log_${tb}_${tag}.txt)"
        FAIL=$((FAIL+1))
    fi
}

run_tb tb_rgb2gray gray "+W=$W +H=$H"
run_tb tb_colorize color "+W=$W +H=$H"
run_tb tb_sobel_edge sobel "+W=$W +H=$H"
run_tb tb_preprocess_top mode0 "+MODE=0 +W=$W +H=$H"
run_tb tb_preprocess_top mode1 "+MODE=1 +W=$W +H=$H"
run_tb tb_preprocess_top mode2 "+MODE=2 +W=$W +H=$H"
run_tb tb_preprocess_top mode3 "+MODE=3 +W=$W +H=$H"
run_tb tb_preprocess_top bypass "+MODE=9 +W=$W +H=$H"
run_tb tb_button_debounce btn ""
run_tb tb_prep_regs regs ""
run_tb tb_ovreg_axil_decode dec ""

echo "== 回归结果: PASS=$PASS FAIL=$FAIL =="
echo "== 4. HW vs golden compare + sampling verify =="
if python compare.py --width "$W" --height "$H" --report verify_report.md; then
    echo ">>> compare PASS (verify_report.md)"
else
    echo ">>> compare FAIL (see verify_report.md)"
    FAIL=$((FAIL+1))
fi
[ $FAIL -eq 0 ] && echo "ALL PASS ✓" || echo "存在失败 ✗"
exit $FAIL
