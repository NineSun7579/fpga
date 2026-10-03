# Physical-only experiment on the old 201932 mapped database.
set root [file normalize [pwd]]
if {[file tail $root] ne "sta50k_holdexperiment"} {
    error "Refusing execution outside the distinct hold experiment directory"
}
set mapped [file join $root device_map hdmi_ddr_ov5640_top_map.adf]
if {![file exists $mapped]} { error "Missing isolated mapped ADF" }
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
pnr -input_db_file $mapped -force_to_run -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 200 -fix_hold_violation_threshold_for_clk_tree 200 -max_hold_violated_paths_num 15000 -fast_router FALSE
