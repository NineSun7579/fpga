error {BLOCKED: main-session bound enable and real evidence required; timing CDB reload remains separately unproven}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
report_timing -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_final_route_runtime01/execution01/place_route/v7_sdt_top_pnr.adf} -force_to_run -delay_type min_max -report_exception TRUE -input_pins TRUE -nworst 2 -max_path 1024 -from {{source_diagnostics/cameras[0].source/mailbox[0]/CLK}} -to {{source_diagnostics/cameras[0].source/host_bank[0]/D}}
