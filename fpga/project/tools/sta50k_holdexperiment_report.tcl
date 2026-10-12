set root [file normalize [pwd]]
if {[file tail $root] ne "sta50k_holdexperiment"} {
    error "Refusing execution outside the distinct hold experiment directory"
}
set routed [file join $root place_route hdmi_ddr_ov5640_top_pnr.adf]
if {![file exists $routed]} { error "Missing newly routed isolated ADF" }
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
report_timing -input_db_file $routed -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE
