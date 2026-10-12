set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
compile -top_module fpga_v8_cooperative_top_v2_rfg01
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 200 -fix_hold_violation_threshold_for_clk_tree 200 -max_hold_violated_paths_num 30000
