# Inert review template. Queue-controller integration has not been authorized.
error "OFFLINE_ONLY: controller integration, single-PDS idle mutex and stage export gates pending"
# Future controller executes ONE stage per process in this arm's own directory.
# It must not remove this guard and run the entire sequence without export gates.
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
add_design {rtl/twoff_probe.v}
add_constraint {constraints/clock.fdc}
add_constraint {constraints/site.lcf}
switch -- $stage {
    compile { compile -top_module map03_twoff_probe }
    synthesis { synthesize -ads -selected_syn_tool_opt 2 }
    mapping {
        dev_map -input_db_file {synthesize/map03_twoff_probe_syn.adf} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0
        export_fdc -file {device_map/actual_roundtrip.fdc}
    }
    default { error "Only compile, synthesis or mapping is in scope" }
}
# PCF reference is deliberately unregistered: post-map loading cannot prove
# map-stage packing inhibition. Actual generated PCF/CDB/FDC must be archived.
