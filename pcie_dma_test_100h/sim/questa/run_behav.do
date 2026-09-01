# Run from the PCIe project root. This smoke uses a controlled PCIe boundary
# model; it does not claim LTSSM, TLP, DMA, or electrical-link coverage.
onerror {
    puts "ERROR: PCIe behavior smoke failed"
    quit -code 1 -force
}

if {![info exists env(SIM_PROJECT_ROOT)] || ![file isdirectory $env(SIM_PROJECT_ROOT)]} {
    error "SIM_PROJECT_ROOT must identify the PCIe project root"
}
set project_root [file normalize $env(SIM_PROJECT_ROOT)]
cd $project_root

file mkdir build/logs
if {[file exists build/logs/sim-behav.log]} {
    file delete -force build/logs/sim-behav.log
}
transcript file build/logs/sim-behav.log

if {![info exists env(SIM_RUN_ID)] || ![regexp {^[0-9a-f]{32}$} $env(SIM_RUN_ID)]} {
    error "SIM_RUN_ID must be a 32-character lowercase hexadecimal value"
}
if {![file isdirectory ../build/simlib/usim]} {
    error "USIM library not found: ../build/simlib/usim"
}

echo "INFO: SIM_RUN_ID=$env(SIM_RUN_ID)"

set work_dir "build/sim/behav/$env(SIM_RUN_ID)/work"
file mkdir [file dirname $work_dir]
vlib $work_dir
vmap work $work_dir
vmap usim ../build/simlib/usim

vlog -sv -work work -f sim/questa/behav.f

vsim \
    -voptargs="+acc" \
    -L usim \
    work.tb_pcie_dma_test

run -all
quit -code 0 -force
