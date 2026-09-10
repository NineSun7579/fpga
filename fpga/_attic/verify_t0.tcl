# 任务0 验证 + 基线重编译 (pds_shell 批处理)
# 序列与 2026-09-08 20:12 GUI 成功运行完全一致
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
compile -top_module top
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr
report_timing
