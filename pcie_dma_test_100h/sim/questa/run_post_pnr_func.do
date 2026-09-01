# Run from the PCIe project root through scripts/run.ps1. This smoke verifies
# the placed-and-routed functional netlist without SDF annotation.
onerror {
    puts "ERROR: PCIe post-PNR functional smoke failed"
    quit -code 1 -force
}

if {![info exists env(SIM_PROJECT_ROOT)] || ![file isdirectory $env(SIM_PROJECT_ROOT)]} {
    error "SIM_PROJECT_ROOT must identify the PCIe project root"
}
set project_root [file normalize $env(SIM_PROJECT_ROOT)]
cd $project_root

file mkdir build/logs
if {[file exists build/logs/sim-post-pnr-func.log]} {
    file delete -force build/logs/sim-post-pnr-func.log
}
transcript file build/logs/sim-post-pnr-func.log

if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![file isdirectory ../build/simlib/usim]} {
    error "USIM library not found: ../build/simlib/usim"
}
if {![file isdirectory ../build/simlib/vsim]} {
    error "VSIM library not found: ../build/simlib/vsim"
}
foreach library_name {hsstlp_lane hsstlp_pll pciegen2} {
    if {![file isdirectory "../build/simlib/$library_name"]} {
        error "Pango primitive library not found: ../build/simlib/$library_name"
    }
}
set functional_netlist build/pds/generate_netlist/pcie_dma_test_func.v
if {![file isfile $functional_netlist] || [file size $functional_netlist] <= 0} {
    error "Post-PNR functional netlist not found or empty: $functional_netlist"
}
set netlist_handle [open $functional_netlist r]
set embedded_sdf 0
while {[gets $netlist_handle netlist_line] >= 0} {
    if {[string first {$sdf_annotate} $netlist_line] >= 0} {
        set embedded_sdf 1
        break
    }
}
close $netlist_handle
if {$embedded_sdf} {
    error "Post-PNR functional netlist contains embedded SDF annotation: $functional_netlist"
}

echo "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"

set run_root [file normalize "build/sim/post_pnr_func/$env(SIM_RUN_ID)"]
set work_dir "$run_root/work"
file mkdir $run_root
vlib $work_dir
vmap work $work_dir
vmap usim ../build/simlib/usim
vmap vsim ../build/simlib/vsim
vmap hsstlp_lane ../build/simlib/hsstlp_lane
vmap hsstlp_pll ../build/simlib/hsstlp_pll
vmap pciegen2 ../build/simlib/pciegen2

vlog -sv -work work -f sim/questa/post_pnr_func.f

vsim \
    -voptargs="+acc" \
    -suppress 2697 \
    -L usim \
    -L vsim \
    -L hsstlp_lane \
    -L hsstlp_pll \
    -L pciegen2 \
    work.tb_pcie_dma_post_pnr_func

run -all
quit -code 0 -force
