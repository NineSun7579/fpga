error {DRAFT ONLY: full real signoff including full bank gate required}
set root {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_route_prepare01/execution01}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
gen_bit_stream -input_db_file $root/place_route/v7_sdt_top_pnr.adf -force_to_run -create_bit_file TRUE
