set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
set base {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_timing_reload_probe01/inputs}
foreach n {clock.fdc cdc.fdc ddr3.fdc ov5640.fdc pcie.fdc sfp.fdc} {add_constraint $base/constraints/$n}
add_constraint $base/device_map/v7_sdt_top.pcf
report_timing -force_to_run -input_db_file $base/diagnostic_only/v7_sdt_top_pnr.adf -delay_type min_max -report_exception TRUE -input_pins TRUE -nworst 2 -max_path 2 -from {{source_diagnostics/cameras[0].source/mailbox[0]/CLK}} -to {{source_diagnostics/cameras[0].source/host_bank[0]/D}}
