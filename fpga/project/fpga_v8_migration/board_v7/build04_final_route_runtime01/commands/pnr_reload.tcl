error {BLOCKED: main-session bound enable and real evidence required; timing CDB reload remains separately unproven}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/cdc.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/ddr3.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/ov5640.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/pcie.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/constraints/sfp.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/inputs/device_map/v7_sdt_top.pcf}
pnr -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/inputs/device_map/v7_sdt_top_map.adf} -optimize_multi_corner_timing -fix_hold_violation
