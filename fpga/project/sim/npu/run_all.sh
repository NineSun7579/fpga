#!/bin/bash
# run_all.sh : NPU 算子一致性回归 (需求(2)(3))
# 用法: ./run_all.sh   (golden 生成 -> 编译 -> 逐 TB 仿真 -> compare)
set -e
cd "$(dirname "$0")"

MSBIN="${MODELSIM_BIN:-/c/modeltech64_10.6e/win64}"
SRC=../../source/npu
PDS_SIM="/c/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"

echo "== 1. golden =="
python npu_golden.py

echo "== 2. compile =="
rm -rf work transcript
"$MSBIN/vlib" work >/dev/null
"$MSBIN/vlog" -quiet gtp_apm_e2_sim.v \
    "$SRC/common/spram.v" "$SRC/common/spram_D.v" "$SRC/common/sync_fifo.v" "$SRC/common/fifo_ram.v" "$SRC/common/pipe.v" "$SRC/common/scale_mul_unsign.v" \
    "$SRC/common/scale_mul_unsign_s3.v" "$SRC/common/scale_mul_s3.v" \
    "$SRC/conv/conv_mul_E2.v" "$SRC/conv/conv_conv.v" \
    "$SRC/conv/conv_add.v" "$SRC/conv/conv_top.v" \
    "$SRC/conv/conv_ctrl.v" "$SRC/conv/conv_in_buf.v" "$SRC/conv/conv_in_buf_ctrl.v" \
    "$SRC/conv/conv_in_buf_top.v" "$SRC/conv/conv_in_ctrl.v" \
    "$SRC/conv/conv_weight.v" \
    "$SRC/conv11_16/conv11_mul_E2.v" "$SRC/conv11_16/conv11_conv.v" "$SRC/conv11_16/conv11_ctrl.v" "$SRC/conv11_16/conv11_in_buf.v" "$SRC/conv11_16/conv11_in_buf_ctrl.v" "$SRC/conv11_16/conv11_in_buf_top.v" "$SRC/conv11_16/conv11_in_ctrl.v" "$SRC/conv11_16/conv11_weight.v" "$SRC/conv11_16/conv11_out_buf.v" "$SRC/conv11_16/conv11_out_buf_ctrl.v" "$SRC/conv11_16/conv11_out_buf_top.v" "$SRC/conv11_16/conv11_add.v" "$SRC/conv11_16/conv11_para_top.v" "$SRC/out_buf/out_buf.v" "$SRC/out_buf/out_buf_ctrl.v" "$SRC/out_buf/out_buf_top.v" "$SRC/out_buf/out_switch.v" \
    "$SRC/cat_add/cat_add.v" \
    "$SRC/sppf/sppf_maxpool.v" \
    "$SRC/upsample/upsample_top.v" "$SRC/upsample/upsample_in_buf_top.v" \
    "$SRC/upsample/upsample_in_buf.v" "$SRC/upsample/upsample_in_buf_ctrl.v" \
    "$SRC/upsample/upsample_ctrl.v" \
    tb_cat_add.v tb_conv11_conv.v tb_conv_conv.v tb_sppf_unit.v \
    tb_upsample_top.v tb_conv_top.v tb_conv11_para_top.v

echo "== 3. regress =="
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

run_tb tb_cat_add       cat   ""
run_tb tb_conv11_conv   c11   ""
run_tb tb_conv_conv     c33   ""
run_tb tb_sppf_unit     sppu  ""
run_tb tb_upsample_top  ups   ""
run_tb tb_conv_top      ct    ""
run_tb tb_conv11_para_top p11   ""

echo "== 4. compare =="
if python compare.py; then
    echo ">>> compare PASS (verify_report.md)"
else
    echo ">>> compare FAIL"
    FAIL=$((FAIL+1))
fi

echo "== 回归结果: PASS=$PASS FAIL=$FAIL =="
[ $FAIL -eq 0 ] && echo "ALL PASS" || echo "存在失败"
exit $FAIL
