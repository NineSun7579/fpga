# REVIEW ONLY. Guard removed only by a separately sealed producer after real gates.
error {DRAFT BLOCKED: mapping60 FAIL; mailbox unique1280 !=1320; KEEPBUF derive blocked; timing reload unproven}
set root {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_route_prepare01/execution01}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
# Fresh shell/project: never register original logical clock.fdc together with replacement.
add_constraint $root/constraints/clock.fdc
add_constraint $root/constraints/cdc.fdc
add_constraint $root/constraints/ddr3.fdc
add_constraint $root/constraints/ov5640.fdc
add_constraint $root/constraints/pcie.fdc
add_constraint $root/constraints/sfp.fdc
# Native PCF preserves physical placements; exact60 equality must already be proved.
add_constraint $root/inputs/device_map/v7_sdt_top.pcf
pnr -force_to_run -input_db_file $root/inputs/device_map/v7_sdt_top_map.adf -optimize_multi_corner_timing -fix_hold_violation
