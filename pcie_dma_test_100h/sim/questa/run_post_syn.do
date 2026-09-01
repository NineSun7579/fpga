# Run from the PCIe project root through scripts/run.ps1. This smoke verifies
# the synthesis netlist boundary and does not claim implementation timing.
onerror {
    puts "ERROR: PCIe post-synthesis smoke failed"
    quit -code 1 -force
}

if {![info exists env(SIM_PROJECT_ROOT)] || ![file isdirectory $env(SIM_PROJECT_ROOT)]} {
    error "SIM_PROJECT_ROOT must identify the PCIe project root"
}
set project_root [file normalize $env(SIM_PROJECT_ROOT)]
cd $project_root

file mkdir build/logs
if {[file exists build/logs/sim-post-syn.log]} {
    file delete -force build/logs/sim-post-syn.log
}
transcript file build/logs/sim-post-syn.log

if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![info exists env(PANGO_PDS_ROOT)] || ![file isdirectory $env(PANGO_PDS_ROOT)]} {
    error "PANGO_PDS_ROOT must identify the installed PDS root"
}
if {![file isdirectory ../build/simlib/usim]} {
    error "USIM library not found: ../build/simlib/usim"
}
if {![file isfile build/pds/synthesize/pcie_dma_test_syn.vm]} {
    error "Post-synthesis netlist not found: build/pds/synthesize/pcie_dma_test_syn.vm"
}

echo "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"

set run_root  [file normalize "build/sim/post_syn/$env(SIM_RUN_ID)"]
set work_dir  "$run_root/work"
set vendor_dir "$run_root/pcie_vendor"
file mkdir $run_root
vlib $work_dir
vlib $vendor_dir
vmap work $work_dir
vmap usim ../build/simlib/usim
vmap pcie_vendor $vendor_dir

do sim/questa/compile_vendor_link.do
vlog -sv -work work -f sim/questa/post_syn.f

vsim \
    -voptargs="+acc" \
    -L usim \
    -L pcie_vendor \
    work.tb_pcie_dma_post_syn

run -all
quit -code 0 -force
