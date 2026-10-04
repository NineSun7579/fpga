# Batch build script for ov5640_sfp480p_test (OV5640 480p60 -> SFP0 fiber out)
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484

add_design "source/rtl/hdmi_ddr_ov5640_top.v"
add_design "source/rtl/video_reset_sync.v"
add_design "source/rtl/video_mode_keys.v"
add_design "source/rtl/video_mode_switch.v"
add_design "source/rtl/hdmi_720p_capture.v"
add_design "source/rtl/ms7200_config.v"
add_design "source/rtl/cam2_merge.v"
add_design "source/rtl/sccb_read_probe.v"
add_design "source/rtl/sccb_diag.v"
add_design "source/rtl/iic_dri.v"
#[SLIM] add_design "source/rtl/ms72xx_ctl.v"
add_design "source/rtl/ms7200_ctl.v"
#[SLIM] add_design "source/rtl/ms7210_ctl.v"
add_design "source/rtl/cmos_8_16bit.v"
#[SLIM] add_design "source/rtl/fram_buf.v"
add_design "source/rtl/i2c_com.v"
add_design "source/rtl/power_on_delay.v"
#[SLIM] add_design "source/rtl/rd_buf.v"
#[SLIM] add_design "source/rtl/rd_ctrl.v"
add_design "source/rtl/reg_config.v"
add_design "source/rtl/sfp_video_tx.v"
#[SLIM] add_design "source/rtl/sfp_test_src.v"
add_design "source/rtl/video_async_fifo.v"
#[SLIM] add_design "source/rtl/sync_vg.v"
#[SLIM] add_design "source/rtl/wr_buf.v"
#[SLIM] add_design "source/rtl/wr_cmd_trans.v"
#[SLIM] add_design "source/rtl/wr_ctrl.v"
#[SLIM] add_design "source/rtl/wr_rd_ctrl_top.v"

add_design "source/rtl/pll/pll.idf"
#[SLIM] add_design "source/rtl/wr_fram_buf/wr_fram_buf.idf"
#[SLIM] add_design "source/rtl/rd_fram_buf/rd_fram_buf.idf"
#[SLIM] add_design "source/rtl/DDR3_50H/DDR3_50H.idf"
add_design "source/rtl/hsst_test/hsst_test.idf"

add_constraint "ov5640_sfp480p_test.fdc"
# Require all 31 verified HDMI-IN external pin constraints before compilation.
set hdmi_pin_file [open "hdmi_in_mes50hp.fdc" r]
set hdmi_pin_text [read $hdmi_pin_file]
close $hdmi_pin_file
set hdmi_required_ports {pixclk_in vs_in hs_in de_in rstn_in iic_scl iic_sda}
foreach hdmi_color {r_in g_in b_in} {
    for {set hdmi_bit 0} {$hdmi_bit < 8} {incr hdmi_bit} {
        lappend hdmi_required_ports [format {%s[%d]} $hdmi_color $hdmi_bit]
    }
}
foreach hdmi_port $hdmi_required_ports {
    set hdmi_pin_line [format {define_attribute {p:%s} {PAP_IO_LOC}} $hdmi_port]
    if {[string first $hdmi_pin_line $hdmi_pin_text] < 0} {
        error "MES50HP HDMI-IN pin $hdmi_port is unverified: complete hdmi_in_mes50hp.fdc from the board schematic/original demo before building"
    }
}
add_constraint "hdmi_in_mes50hp.fdc"
add_constraint "timing_cdc.fdc"

compile -top_module hdmi_ddr_ov5640_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold 0
report_timing
gen_bit_stream
