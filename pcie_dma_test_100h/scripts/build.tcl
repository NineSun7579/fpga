# Rebuild the integrated PCIe DMA design from version-controlled inputs.
# Generated PDS databases and reports are written below the caller-provided
# work directory; this script never reuses the GUI-recorded impl.tcl history.

set project_root [file normalize "[file dirname [info script]]/.."]

if {![info exists ::env(PDS_RUN_ID)] ||
    ![regexp {^[0-9a-f]{32}$} $::env(PDS_RUN_ID)]} {
    error "PDS_RUN_ID must be a 32-character lowercase hexadecimal value"
}
set run_id $::env(PDS_RUN_ID)

if {[info exists ::env(PDS_RUN_TO)]} {
    set run_to $::env(PDS_RUN_TO)
} else {
    set run_to "gen_bit_stream"
}

set valid_stages [list \
    compile \
    synthesize \
    dev_map \
    pnr \
    report_timing \
    gen_netlist \
    gen_bit_stream]

if {[lsearch -exact $valid_stages $run_to] < 0} {
    error "Unsupported PDS_RUN_TO stage: $run_to"
}

puts "INFO: project root: $project_root"
puts "INFO: PDS_RUN_ID=$run_id"
puts "INFO: requested final stage: $run_to"

set_arch \
    -family Logos2 \
    -device PG2L50H \
    -package FBG484 \
    -speedgrade -6

# Keep the source order aligned with the last successful .pds project. The
# PCIe IDF is added separately so PDS selects the generated x2 implementation;
# recursively adding ipcore/ would introduce duplicate example modules.
set source_list "$project_root/scripts/pds_sources.f"
if {![file exists $source_list]} {
    error "Missing PDS source list: $source_list"
}
set source_handle [open $source_list r]
set source_text [read $source_handle]
close $source_handle

set design_sources [list]
foreach line [split $source_text "\n"] {
    set relative_path [string trim $line]
    if {$relative_path eq "" || [string match "#*" $relative_path]} {
        continue
    }
    lappend design_sources $relative_path
}
if {[llength $design_sources] == 0} {
    error "PDS source list is empty: $source_list"
}

foreach relative_path $design_sources {
    set source_path "$project_root/$relative_path"
    if {![file exists $source_path]} {
        error "Missing design source: $source_path"
    }
    add_design $source_path
}

set pcie_ip "$project_root/ipcore/pcie_test/pcie_test.idf"
set constraint_file "$project_root/fdc/pcie_dma_test.fdc"

if {![file exists $pcie_ip]} {
    error "Missing PCIe IP definition: $pcie_ip"
}
if {![file exists $constraint_file]} {
    error "Missing design constraint: $constraint_file"
}

add_design $pcie_ip
add_constraint $constraint_file

puts "INFO: compiling Verilog-2001 RTL"
compile \
    -top_module pcie_dma_test \
    -include_path [list \
        $project_root \
        "$project_root/hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl"]

if {$run_to eq "compile"} {
    puts "INFO: requested stage compile completed"
    return
}

puts "INFO: running ADS synthesis"
synthesize \
    -ads \
    -write_verilog TRUE

if {$run_to eq "synthesize"} {
    puts "INFO: requested stage synthesize completed"
    return
}

puts "INFO: mapping design"
dev_map \
    -detail

if {$run_to eq "dev_map"} {
    puts "INFO: requested stage dev_map completed"
    return
}

puts "INFO: running place and route"
pnr \
    -optimize_multi_corner_timing \
    -fix_hold_violation \
    -report_timing

if {$run_to eq "pnr"} {
    puts "INFO: requested stage pnr completed"
    return
}

puts "INFO: generating final timing report"
report_timing \
    -nworst 10 \
    -max_path 100 \
    -report_exception TRUE

if {$run_to eq "report_timing"} {
    puts "INFO: requested stage report_timing completed"
    return
}

puts "INFO: generating post-PNR timing netlist and SDF"
gen_netlist \
    -sdf_annotate TRUE \
    -process_corner slow

if {$run_to eq "gen_netlist"} {
    puts "INFO: requested stage gen_netlist completed"
    return
}

puts "INFO: generating compressed bitstream"
gen_bit_stream \
    -create_bit_file TRUE \
    -create_bin_file \
    -compress_bitstream TRUE \
    -master_configuration_clock_frequency {40M}

puts "INFO: PCIe DMA implementation completed"
puts "INFO: PDS_RUN_COMPLETE=$run_id"
