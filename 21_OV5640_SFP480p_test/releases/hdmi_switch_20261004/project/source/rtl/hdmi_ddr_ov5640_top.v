`timescale 1ns/1ps
// MES50HP PGL50H-6-FBG484: dual OV5640 or computer HDMI IN -> SFP0 CH2.
// Wire protocol stays 1280x480 RGB565; the 100H splits each row at x=640.
// DDR and local HDMI OUT remain outside this optical-only build.
module hdmi_ddr_ov5640_top #(
    parameter COLOR_BAR_TEST=0,
    parameter KEY_DEBOUNCE_CYCLES=500000,
    parameter DIAGNOSTIC_HDMI_BOOT=0
)(
    input sys_clk,
    output [1:0] cmos_init_done,
    inout cmos1_scl, cmos1_sda,
    input cmos1_vsync, cmos1_href, cmos1_pclk,
    input [7:0] cmos1_data,
    output cmos1_reset,
    inout cmos2_scl, cmos2_sda,
    input cmos2_vsync, cmos2_href, cmos2_pclk,
    input [7:0] cmos2_data,
    output cmos2_reset,
    output reg heart_beat_led,
    // MS7200 RGB888 DVP input. Physical reset is low in camera mode.
    input pixclk_in, vs_in, hs_in, de_in,
    input [7:0] r_in, g_in, b_in,
    output rstn_in, iic_scl,
    inout iic_sda,
    output hdmi_int_led,
    input sfp_refckp, sfp_refckn,
    input sfp0_rxp, sfp0_rxn,
    output sfp0_txp, sfp0_txn,
    input sfp1_rxp, sfp1_rxn,
    output sfp1_txp, sfp1_txn,
    output sfp0_tx_disable,
    input sfp0_los,
    output led_sfp_pll, led_sfp_ready, led_sfp_rxsync, led_sfp_pcs,
    output sfp1_tx_disable,
    input key1, key2
);
    wire cfg_clk, clk_25M, pix_clk_unused, locked;
    pll u_pll(.clkin1(sys_clk),.clkout0(pix_clk_unused),.clkout1(cfg_clk),
               .clkout2(clk_25M),.pll_lock(locked));
    reg [15:0] startup_count=0;
    reg startup_ready=0;
    always @(posedge cfg_clk or negedge locked) begin
        if (!locked) begin startup_count <= 0; startup_ready <= 0; end
        else if (startup_count == 10000) startup_ready <= 1;
        else startup_count <= startup_count + 1'b1;
    end
    wire rstn_int = locked && startup_ready;
    wire sys_rst_n, fab_rst_n, mrg_rst_n;
    wire clk2core_tx;
    reg mrg_clk=0;
    always @(negedge clk2core_tx) mrg_clk <= ~mrg_clk;
    video_reset_sync u_sys_reset(sys_clk,rstn_int,sys_rst_n);
    video_reset_sync u_fab_reset(clk2core_tx,rstn_int,fab_rst_n);
    video_reset_sync u_mrg_reset(mrg_clk,rstn_int,mrg_rst_n);

    wire hdmi_request, hdmi_active;
    wire diag_press;
    generate if (DIAGNOSTIC_HDMI_BOOT) begin : g_diagnostic_boot
        // One registered virtual KEY2 press: wait 200 ms, press 100 ms.
        // Production default prunes this counter and never generates a press.
        reg [23:0] counter;
        reg press_q;
        always @(posedge sys_clk or negedge sys_rst_n) begin
            if (!sys_rst_n) begin counter <= 0; press_q <= 0; end
            else begin
                if (counter < 15000000) counter <= counter + 1'b1;
                press_q <= counter >= 10000000 && counter < 15000000;
            end
        end
        assign diag_press = press_q;
    end else begin : g_production_boot
        assign diag_press = 1'b0;
    end endgenerate
    video_mode_keys #(.DEBOUNCE_CYCLES(KEY_DEBOUNCE_CYCLES)) u_keys(
        .clk(sys_clk),.rst_n(sys_rst_n),.key1_n(key1),.key2_n(key2 && !diag_press),
        .hdmi_request(hdmi_request));
    wire source_cam_request_n, source_hdmi_request_n, tx_request_n;
    wire [18:0] selected_video, hdmi_video;
    wire [15:0] merge_data;
    wire merge_de, merge_vs, hdmi_fault, hdmi_format_ok;
    video_mode_switch u_mode(
        .clk(mrg_clk),.rst_n(mrg_rst_n),.hdmi_request(hdmi_request),
        .cam_video({merge_vs,1'b0,merge_de,merge_data}),.hdmi_video(hdmi_video),
        .hdmi_fault(hdmi_fault),.hdmi_active(hdmi_active),
        .source_cam_request_n(source_cam_request_n),
        .source_hdmi_request_n(source_hdmi_request_n),
        .tx_request_n(tx_request_n),.video(selected_video));

    // Mode commits are registered in the fixed merge clock. Assert camera
    // reset immediately on HDMI selection; release only on sys_clk edges.
    wire camera_sys_rst_n;
    video_reset_sync u_camera_sys_reset(sys_clk,sys_rst_n && !hdmi_active,camera_sys_rst_n);
    wire initial_en;
    power_on_delay power_on_delay_inst(.clk_50M(sys_clk),.reset_n(camera_sys_rst_n),
        .camera1_rstn(cmos1_reset),.camera2_rstn(cmos2_reset),.camera_pwnd(),
        .initial_en(initial_en));
    wire [1:0] cmos_init_done_int;
    reg_config #(.COLOR_BAR_TEST(COLOR_BAR_TEST)) coms1_reg_config(
        .clk_25M(clk_25M),.camera_rstn(cmos1_reset),.initial_en(initial_en),
        .i2c_sclk(cmos1_scl),.i2c_sdat(cmos1_sda),
        .reg_conf_done(cmos_init_done_int[0]),.reg_index(),.clock_20k());
    reg_config #(.COLOR_BAR_TEST(COLOR_BAR_TEST)) coms2_reg_config(
        .clk_25M(clk_25M),.camera_rstn(cmos2_reset),.initial_en(initial_en),
        .i2c_sclk(cmos2_scl),.i2c_sdat(cmos2_sda),
        .reg_conf_done(cmos_init_done_int[1]),.reg_index(),.clock_20k());
    assign cmos_init_done = cmos_init_done_int;
    reg [7:0] cmos1_d_d0, cmos2_d_d0;
    reg cmos1_href_d0, cmos2_href_d0, cmos1_vsync_d0, cmos2_vsync_d0;
    always @(posedge cmos1_pclk) begin
        cmos1_d_d0 <= cmos1_data; cmos1_href_d0 <= cmos1_href; cmos1_vsync_d0 <= cmos1_vsync;
    end
    always @(posedge cmos2_pclk) begin
        cmos2_d_d0 <= cmos2_data; cmos2_href_d0 <= cmos2_href; cmos2_vsync_d0 <= cmos2_vsync;
    end
    wire cmos1_pclk_16bit, cmos2_pclk_16bit, cmos1_href_16bit, cmos2_href_16bit;
    wire [15:0] cmos1_d_16bit, cmos2_d_16bit;
    wire cmos1_vs_16bit, cmos2_vs_16bit;
    wire cmos1_byte_rst_n, cmos2_byte_rst_n;
    video_reset_sync u_cmos1_byte_reset(cmos1_pclk,cmos_init_done_int[0],cmos1_byte_rst_n);
    video_reset_sync u_cmos2_byte_reset(cmos2_pclk,cmos_init_done_int[1],cmos2_byte_rst_n);
    cmos_8_16bit cmos1_8_16bit(.pclk(cmos1_pclk),.rst_n(cmos1_byte_rst_n),
        .pdata_i(cmos1_d_d0),.de_i(cmos1_href_d0),.vs_i(cmos1_vsync_d0),
        .pixel_clk(cmos1_pclk_16bit),.pdata_o(cmos1_d_16bit),.de_o(cmos1_href_16bit),.vs_o(cmos1_vs_16bit));
    cmos_8_16bit cmos2_8_16bit(.pclk(cmos2_pclk),.rst_n(cmos2_byte_rst_n),
        .pdata_i(cmos2_d_d0),.de_i(cmos2_href_d0),.vs_i(cmos2_vsync_d0),
        .pixel_clk(cmos2_pclk_16bit),.pdata_o(cmos2_d_16bit),.de_o(cmos2_href_16bit),.vs_o(cmos2_vs_16bit));
    wire merge_req_n = source_cam_request_n && (&cmos_init_done_int);
    wire merge_a_rst_n, merge_b_rst_n, merge_o_rst_n;
    video_reset_sync u_merge_a_reset(cmos1_pclk_16bit,merge_req_n,merge_a_rst_n);
    video_reset_sync u_merge_b_reset(cmos2_pclk_16bit,merge_req_n,merge_b_rst_n);
    video_reset_sync u_merge_o_reset(mrg_clk,merge_req_n,merge_o_rst_n);
    cam2_merge #(.LINE_PIX(640),.LINES(480)) u_cam2_merge(
        .a_clk(cmos1_pclk_16bit),.a_rst_n(merge_a_rst_n),.a_data(cmos1_d_16bit),
        .a_de(cmos1_href_16bit),.a_vs(cmos1_vs_16bit),.corr_mode(4'd0),
        .b_clk(cmos2_pclk_16bit),.b_rst_n(merge_b_rst_n),.b_data(cmos2_d_16bit),
        .b_de(cmos2_href_16bit),.b_vs(cmos2_vs_16bit),
        .o_clk(mrg_clk),.o_rst_n(merge_o_rst_n),
        .c_data(merge_data),.c_de(merge_de),.c_vs(merge_vs));

    wire hdmi_cfg_rst_n, hdmi_init_done;
    video_reset_sync u_hdmi_cfg_reset(cfg_clk,rstn_int && hdmi_active,hdmi_cfg_rst_n);
    assign rstn_in = hdmi_cfg_rst_n;
    ms7200_config u_hdmi_config(.clk(cfg_clk),.reset_n(hdmi_cfg_rst_n),
        .init_done(hdmi_init_done),.scl(iic_scl),.sda(iic_sda));
    hdmi_720p_capture u_hdmi_capture(.pclk(pixclk_in),.out_clk(mrg_clk),
        .request_n(source_hdmi_request_n),.capture_ready(hdmi_init_done),
        .vs_in(vs_in),.hs_in(hs_in),.de_in(de_in),.r_in(r_in),.g_in(g_in),.b_in(b_in),
        .video(hdmi_video),.fault(hdmi_fault),.format_ok(hdmi_format_ok));

    wire tx_vid_rst_n, tx_fab_rst_n;
    video_reset_sync u_tx_vid_reset(mrg_clk,tx_request_n,tx_vid_rst_n);
    video_reset_sync u_tx_fab_reset(clk2core_tx,tx_request_n,tx_fab_rst_n);
    wire [31:0] sfp_tx_d;
    wire [3:0] sfp_tx_k;
    wire hsst_pll_lock, hsst_tx_done_2, hsst_tx_done_3;
    wire hsst_link_ready = hsst_pll_lock && hsst_tx_done_2;
    sfp_video_tx u_sfp_video_tx(.vid_clk(mrg_clk),.vid_rst_n(tx_vid_rst_n),
        .vid_data(selected_video),.fab_clk(clk2core_tx),.fab_rst_n(tx_fab_rst_n),
        .link_ready(hsst_link_ready),.txd(sfp_tx_d),.txk(sfp_tx_k));
    assign sfp0_tx_disable = 1'b0;
    assign sfp1_tx_disable = 1'b1;
    wire sfp_rx_sigdet, sfp_rx_pcs_synced;
    (* ASYNC_REG = "TRUE" *) reg [1:0] pll_sync, ready_sync, los_sync, pcs_sync, det_sync, hdmi_done_sync;
    always @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            pll_sync <= 0; ready_sync <= 0; los_sync <= 3;
            pcs_sync <= 0; det_sync <= 0; hdmi_done_sync <= 0;
        end else begin
            pll_sync <= {pll_sync[0],hsst_pll_lock};
            ready_sync <= {ready_sync[0],hsst_link_ready};
            los_sync <= {los_sync[0],sfp0_los};
            pcs_sync <= {pcs_sync[0],sfp_rx_pcs_synced};
            det_sync <= {det_sync[0],sfp_rx_sigdet};
            hdmi_done_sync <= {hdmi_done_sync[0],hdmi_init_done};
        end
    end
    assign led_sfp_pll = pll_sync[1];
    assign led_sfp_ready = ready_sync[1];
    assign led_sfp_rxsync = pcs_sync[1] && !los_sync[1];
    assign led_sfp_pcs = det_sync[1];
    assign hdmi_int_led = hdmi_done_sync[1];
    reg [25:0] heartbeat_count;
    always @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin heartbeat_count <= 0; heart_beat_led <= 0; end
        else if (heartbeat_count == 24999999) begin
            heartbeat_count <= 0; heart_beat_led <= !heart_beat_led;
        end else heartbeat_count <= heartbeat_count + 1'b1;
    end
    hsst_test u_hsst(
        .i_free_clk(sys_clk),.i_p_refckp_0(sfp_refckp),.i_p_refckn_0(sfp_refckn),
        .i_wtchdg_clr_0(~sys_rst_n),.o_wtchdg_st_0(),.o_pll_done_0(),
        .o_txlane_done_2(hsst_tx_done_2),.o_txlane_done_3(hsst_tx_done_3),
        .o_rxlane_done_2(),.o_rxlane_done_3(),.o_p_clk2core_tx_2(clk2core_tx),
        .i_p_tx2_clk_fr_core(clk2core_tx),.i_p_tx3_clk_fr_core(clk2core_tx),
        .i_p_rx2_clk_fr_core(clk2core_tx),.i_p_rx3_clk_fr_core(clk2core_tx),
        .o_p_pll_lock_0(hsst_pll_lock),.o_p_rx_sigdet_sta_2(sfp_rx_sigdet),
        .o_p_rx_sigdet_sta_3(),.o_p_lx_cdr_align_2(),.o_p_lx_cdr_align_3(),
        .o_p_pcs_lsm_synced_2(sfp_rx_pcs_synced),.o_p_pcs_lsm_synced_3(),
        .i_p_l2rxn(sfp0_rxn),.i_p_l2rxp(sfp0_rxp),
        .i_p_l3rxn(sfp1_rxn),.i_p_l3rxp(sfp1_rxp),
        .o_p_l2txn(sfp0_txn),.o_p_l2txp(sfp0_txp),
        .o_p_l3txn(sfp1_txn),.o_p_l3txp(sfp1_txp),
        .i_txd_2(sfp_tx_d),.i_tdispsel_2(4'b0),.i_tdispctrl_2(4'b0),.i_txk_2(sfp_tx_k),
        .i_txd_3(32'hBC0028BC),.i_tdispsel_3(4'b0),.i_tdispctrl_3(4'b0),.i_txk_3(4'b1001),
        .o_rxstatus_2(),.o_rxd_2(),.o_rdisper_2(),.o_rdecer_2(),.o_rxk_2(),
        .o_rxstatus_3(),.o_rxd_3(),.o_rdisper_3(),.o_rdecer_3(),.o_rxk_3(),
        .i_pll_rst_0(~sys_rst_n));
endmodule
