set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_constraint_load_fix01/candidate02/constraints_live/synthesis_exact_clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_constraint_load_fix01/candidate02/constraints_live/production60.lcf}
dev_map -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_constraint_load_fix01/candidate02/synthesize/v7_sdt_top_syn.adf} -override_pcf TRUE -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0
