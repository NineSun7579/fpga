# Diagnose Questa negative-timing solvers without changing the canonical S2-F
# acceptance entry. All three runs use the same netlist, SDF, libraries and TB.
onerror {
    puts "ERROR: PCIe post-PNR timing diagnostic failed"
    quit -code 1 -force
}

if {![info exists env(SIM_PROJECT_ROOT)] || ![file isdirectory $env(SIM_PROJECT_ROOT)]} {
    error "SIM_PROJECT_ROOT must identify the PCIe project root"
}
if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![info exists env(SIM_GLS_NEG_TCHK_LEVEL)] ||
    ![regexp {^level[123]$} $env(SIM_GLS_NEG_TCHK_LEVEL)]} {
    error "SIM_GLS_NEG_TCHK_LEVEL must be level1, level2 or level3"
}

set project_root [file normalize $env(SIM_PROJECT_ROOT)]
set solver_level $env(SIM_GLS_NEG_TCHK_LEVEL)
cd $project_root

file mkdir build/logs
set level_log "build/logs/sim-post-pnr-timing-diagnostic-$solver_level.log"
if {[file exists $level_log]} {
    file delete -force $level_log
}
transcript file $level_log
echo "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"
echo "INFO: GLS_NEG_TCHK_LEVEL=$solver_level"
echo "INFO: DIAGNOSTIC_ONLY=S2F_ACCEPTANCE_UNCHANGED"

set simlib_root [file normalize "$project_root/../build/simlib"]
foreach library_name {usim vsim hsstlp_lane hsstlp_pll pciegen2} {
    if {![file isdirectory "$simlib_root/$library_name"]} {
        error "Pango simulation library not found: $library_name"
    }
}

set timing_netlist build/pds/generate_netlist/pcie_dma_test_sim.v
set sdf_file build/pds/generate_netlist/pcie_dma_test_sta.sdf
foreach required_file [list $timing_netlist $sdf_file] {
    if {![file isfile $required_file] || [file size $required_file] <= 0} {
        error "Post-PNR timing input not found or empty: $required_file"
    }
}

# The generated timing netlist owns the only SDF annotation request.
set netlist_handle [open $timing_netlist r]
set embedded_sdf 0
while {[gets $netlist_handle netlist_line] >= 0} {
    if {[string first {$sdf_annotate("pcie_dma_test_sta.sdf")} $netlist_line] >= 0} {
        set embedded_sdf 1
        break
    }
}
close $netlist_handle
if {!$embedded_sdf} {
    error "Timing netlist does not contain the expected embedded SDF annotation"
}

set sdf_handle [open $sdf_file r]
set sdf_design_found 0
while {[gets $sdf_handle sdf_line] >= 0} {
    if {[regexp {\(DESIGN\s+"pcie_dma_test"\)} $sdf_line]} {
        set sdf_design_found 1
        break
    }
}
close $sdf_handle
if {!$sdf_design_found} {
    error "SDF design name does not match pcie_dma_test"
}

set run_root [file normalize \
    "build/sim/post_pnr_timing_diagnostic/$env(SIM_RUN_ID)/$solver_level"]
set work_dir "$run_root/work"
file mkdir $run_root
vlib $work_dir
vmap work $work_dir
vmap usim "$simlib_root/usim"
vmap vsim "$simlib_root/vsim"
vmap hsstlp_lane "$simlib_root/hsstlp_lane"
vmap hsstlp_pll "$simlib_root/hsstlp_pll"
vmap pciegen2 "$simlib_root/pciegen2"

# Each solver level runs in an independent process because the TB uses $finish.
vlog -sv -work work -f sim/questa/post_pnr_timing.f
set timing_dir [file dirname [file normalize $timing_netlist]]
cd $timing_dir
vsim \
    -voptargs="+acc" \
    +delayed_timing_checks \
    +ntc_warn \
    -glsnegtchk $solver_level \
    -suppress 2697 \
    -L usim \
    -L vsim \
    -L hsstlp_lane \
    -L hsstlp_pll \
    -L pciegen2 \
    work.tb_pcie_dma_post_pnr_timing

run -all
quit -code 0 -force
