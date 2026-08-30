# Rebuild the integrated PCIe DMA design from version-controlled inputs.
# Generated PDS databases and reports are written below the caller-provided
# work directory; this script never reuses the GUI-recorded impl.tcl history.

set project_root [file normalize "[file dirname [info script]]/.."]

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
puts "INFO: requested final stage: $run_to"

set_arch \
    -family Logos2 \
    -device PG2L50H \
    -package FBG484 \
    -speedgrade -6

# Keep the source order aligned with the last successful .pds project. The
# PCIe IDF is added separately so PDS selects the generated x2 implementation;
# recursively adding ipcore/ would introduce duplicate example modules.
set design_sources [list \
    "hdl/uart2apb_32bit/pgr_apb_ctr_32bit.v" \
    "hdl/uart2apb_32bit/pgr_apb_mif_32bit.v" \
    "hdl/uart2apb_32bit/pgr_clk_gen_32bit.v" \
    "hdl/uart2apb_32bit/pgr_cmd_parser_32bit.v" \
    "hdl/uart2apb_32bit/pgr_fifo_top_32bit.v" \
    "hdl/uart2apb_32bit/pgr_uart_rx_32bit.v" \
    "hdl/uart2apb_32bit/pgr_uart_top_32bit.v" \
    "hdl/uart2apb_32bit/pgr_uart_tx_32bit.v" \
    "hdl/uart2apb_32bit/pgr_uart2apb_top_32bit.v" \
    "hdl/uart2apb_32bit/fifo/pgm_distributed_fifo_ctr_v1_0.v" \
    "hdl/uart2apb_32bit/fifo/pgm_distributed_fifo_v1_1.v" \
    "hdl/uart2apb_32bit/fifo/pgm_distributed_sdpram_v1_1.v" \
    "hdl/uart2apb_32bit/fifo/pgr_prefetch_fifo.v" \
    "hdl/pcie_dma_ctrl/ipm_distributed_sdpram_v1_2.v" \
    "hdl/pcie_dma_ctrl/ips2l_expd_apb_mux.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_controller.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_cpld_tx_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_mrd_tx_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_mwr_tx_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_rd_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_rx_cpld_wr_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_rx_mwr_wr_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_rx_top.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_tlp_rcv.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_tlp_tx_mux.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_tx_cpld_rd_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_tx_mwr_rd_ctrl.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_tx_top.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_wr_ctrl.v" \
    "hdl/pcie_dma_ctrl/pgs_pciex4_prefetch_fifo_v1_2.v" \
    "hdl/pcie_dma_ctrl/fifo/pgs_pciex4_fifo_ctrl.v" \
    "hdl/pcie_dma_ctrl/fifo/pgs_pciex4_fifo_v1_2.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/ips2l_pcie_dma_ram.v" \
    "hdl/pcie_dma_ctrl/fifo/ipm_distributed_sdpram_v1_2_distributed_fifo.v" \
    "hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl/ipm2l_sdpram_v1_1_ips2l_pcie_dma_ram.v" \
    "hdl/pcie_dma_test.v"]

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
