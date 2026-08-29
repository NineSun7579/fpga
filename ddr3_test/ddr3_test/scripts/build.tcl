# Rebuild the DDR3 vendor example as an explicit board bring-up design.
# The hand-written example RTL is listed here; the generated DDR controller
# and PHY sources are expanded only through ddr3.idf to avoid duplicates.

set project_root [file normalize "[file dirname [info script]]/.."]

if {[info exists ::env(PDS_RUN_TO)]} {
    set run_to $::env(PDS_RUN_TO)
} else {
    set run_to "compile"
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
puts "INFO: top-level role: DDR3 board bring-up example"

set_arch \
    -family Logos2 \
    -device PG2L100H \
    -package FBG484 \
    -speedgrade -6

# Preserve the source order from the successful vendor-generated PDS project.
set example_sources [list \
    "ip_core/ddr3/example_design/rtl/prbs15_64bit_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/prbs31_128bit_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/axi_bist_top_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/test_main_ctrl_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/test_rd_ctrl_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/test_wr_ctrl_v1_0.v" \
    "ip_core/ddr3/example_design/rtl/uart_rd_lock.v" \
    "ip_core/ddr3/example_design/rtl/test_ddr.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_clk_gen_32bit.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_cmd_parser_32bit.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_seu_rs232_intf.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_rx.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_tx.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_32bit.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_top_32bit.v" \
    "ip_core/ddr3/example_design/rtl/uart_ctrl_32bit/ips2l_ver_ctrl_32bit.v" \
    "ip_core/ddr3/example_design/rtl/adc/adc.v" \
    "ip_core/ddr3/example_design/rtl/adc/adc_ctrl.v"]

foreach relative_path $example_sources {
    set source_path "$project_root/$relative_path"
    if {![file exists $source_path]} {
        error "Missing example source: $source_path"
    }
    add_design $source_path
}

set ddr_ip "$project_root/ip_core/ddr3/ddr3.idf"
set timing_constraint "$project_root/ip_core/ddr3/pnr/ddr_test.fdc"
set route_constraint "$project_root/ip_core/ddr3/pnr/ddr3.rcf"

foreach required_file [list $ddr_ip $timing_constraint $route_constraint] {
    if {![file exists $required_file]} {
        error "Missing DDR3 project input: $required_file"
    }
}

add_design $ddr_ip
add_constraint $timing_constraint
add_constraint $route_constraint

puts "INFO: compiling Verilog-2001 DDR3 bring-up design"
compile -top_module test_ddr

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
dev_map -detail

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

puts "INFO: generating bitstream"
gen_bit_stream \
    -create_bit_file TRUE \
    -create_bin_file

puts "INFO: DDR3 bring-up implementation completed"
