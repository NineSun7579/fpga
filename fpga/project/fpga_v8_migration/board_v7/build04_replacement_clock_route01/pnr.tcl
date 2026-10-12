set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/cdc.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/ddr3.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/ov5640.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/pcie.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/constraints/sfp.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/device_map/v7_sdt_top.pcf}
pnr -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_replacement_clock_route01/work/device_map/v7_sdt_top_map.adf} -optimize_multi_corner_timing -fix_hold_violation -report_timing
