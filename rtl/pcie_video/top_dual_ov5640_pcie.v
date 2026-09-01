module top_dual_ov5640_pcie (
    input sys_clk,
    input sys_rst_n,
    input cam_pclk_1,
    input cam_vsync_1,
    input cam_href_1,
    input [7:0] cam_data_1,
    output cam_rst_n_1,
    output cam_pwdn_1,
    output cam_scl_1,
    inout cam_sda_1,
    input cam_pclk_2,
    input cam_vsync_2,
    input cam_href_2,
    input [7:0] cam_data_2,
    output cam_rst_n_2,
    output cam_pwdn_2,
    output cam_scl_2,
    inout cam_sda_2,
    output mem_rst_n,
    output mem_ck,
    output mem_ck_n,
    output mem_cke,
    output mem_ras_n,
    output mem_cas_n,
    output mem_we_n,
    output mem_odt,
    output mem_cs_n,
    output [14:0] mem_a,
    output [2:0] mem_ba,
    inout [3:0] mem_dqs,
    inout [3:0] mem_dqs_n,
    inout [31:0] mem_dq,
    output [3:0] mem_dm,
    input pcie_ref_clk_n,
    input pcie_ref_clk_p,
    input pcie_perst_n,
    input [1:0] pcie_rxn,
    input [1:0] pcie_rxp,
    output [1:0] pcie_txn,
    output [1:0] pcie_txp,
    output pcie_link_up
);

localparam [12:0] H_CMOS_DISP = 13'd1920;
localparam [12:0] V_CMOS_DISP = 13'd1080;
localparam [12:0] TOTAL_H_PIXEL = 13'd2200;
localparam [12:0] TOTAL_V_PIXEL = 13'd1125;
localparam [27:0] FRAME_PIXELS = 28'd2073600;

wire pll_lock;
wire clk_50m;
wire pixel_clk_unused;
wire pixel_clk_5x_unused;
wire rst_n = sys_rst_n & pll_lock;
wire cam_valid_1;
wire cam_valid_2;
wire [15:0] cam_data_rgb_1;
wire [15:0] cam_data_rgb_2;
wire cam_frame_1;
wire cam_frame_2;
wire ddr_init_done;
wire ddr_rd_en;
wire [15:0] ddr_rd_data;
wire pcie_clk;
wire pcie_rst_n;
wire axis_valid;
wire [127:0] axis_data;
reg ddr_init_done_d;

pll_clk u_pll_clk (
    .rst(~sys_rst_n), .clkin1(sys_clk), .clkout0(pixel_clk_unused),
    .clkout1(pixel_clk_5x_unused), .clkout2(clk_50m), .lock(pll_lock)
);

ov5640_dri u_cam_1 (
    .clk(clk_50m), .rst_n(rst_n), .cam_pclk(cam_pclk_1), .cam_vsync(cam_vsync_1),
    .cam_href(cam_href_1), .cam_data(cam_data_1), .cam_rst_n(cam_rst_n_1),
    .cam_pwdn(cam_pwdn_1), .cam_scl(cam_scl_1), .cam_sda(cam_sda_1),
    .cmos_h_pixel(H_CMOS_DISP), .cmos_v_pixel(V_CMOS_DISP),
    .total_h_pixel(TOTAL_H_PIXEL), .total_v_pixel(TOTAL_V_PIXEL),
    .capture_start(ddr_init_done), .cam_init_done(), .cmos_frame_vsync(cam_frame_1),
    .cmos_frame_href(), .cmos_frame_valid(cam_valid_1), .cmos_frame_data(cam_data_rgb_1)
);

ov5640_dri u_cam_2 (
    .clk(clk_50m), .rst_n(rst_n), .cam_pclk(cam_pclk_2), .cam_vsync(cam_vsync_2),
    .cam_href(cam_href_2), .cam_data(cam_data_2), .cam_rst_n(cam_rst_n_2),
    .cam_pwdn(cam_pwdn_2), .cam_scl(cam_scl_2), .cam_sda(cam_sda_2),
    .cmos_h_pixel(H_CMOS_DISP), .cmos_v_pixel(V_CMOS_DISP),
    .total_h_pixel(TOTAL_H_PIXEL), .total_v_pixel(TOTAL_V_PIXEL),
    .capture_start(ddr_init_done), .cam_init_done(), .cmos_frame_vsync(cam_frame_2),
    .cmos_frame_href(), .cmos_frame_valid(cam_valid_2), .cmos_frame_data(cam_data_rgb_2)
);

pcie_video_endpoint u_pcie (
    .button_rst_n(sys_rst_n), .perst_n(pcie_perst_n), .txd(), .rxd(1'b1),
    .ref_clk_n(pcie_ref_clk_n), .ref_clk_p(pcie_ref_clk_p), .rxn(pcie_rxn), .rxp(pcie_rxp),
    .txn(pcie_txn), .txp(pcie_txp), .ref_led(), .pclk_led(), .smlh_link_up(),
    .rdlh_link_up(pcie_link_up), .video_clk(pcie_clk), .video_rst_n(pcie_rst_n),
    .video_axis_valid(axis_valid), .video_axis_data(axis_data),
    .pcie_user_clk(pcie_clk), .pcie_user_rst_n(pcie_rst_n)
);

assign ddr_rd_en = ddr_init_done & pcie_rst_n;

ddr3_ctrl_top u_ddr3 (
    .clk(clk_50m), .rd_clk(pcie_clk), .rst_n(rst_n), .ddr3_init_done(ddr_init_done),
    .wd_en_1(cam_valid_1), .wd_en_2(cam_valid_2), .wd_data_1(cam_data_rgb_1),
    .wd_data_2(cam_data_rgb_2), .wd_clk_1(cam_pclk_1), .wd_clk_2(cam_pclk_2),
    .wd_load_1(cam_frame_1), .wd_load_2(cam_frame_2), .rd_en(ddr_rd_en),
    .rd_data(ddr_rd_data), .rd_load(cam_frame_1), .ddr3_pingpang_en(1'b1),
    .ddr3_read_valid(1'b1), .h_disp(H_CMOS_DISP), .addr_rd_min(28'd0),
    .addr_rd_max(FRAME_PIXELS), .rd_burst_len(10'd240), .addr_wd_min(28'd0),
    .addr_wd_max(FRAME_PIXELS), .wd_burst_len(10'd240), .mem_rst_n(mem_rst_n),
    .mem_ck(mem_ck), .mem_ck_n(mem_ck_n), .mem_cke(mem_cke), .mem_ras_n(mem_ras_n),
    .mem_cas_n(mem_cas_n), .mem_we_n(mem_we_n), .mem_odt(mem_odt), .mem_cs_n(mem_cs_n),
    .mem_a(mem_a), .mem_ba(mem_ba), .mem_dqs(mem_dqs), .mem_dqs_n(mem_dqs_n),
    .mem_dq(mem_dq), .mem_dm(mem_dm)
);

always @(posedge pcie_clk or negedge pcie_rst_n)
    if (!pcie_rst_n)
        ddr_init_done_d <= 1'b0;
    else
        ddr_init_done_d <= ddr_init_done;

rgb565_to_axis128 u_packer (
    .clk(pcie_clk), .rst_n(pcie_rst_n), .pixel_valid(ddr_rd_en), .pixel_data(ddr_rd_data),
    .frame_start(ddr_init_done & ~ddr_init_done_d), .axis_valid(axis_valid), .axis_ready(1'b1),
    .axis_data(axis_data), .axis_keep(), .axis_last(), .axis_user()
);

endmodule
