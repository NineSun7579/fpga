set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_design {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/physical_subagent_evidence_01/fixed_06/tiny_match09/dot/tiny.v}
add_constraint -logic -fdc {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/physical_subagent_evidence_01/fixed_06/tiny_match09/dot/tiny.fdc}
compile -top_module tiny
synthesize -ads
dev_map
report_timing -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/physical_subagent_evidence_01/fixed_06/tiny_match09/dot/device_map/tiny_map.adf} -force_to_run -delay_type max -max_path 100 -nworst 2 -input_pins TRUE -report_exception TRUE
