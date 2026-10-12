set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/cdc.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/ddr3.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/ov5640.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/pcie.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/constraints_live/sfp.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/device_map/v7_sdt_top.pcf}
pnr -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_diagnostic_behavior_route01/work/device_map/v7_sdt_top_map.adf} -optimize_multi_corner_timing -fix_hold_violation
