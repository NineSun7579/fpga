set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/clock.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/cdc.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/ddr3.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/ov5640.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/pcie.fdc}
add_constraint {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_functional_route04/functional_candidate01/constraints_live/sfp.fdc}
synthesize -force_to_run -ads
