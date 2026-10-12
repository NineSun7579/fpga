open_project {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/project.pds}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
.switch_db -input {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/synthesis_export/synthesis_dump.txt} -output {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/physical_03/route01_recovered_syn.adf}
if {![file exists {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/physical_03/route01_recovered_syn.adf}]} {error {Recovered synthesis DB missing}}
dev_map -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/physical_03/route01_recovered_syn.adf}
if {![file exists {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/device_map/v7_sdt_top_map.adf}]} {error {Actual mapped DB missing}}
pnr -force_to_run -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_route_01/device_map/v7_sdt_top_map.adf} -optimize_multi_corner_timing -fix_hold_violation
