# Run from the PCIe project root. This flow uses the generated Pango Root
# Complex and the project-owned Endpoint; it does not model the RK3568 board.
onerror {
    puts "ERROR: PCIe S2-B real-link simulation failed"
    quit -code 1 -force
}

file mkdir build/logs
if {[file exists build/logs/sim-link.log]} {
    file delete -force build/logs/sim-link.log
}
transcript file build/logs/sim-link.log

if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![info exists env(PANGO_PDS_ROOT)] || ![file isdirectory $env(PANGO_PDS_ROOT)]} {
    error "PANGO_PDS_ROOT must identify the installed PDS root"
}

puts "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"

set run_root   [file normalize "build/sim/link/$env(SIM_RUN_ID)"]
set work_dir   "$run_root/work"
set vendor_dir "$run_root/pcie_vendor"

file mkdir $run_root
vlib $work_dir
vlib $vendor_dir
vmap work $work_dir
vmap pcie_vendor $vendor_dir

do scripts/compile_vendor_link.do
vlog -sv -work work -f sim/link.f

vsim \
    -voptargs="+acc" \
    -L pcie_vendor \
    work.tb_pcie_dma_link

run -all
quit -code 0 -force
