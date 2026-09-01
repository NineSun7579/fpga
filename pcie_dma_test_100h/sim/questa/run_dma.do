# Run from the PCIe project root. This flow uses the generated Pango Root
# Complex and the project-owned Endpoint; it does not model the RK3568 board.
onerror {
    puts "ERROR: PCIe S2-C DMA simulation failed"
    quit -code 1 -force
}

if {![info exists env(SIM_PROJECT_ROOT)] || ![file isdirectory $env(SIM_PROJECT_ROOT)]} {
    error "SIM_PROJECT_ROOT must identify the PCIe project root"
}
set project_root [file normalize $env(SIM_PROJECT_ROOT)]
cd $project_root

file mkdir build/logs
if {[file exists build/logs/sim-dma.log]} {
    file delete -force build/logs/sim-dma.log
}
transcript file build/logs/sim-dma.log

if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![info exists env(PANGO_PDS_ROOT)] || ![file isdirectory $env(PANGO_PDS_ROOT)]} {
    error "PANGO_PDS_ROOT must identify the installed PDS root"
}

echo "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"

set run_root   [file normalize "build/sim/dma/$env(SIM_RUN_ID)"]
set work_dir   "$run_root/work"
set vendor_dir "$run_root/pcie_vendor"

file mkdir $run_root
vlib $work_dir
vlib $vendor_dir
vmap work $work_dir
vmap pcie_vendor $vendor_dir

do sim/questa/compile_vendor_link.do
vlog -sv -override_timescale 1ns/10ps -work work -f sim/questa/dma.f

vsim \
    -voptargs="+acc" \
    -L pcie_vendor \
    work.tb_pcie_dma_s2c

run -all
quit -code 0 -force
