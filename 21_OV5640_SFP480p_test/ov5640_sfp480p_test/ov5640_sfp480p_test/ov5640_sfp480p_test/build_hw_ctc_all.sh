#!/bin/bash
# 50K 硬件 CTC 版本完整编译脚本

set -e  # 遇到错误立即退出

PROJECT_DIR="/c/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test"
PDS_SHELL="C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe"
LOG_FILE="$PROJECT_DIR/build_hw_ctc_full.log"

cd "$PROJECT_DIR"

echo "======================================" | tee -a "$LOG_FILE"
echo "50K 硬件 CTC 版本完整编译" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

# 1. 综合（Synthesize）
echo -e "\n[1/3] 综合阶段..." | tee -a "$LOG_FILE"
"$PDS_SHELL" -project "$(pwd)/ov5640_sfp480p_test.pds" -run synthesize >> "$LOG_FILE" 2>&1
echo "✓ 综合完成" | tee -a "$LOG_FILE"

# 2. 布局布线（Place & Route）
echo -e "\n[2/3] 布局布线阶段..." | tee -a "$LOG_FILE"
"$PDS_SHELL" -project "$(pwd)/ov5640_sfp480p_test.pds" -run pnr >> "$LOG_FILE" 2>&1
echo "✓ 布局布线完成" | tee -a "$LOG_FILE"

# 3. 生成比特流（Generate Bitstream）
echo -e "\n[3/3] 比特流生成阶段..." | tee -a "$LOG_FILE"
"$PDS_SHELL" -project "$(pwd)/ov5640_sfp480p_test.pds" -run gen_bit_stream >> "$LOG_FILE" 2>&1
echo "✓ 比特流生成完成" | tee -a "$LOG_FILE"

echo -e "\n======================================" | tee -a "$LOG_FILE"
echo "编译完成！" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

# 显示比特流文件信息
echo -e "\n比特流文件:" | tee -a "$LOG_FILE"
ls -lh generate_bitstream/hdmi_ddr_ov5640_top.sbit | tee -a "$LOG_FILE"
