error {DRAFT ONLY: no real PNR/full input binding yet}
set root {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_route_prepare01/execution01}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
.switch_db -input $root/place_route/v7_sdt_top_pnr.adf -output $root/evidence/runtime/final_export/routed_dump.txt
report_timing -input_db_file $root/place_route/v7_sdt_top_pnr.adf -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE
