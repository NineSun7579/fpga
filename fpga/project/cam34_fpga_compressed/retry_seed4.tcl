set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
pnr -input_db_file {D:/race/ov56401/project/cam34_fpga_compressed/project/device_map/top_map.adf} -force_to_run -gplace_seed 4 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE -max_hold_violated_paths_num 15000 -fast_router FALSE
report_timing -input_db_file {D:/race/ov56401/project/cam34_fpga_compressed/project/place_route/top_pnr.adf} -force_to_run -delay_type min_max -nworst 1 -max_path 80 -input_pins TRUE
