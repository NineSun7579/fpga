set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/diagnostic_sync_register_map12/execution/site/constraints/clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/diagnostic_sync_register_map12/execution/site/constraints/site.lcf}
dev_map -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/diagnostic_sync_register_map12/execution/site/synthesize/map03_twoff_probe_syn.adf} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0
