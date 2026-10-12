set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint -physical -pcf {C:/Users/NineSun/Desktop/ov56401/project/per_camera_fps/pll56/build_aai6kbmf/work/device_map/top.pcf}
set mapped {C:/Users/NineSun/Desktop/ov56401/project/per_camera_fps/pll56/build_aai6kbmf/work/device_map/top_map.adf}
pnr -gplace_seed 1 -input_db_file $mapped -force_to_run -slack_prior_in_global_router TRUE -logic_optimize_enable TRUE -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 200 -fix_hold_violation_threshold_for_clk_tree 200 -max_hold_violated_paths_num 50000 -fast_router FALSE
