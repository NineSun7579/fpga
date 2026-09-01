# Compile the generated PCIe example and installed Pango models into a vendor
# library. The project canonical HDL is compiled separately by run_link.do.

if {![info exists env(PANGO_PDS_ROOT)]} {
    error "PANGO_PDS_ROOT is required for PCIe vendor model compilation"
}

set project_root   [file normalize [pwd]]
set vendor_sim_dir [file normalize "$project_root/ipcore/pcie_test/sim/modelsim"]
set pds_root       [string map {\\ /} [file normalize $env(PANGO_PDS_ROOT)]]
set model_root     "$pds_root/arch/vendor/pango/verilog/simulation/modelsim10.2c"
set model_log      [file normalize "$project_root/build/logs/vlog-link-vendor-models.log"]

if {![file isdirectory $vendor_sim_dir]} {
    error "Vendor PCIe ModelSim directory not found: $vendor_sim_dir"
}
if {![file isdirectory $model_root]} {
    error "Installed Pango ModelSim model root not found: $model_root"
}

set previous_dir [pwd]
cd $vendor_sim_dir

vlog -sv -work pcie_vendor +incdir+./ ./DWC_pcie_ctl_cc_constants.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/pcie_defs.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/cxpl_defs.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/adm_defs.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/radm_defs.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/port_cfg.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/cap_port_cfg.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/pipe_defines.svh
vlog -sv -work pcie_vendor +incdir+./include ./include/DWC_pcie_ctl_all_defs.svh
vlog -sv -work pcie_vendor +incdir+./power_management \
    ./power_management/DWC_pcie_pm_pkg.svh

# Preserve the vendor-provided DWC/HSST compilation order while replacing only
# its obsolete installation prefix and output library. Marker drift is fatal.
set source_do_path "$vendor_sim_dir/pango_pcie_top_sim.do"
set source_channel [open $source_do_path r]
set source_do [read $source_channel]
close $source_channel

set start_marker {vlog -sv +define+IPS2L_PCIE_SPEEDUP_SIM +define+DWC_DISABLE_CDC_METHOD_REPORTING -override_timescale 1ns/10ps}
set end_marker   {-l vlog_gtp.log}
set start_index  [string first $start_marker $source_do]
set end_index    [string first $end_marker $source_do $start_index]

if {$start_index < 0 || $end_index < 0 ||
    [string first $start_marker $source_do [expr {$start_index + 1}]] >= 0 ||
    [string first $end_marker $source_do [expr {$end_index + 1}]] >= 0} {
    error "Vendor PCIe model compile block markers are missing or ambiguous"
}

set end_index [expr {$end_index + [string length $end_marker] - 1}]
set compile_block [string range $source_do $start_index $end_index]
set old_prefix {D:/pds2022_sp6_4/PDS_2022.2-SP6.4/ip/system_ip/ips2l_pcie_gen2/ips2l_pcie_gen2_eval/ips2l_pcie_gen2/../../../../../}

if {[string first $old_prefix $compile_block] < 0} {
    error "Vendor PCIe model compile block no longer contains the approved path prefix"
}

set compile_block [string map [list \
    $old_prefix "$pds_root/" \
    {-l vlog_gtp.log} "-l \"$model_log\""] $compile_block]
regsub {^vlog[ \t]+} $compile_block {vlog -work pcie_vendor } compile_block

if {[string first {D:/pds2022_sp6_4/} $compile_block] >= 0} {
    error "Vendor PCIe model compile block still contains the obsolete PDS path"
}

puts "INFO: compiling installed Pango PCIe models from $model_root"
uplevel #0 $compile_block

cd $previous_dir
