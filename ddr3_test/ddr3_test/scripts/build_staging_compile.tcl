# Compile the regenerated PG2L50H DDR3 staging assets only.
# Board constraints and implementation stages are intentionally out of scope.

if {![info exists ::env(DDR3_STAGING_ROOT)]} {
    error "DDR3_STAGING_ROOT is required"
}
if {![info exists ::env(M2B2_RUN_ID)]} {
    error "M2B2_RUN_ID is required"
}

set staging_root [file normalize $::env(DDR3_STAGING_ROOT)]
set run_id $::env(M2B2_RUN_ID)

puts "INFO: M2B2_RUN_ID=$run_id"
puts "INFO: M2B2_TARGET=Logos2/PG2L50H/FBG484/-6"
puts "INFO: M2B2_TOP=test_ddr"
puts "INFO: M2B2_STAGING_ROOT=$staging_root"

set_arch \
    -family Logos2 \
    -device PG2L50H \
    -package FBG484 \
    -speedgrade -6

# Preserve the source order recorded by the generated PDS example project.
set example_sources [list \
    "example_design/rtl/prbs15_64bit_v1_0.v" \
    "example_design/rtl/prbs31_128bit_v1_0.v" \
    "example_design/rtl/axi_bist_top_v1_0.v" \
    "example_design/rtl/test_main_ctrl_v1_0.v" \
    "example_design/rtl/test_rd_ctrl_v1_0.v" \
    "example_design/rtl/test_wr_ctrl_v1_0.v" \
    "example_design/rtl/uart_rd_lock.v" \
    "example_design/rtl/test_ddr.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_clk_gen_32bit.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_cmd_parser_32bit.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_seu_rs232_intf.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_rx.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_tx.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_32bit.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_top_32bit.v" \
    "example_design/rtl/uart_ctrl_32bit/ips2l_ver_ctrl_32bit.v" \
    "example_design/rtl/adc/adc.v" \
    "example_design/rtl/adc/adc_ctrl.v"]

if {[llength $example_sources] != 18} {
    error "Unexpected M2-B2 example source count"
}

foreach relative_path $example_sources {
    set source_path "$staging_root/$relative_path"
    if {![file exists $source_path]} {
        error "Missing M2-B2 staging source: $source_path"
    }
    add_design $source_path
}

set ddr_ip "$staging_root/ddr3.idf"
if {![file exists $ddr_ip]} {
    error "Missing M2-B2 staging IDF: $ddr_ip"
}
add_design $ddr_ip

puts "INFO: M2B2_SOURCE_COUNT=[llength $example_sources]"
puts "INFO: compiling PG2L50H DDR3 staging design"
compile -top_module test_ddr

puts "INFO: M2B2_COMPILE_OK run_id=$run_id"
