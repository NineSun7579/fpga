    .xdma_clk (pcie_clk),
    .xdma_irq (          )
);

// =====================================================================
// [SFP 2026-09-29] fiber RX path:
//   SFP(QR3 HSST CH2) -> sfp_rx_link -> sfp_video_rx (1280 wide unpack)
//   -> sfp_rx_cam_if (split 640+640 + CDC to axi_clk)
//   -> cam5/cam6 ov5640_ddr write engines -> axi_dma_write -> ddr_w_arb m4/m5
//   DDR ping-pong: cam5 0x0180_0000/0x01A0_0000, cam6 0x01C0_0000/0x01E0_0000
// =====================================================================
sfp_rx_link u_sfp_rx_link (
    .i_free_clk       (free_clk),
    .i_refckp         (ref_clk_p),      // F6, shared with PCIe
    .i_refckn         (ref_clk_n),      // E6
    .i_l2rxn          (sfp_l2rxn),      // D11
    .i_l2rxp          (sfp_l2rxp),      // C11
    .o_l2txn          (sfp_l2txn),      // D5
    .o_l2txp          (sfp_l2txp),      // C5
    .o_sfp_tx_disable (sfp_tx_disable), // L16
    .o_rx_clk         (sfp_rx_clk),
    .o_rx_rst_n       (sfp_rx_rst_n),
    .o_rxd            (sfp_rxd),
    .o_rxk            (sfp_rxk),
    .o_rx_en          (sfp_rx_en),
    .o_pll_lock       (),
    .o_rxlane_done    (),
    .o_pcs_synced     (),
    .o_rx_sigdet      ()
);

sfp_video_rx u_sfp_video_rx (
    .i_clk      (sfp_rx_clk),
    .i_rst_n    (sfp_rx_rst_n),
    .i_en       (sfp_rx_en),
    .i_rxd      (sfp_rxd),
    .i_rxk      (sfp_rxk),
    .o_vs       (sfp_vs),
    .o_hs       (sfp_hs),
    .o_de       (sfp_de),
    .o_pix      (sfp_pix),
    .o_overflow ()
);

sfp_rx_cam_if #(
    .IMG_W   (1280),
    .SPLIT_W (640),
    .FIFO_D  (1024)
) u_sfp_rx_cam_if (
    .i_rx_clk   (sfp_rx_clk),
    .i_rx_rst_n (sfp_rx_rst_n),
    .i_vs       (sfp_vs),
    .i_hs       (sfp_hs),
    .i_de       (sfp_de),
    .i_pix      (sfp_pix),
    .i_axi_clk  (axi_clk),
    .i_axi_rst_n(~axi_rst),
    .o_vs5  (cam5_vs),  .o_hs5 (cam5_hs),  .o_de5 (cam5_de),  .o_pix5 (cam5_pix),
    .o_vs6  (cam6_vs),  .o_hs6 (cam6_hs),  .o_de6 (cam6_de),  .o_pix6 (cam6_pix)
);

// ---- cam5 write engine (fiber left half = 50K CMOS1) ----
ov5640_ddr #(
    .DATA_WIDTH     (16),
    .AXI_ADDR_WIDTH (32),
    .AXI_LEN_WIDTH  (32),
    .AXI_DATA_WIDTH (128),
    .CAM_DATA_LEN   (38400),            // 640*480*2/16
    .DEVICE         ("PG")
) cam5_ov5640_ddr (
    .axi_clk        (axi_clk),
    .axi_rst        (axi_rst),
    .axi_cam_en     (1'b1),
    .dbg_fault_snapshot (), .dbg_reject_counts (), .dbg_input_pixels (),
    .dma_abort      (1'b0),
    .dma_abort_req  (),
    .axi_data_available (cam5_s_data_available),
    .dma_done       (1'b0),
    .cam_data_addr_1(32'h0180_0000),
    .cam_data_addr_2(32'h01A0_0000),
    .prev_frame_base(32'h0180_0000),    // KF unused on fiber channels
    .cam_data_len   (38400),
    .s_data         (cam5_pix),
    .s_data_valid   (cam5_de),
    .s_hsync        (cam5_hs),
    .s_vsync        (cam5_vs),
    .axi_data       (cam5_s_data),
    .axi_data_valid (cam5_s_data_valid),
    .axi_data_last  (cam5_s_data_last),
    .axi_data_ready (cam5_s_data_ready),
    .axi_cmd_addr   (cam5_cmd_addr),
    .axi_cmd_len    (cam5_cmd_len),
    .axi_cmd_valid  (cam5_cmd_valid),
    .axi_cmd_ready  (cam5_cmd_ready),
    .dbg_axi_cnt (), .dbg_axi_num (), .dbg_zdin (), .dbg_zout (),
    .dbg_state (), .dbg_last_cnt (), .dbg_wd_cnt (),
    .xdma_req  (),
    .xdma_ack  (2'b00)
);

axi_dma_write #(
    .WAIT_FOR_DATA(1),
    .BURST_LEN  (BURST_LEN)   ,
    .ID_WIDTH   (AXI_ID_LEN)  ,
    .DATA_WIDTH (AXI_DATA_LEN)
) cam5_axi_dma_write (
    .data_in_available(cam5_s_data_available),
    .abort_req(1'b0),
    .data_in_abort(1'b0),
    .clk(axi_clk),
    .rst(axi_rst),
    .cmd_valid (cam5_cmd_valid),
    .cmd_addr  (cam5_cmd_addr ),
    .cmd_len   (cam5_cmd_len  ),
    .cmd_id    (4'b0011),
    .cmd_ready (cam5_cmd_ready),
    .data_in       (cam5_s_data),
    .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
    .data_in_valid (cam5_s_data_valid),
    .data_in_last  (1'b0),
    .data_in_ready (cam5_s_data_ready),
    .m_axi_awid    (cam5_axi_awid),
    .m_axi_awaddr  (cam5_axi_awaddr),
    .m_axi_awlen   (cam5_axi_awlen),
    .m_axi_awsize  (cam5_axi_awsize),
    .m_axi_awburst (cam5_axi_awburst),
    .m_axi_awlock  (cam5_axi_awlock),
    .m_axi_awcache (cam5_axi_awcache),
    .m_axi_awprot  (cam5_axi_awprot),
    .m_axi_awvalid (cam5_axi_awvalid),
    .m_axi_awready (cam5_axi_awready),
    .m_axi_wdata   (cam5_axi_wdata),
    .m_axi_wstrb   (cam5_axi_wstrb),
    .m_axi_wlast   (cam5_axi_wlast),
    .m_axi_wvalid  (cam5_axi_wvalid),
    .m_axi_wready  (cam5_axi_wready),
    .m_axi_bid     (cam5_axi_bid),
    .m_axi_bresp   (cam5_axi_bresp),
    .m_axi_bvalid  (cam5_axi_bvalid),
    .m_axi_bready  (cam5_axi_bready)
);

// ---- cam6 write engine (fiber right half = 50K CMOS2) ----
ov5640_ddr #(
    .DATA_WIDTH     (16),
    .AXI_ADDR_WIDTH (32),
    .AXI_LEN_WIDTH  (32),
    .AXI_DATA_WIDTH (128),
    .CAM_DATA_LEN   (38400),
    .DEVICE         ("PG")
) cam6_ov5640_ddr (
    .axi_clk        (axi_clk),
    .axi_rst        (axi_rst),
    .axi_cam_en     (1'b1),
    .dbg_fault_snapshot (), .dbg_reject_counts (), .dbg_input_pixels (),
    .dma_abort      (1'b0),
    .dma_abort_req  (),
    .axi_data_available (cam6_s_data_available),
    .dma_done       (1'b0),
    .cam_data_addr_1(32'h01C0_0000),
    .cam_data_addr_2(32'h01E0_0000),
    .prev_frame_base(32'h01C0_0000),
    .cam_data_len   (38400),
    .s_data         (cam6_pix),
    .s_data_valid   (cam6_de),
    .s_hsync        (cam6_hs),
    .s_vsync        (cam6_vs),
    .axi_data       (cam6_s_data),
    .axi_data_valid (cam6_s_data_valid),
    .axi_data_last  (cam6_s_data_last),
    .axi_data_ready (cam6_s_data_ready),
    .axi_cmd_addr   (cam6_cmd_addr),
    .axi_cmd_len    (cam6_cmd_len),
    .axi_cmd_valid  (cam6_cmd_valid),
    .axi_cmd_ready  (cam6_cmd_ready),
    .dbg_axi_cnt (), .dbg_axi_num (), .dbg_zdin (), .dbg_zout (),
    .dbg_state (), .dbg_last_cnt (), .dbg_wd_cnt (),
    .xdma_req  (),
    .xdma_ack  (2'b00)
);

axi_dma_write #(
    .WAIT_FOR_DATA(1),
    .BURST_LEN  (BURST_LEN)   ,
    .ID_WIDTH   (AXI_ID_LEN)  ,
    .DATA_WIDTH (AXI_DATA_LEN)
) cam6_axi_dma_write (
    .data_in_available(cam6_s_data_available),
    .abort_req(1'b0),
    .data_in_abort(1'b0),
    .clk(axi_clk),
    .rst(axi_rst),
    .cmd_valid (cam6_cmd_valid),
    .cmd_addr  (cam6_cmd_addr ),
    .cmd_len   (cam6_cmd_len  ),
    .cmd_id    (4'b1100),
    .cmd_ready (cam6_cmd_ready),
    .data_in       (cam6_s_data),
    .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
    .data_in_valid (cam6_s_data_valid),
    .data_in_last  (1'b0),
    .data_in_ready (cam6_s_data_ready),
    .m_axi_awid    (cam6_axi_awid),
    .m_axi_awaddr  (cam6_axi_awaddr),
    .m_axi_awlen   (cam6_axi_awlen),
    .m_axi_awsize  (cam6_axi_awsize),
    .m_axi_awburst (cam6_axi_awburst),
    .m_axi_awlock  (cam6_axi_awlock),
    .m_axi_awcache (cam6_axi_awcache),
    .m_axi_awprot  (cam6_axi_awprot),
    .m_axi_awvalid (cam6_axi_awvalid),
    .m_axi_awready (cam6_axi_awready),
    .m_axi_wdata   (cam6_axi_wdata),
    .m_axi_wstrb   (cam6_axi_wstrb),
    .m_axi_wlast   (cam6_axi_wlast),
    .m_axi_wvalid  (cam6_axi_wvalid),
    .m_axi_wready  (cam6_axi_wready),
    .m_axi_bid     (cam6_axi_bid),
    .m_axi_bresp   (cam6_axi_bresp),
    .m_axi_bvalid  (cam6_axi_bvalid),
    .m_axi_bready  (cam6_axi_bready)
);

`elsif USE_HDMI
