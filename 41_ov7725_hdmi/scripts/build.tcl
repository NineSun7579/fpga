# Rebuild the OV7725-to-HDMI design from the active PDS project inputs.
# Generated databases and reports are written below the caller-provided work
# directory. The GUI-recorded prj/impl.tcl history is intentionally ignored.

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
puts "INFO: top module: ov7725_hdmi"

set_arch \
    -family Logos2 \
    -device PG2L100H \
    -package FBG484 \
    -speedgrade -6

# Preserve the source order from prj/ov7725_hdmi.pds. The 16 hand-written
# Verilog files are added explicitly; generated IP sources are expanded only
# through their four IDF files to avoid duplicate module definitions.
set design_sources [list \
    "rtl/ov7725_hdmi.v" \
    "rtl/ov7725_dri/i2c_dri.v" \
    "rtl/ov7725_dri/i2c_ov7725_rgb565_cfg.v" \
    "rtl/ov7725_dri/ov7725_dri.v" \
    "rtl/hdmi_top/asyn_rst_syn.v" \
    "rtl/hdmi_top/dvi_encoder.v" \
    "rtl/hdmi_top/dvi_transmitter_top.v" \
    "rtl/hdmi_top/hdmi_top.v" \
    "rtl/hdmi_top/serializer_10_to_1.v" \
    "rtl/hdmi_top/video_driver.v" \
    "rtl/ddr3_ctrl_top/aq_axi_master.v" \
    "rtl/ddr3_ctrl_top/ctrl_fifo.v" \
    "rtl/ddr3_ctrl_top/ddr3_ctrl_top.v" \
    "rtl/ddr3_ctrl_top/ddr3_rw_ctrl.v" \
    "rtl/ov7725_dri/cmos_capture_data.v" \
    "rtl/hdmi_top/video_display.v"]

foreach relative_path $design_sources {
    set source_path "$project_root/$relative_path"
    if {![file exists $source_path]} {
        error "Missing design source: $source_path"
    }
    add_design $source_path
}

set ip_sources [list \
    "prj/ipcore/pll_clk/pll_clk.idf" \
    "prj/ipcore/ddr3_ip/ddr3_ip.idf" \
    "prj/ipcore/wr_fifo/wr_fifo.idf" \
    "prj/ipcore/rd_fifo/rd_fifo.idf"]

foreach relative_path $ip_sources {
    set ip_path "$project_root/$relative_path"
    if {![file exists $ip_path]} {
        error "Missing IP definition: $ip_path"
    }
    add_design $ip_path
}

set constraint_file "$project_root/prj/source/ov7725_hdmi.fdc"
if {![file exists $constraint_file]} {
    error "Missing design constraint: $constraint_file"
}
add_constraint $constraint_file

puts "INFO: compiling 16 Verilog sources and 4 IP definitions"
compile -top_module ov7725_hdmi

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

puts "INFO: OV7725 HDMI implementation completed"
