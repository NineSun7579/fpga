error {BLOCKED: main-session bound enable and real evidence required; timing CDB reload remains separately unproven}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
.switch_db -input {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/place_route/v7_sdt_top_pnr.adf} -output {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/reports/routed_dump.txt}
report_timing -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/place_route/v7_sdt_top_pnr.adf} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE
