`timescale 1ns/1ps
// Isolated internal-IO integration candidate. All interfaces share core_clk.
// Packed camera slot i is [i*FIELD_WIDTH +: FIELD_WIDTH], m0 is least significant.
module fpga_v8_cooperative_core_rfg01 #(
    parameter integer WIDTH = 640,
    parameter integer HEIGHT = 480,
    parameter integer OUT_HEIGHT = 640,
    parameter integer TOP_ROWS = 80,
    parameter integer FILL_VALUE = 114,
    parameter [31:0] OUTPUT_BANK0_ADDR = 32'h08000000,
    parameter [31:0] OUTPUT_BANK1_ADDR = 32'h08200000,
    parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000,
    parameter [3:0] AXI_ID = 4'd1
) (
    input wire core_clk,
    input wire rst_n,
    input wire input_valid,
    output wire input_ready,
    input wire input_raw_valid,
    input wire [31:0] input_src_addr,
    input wire [31:0] input_source_seq,
    input wire [31:0] input_generation,
    input wire [2:0] input_camera,
    input wire input_camera_bank,
    input wire [63:0] input_lease_token,
    output wire input_claim,
    output wire input_reject,
    output wire src_release_valid,
    input wire src_release_ready,
    output wire [31:0] src_release_addr,
    output wire [31:0] src_release_seq,
    output wire [31:0] src_release_generation,
    output wire [2:0] src_release_camera,
    output wire src_release_camera_bank,
    output wire [63:0] src_release_token,
    output wire busy,
    output wire [1:0] bank0_state,
    output wire [1:0] bank1_state,
    output wire bridge_busy,
    output wire bridge_done,
    output wire bridge_error,
    output wire bridge_cmd_error,
    output wire arbiter_busy,
    output wire [2:0] arbiter_owner,
    output wire arbiter_error,
    output wire [4:0] arbiter_error_flags,

    input wire [31:0] s_axil_awaddr,
    input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [31:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready,

    input wire [23:0] camera_awid,
    input wire [191:0] camera_awaddr,
    input wire [47:0] camera_awlen,
    input wire [17:0] camera_awsize,
    input wire [11:0] camera_awburst,
    input wire [5:0] camera_awlock,
    input wire [23:0] camera_awcache,
    input wire [17:0] camera_awprot,
    input wire [23:0] camera_awqos,
    input wire [23:0] camera_awregion,
    input wire [5:0] camera_awvalid,
    output wire [5:0] camera_awready,
    input wire [767:0] camera_wdata,
    input wire [95:0] camera_wstrb,
    input wire [5:0] camera_wlast,
    input wire [5:0] camera_wvalid,
    output wire [5:0] camera_wready,
    output wire [23:0] camera_bid,
    output wire [11:0] camera_bresp,
    output wire [5:0] camera_bvalid,
    input wire [5:0] camera_bready,

    output wire [3:0] m_axi_read_arid,
    output wire [31:0] m_axi_read_araddr,
    output wire [7:0] m_axi_read_arlen,
    output wire [2:0] m_axi_read_arsize,
    output wire [1:0] m_axi_read_arburst,
    output wire m_axi_read_arlock,
    output wire [3:0] m_axi_read_arcache,
    output wire [2:0] m_axi_read_arprot,
    output wire [3:0] m_axi_read_arqos,
    output wire [3:0] m_axi_read_arregion,
    output wire m_axi_read_arvalid,
    input wire m_axi_read_arready,
    input wire [3:0] m_axi_read_rid,
    input wire [127:0] m_axi_read_rdata,
    input wire [1:0] m_axi_read_rresp,
    input wire m_axi_read_rlast,
    input wire m_axi_read_rvalid,
    output wire m_axi_read_rready,

    output wire [3:0] m_axi_write_awid,
    output wire [31:0] m_axi_write_awaddr,
    output wire [7:0] m_axi_write_awlen,
    output wire [2:0] m_axi_write_awsize,
    output wire [1:0] m_axi_write_awburst,
    output wire m_axi_write_awlock,
    output wire [3:0] m_axi_write_awcache,
    output wire [2:0] m_axi_write_awprot,
    output wire [3:0] m_axi_write_awqos,
    output wire [3:0] m_axi_write_awregion,
    output wire m_axi_write_awvalid,
    input wire m_axi_write_awready,
    output wire [127:0] m_axi_write_wdata,
    output wire [15:0] m_axi_write_wstrb,
    output wire m_axi_write_wlast,
    output wire m_axi_write_wvalid,
    input wire m_axi_write_wready,
    input wire [3:0] m_axi_write_bid,
    input wire [1:0] m_axi_write_bresp,
    input wire m_axi_write_bvalid,
    output wire m_axi_write_bready,
    input wire session_fault
);
    localparam [31:0] OUTPUT_LENGTH = 32'd3 * WIDTH * OUT_HEIGHT;
    wire cmd_valid, cmd_ready;
    wire [31:0] cmd_src_addr, cmd_dst_addr, cmd_frame_id;
    wire [3:0] bridge_awid, bridge_bid;
    wire [31:0] bridge_awaddr;
    wire [7:0] bridge_awlen;
    wire [2:0] bridge_awsize, bridge_awprot;
    wire [1:0] bridge_awburst, bridge_bresp;
    wire bridge_awlock;
    wire [3:0] bridge_awcache, bridge_awqos, bridge_awregion;
    wire bridge_awvalid, bridge_awready;
    wire [127:0] bridge_wdata;
    wire [15:0] bridge_wstrb;
    wire bridge_wlast, bridge_wvalid, bridge_wready, bridge_bvalid, bridge_bready;
    wire [6:0] all_awready, all_wready, all_bvalid;
    wire [27:0] all_bid;
    wire [13:0] all_bresp;
    assign camera_awready = all_awready[5:0];
    assign camera_wready = all_wready[5:0];
    assign camera_bid = all_bid[23:0];
    assign camera_bresp = all_bresp[11:0];
    assign camera_bvalid = all_bvalid[5:0];
    assign bridge_awready = all_awready[6];
    assign bridge_wready = all_wready[6];
    assign bridge_bid = all_bid[27:24];
    assign bridge_bresp = all_bresp[13:12];
    assign bridge_bvalid = all_bvalid[6];

    fpga_v8_coop_control_axil_rfg01 #(
        .OUTPUT_BANK0_ADDR(OUTPUT_BANK0_ADDR), .OUTPUT_BANK1_ADDR(OUTPUT_BANK1_ADDR),
        .OUTPUT_LENGTH(OUTPUT_LENGTH)
    ) control (
        .session_fault(session_fault),
        .core_clk(core_clk), .rst_n(rst_n),
        .input_valid(input_valid), .input_ready(input_ready),
        .input_raw_valid(input_raw_valid), .input_src_addr(input_src_addr),
        .input_source_seq(input_source_seq), .input_generation(input_generation),
        .input_camera(input_camera), .input_camera_bank(input_camera_bank),
        .input_lease_token(input_lease_token), .input_claim(input_claim),
        .input_reject(input_reject), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr),
        .cmd_frame_id(cmd_frame_id), .bridge_busy(bridge_busy),
        .bridge_done(bridge_done), .bridge_error(bridge_error),
        .bridge_cmd_error(bridge_cmd_error), .src_release_valid(src_release_valid),
        .src_release_ready(src_release_ready), .src_release_addr(src_release_addr),
        .src_release_seq(src_release_seq), .src_release_generation(src_release_generation),
        .src_release_camera(src_release_camera), .src_release_camera_bank(src_release_camera_bank),
        .src_release_token(src_release_token), .busy(busy),
        .bank0_state(bank0_state), .bank1_state(bank1_state),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot),
        .s_axil_awvalid(s_axil_awvalid), .s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready),
        .s_axil_bresp(s_axil_bresp), .s_axil_bvalid(s_axil_bvalid),
        .s_axil_bready(s_axil_bready), .s_axil_araddr(s_axil_araddr),
        .s_axil_arprot(s_axil_arprot), .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata),
        .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready)
    );

    fpga_v8_raw_frame_axi #(
        .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT),
        .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE),
        .ID_WIDTH(4), .AXI_ID(AXI_ID), .DDR_ADDRESS_LIMIT(DDR_ADDRESS_LIMIT)
    ) bridge (
        .clk(core_clk), .rst_n(rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr), .cmd_frame_id(cmd_frame_id),
        .cmd_error(bridge_cmd_error), .busy(bridge_busy), .done(bridge_done), .error(bridge_error),
        .active_src_addr(), .active_dst_addr(), .active_frame_id(), .completed_frame_id(),
        .m_axi_read_arid(m_axi_read_arid), .m_axi_read_araddr(m_axi_read_araddr),
        .m_axi_read_arlen(m_axi_read_arlen), .m_axi_read_arsize(m_axi_read_arsize),
        .m_axi_read_arburst(m_axi_read_arburst), .m_axi_read_arlock(m_axi_read_arlock),
        .m_axi_read_arcache(m_axi_read_arcache), .m_axi_read_arprot(m_axi_read_arprot),
        .m_axi_read_arqos(m_axi_read_arqos), .m_axi_read_arregion(m_axi_read_arregion),
        .m_axi_read_arvalid(m_axi_read_arvalid), .m_axi_read_arready(m_axi_read_arready),
        .m_axi_read_rid(m_axi_read_rid), .m_axi_read_rdata(m_axi_read_rdata),
        .m_axi_read_rresp(m_axi_read_rresp), .m_axi_read_rlast(m_axi_read_rlast),
        .m_axi_read_rvalid(m_axi_read_rvalid), .m_axi_read_rready(m_axi_read_rready),
        .m_axi_write_awid(bridge_awid), .m_axi_write_awaddr(bridge_awaddr),
        .m_axi_write_awlen(bridge_awlen), .m_axi_write_awsize(bridge_awsize),
        .m_axi_write_awburst(bridge_awburst), .m_axi_write_awlock(bridge_awlock),
        .m_axi_write_awcache(bridge_awcache), .m_axi_write_awprot(bridge_awprot),
        .m_axi_write_awqos(bridge_awqos), .m_axi_write_awregion(bridge_awregion),
        .m_axi_write_awvalid(bridge_awvalid), .m_axi_write_awready(bridge_awready),
        .m_axi_write_wdata(bridge_wdata), .m_axi_write_wstrb(bridge_wstrb),
        .m_axi_write_wlast(bridge_wlast), .m_axi_write_wvalid(bridge_wvalid),
        .m_axi_write_wready(bridge_wready), .m_axi_write_bid(bridge_bid),
        .m_axi_write_bresp(bridge_bresp), .m_axi_write_bvalid(bridge_bvalid),
        .m_axi_write_bready(bridge_bready)
    );

    // The verified candidate arbiter has synchronous active-low rst_n.
    fpga_v8_ddr_write_arbiter #(
        .MASTER_COUNT(7), .ID_WIDTH(4), .ADDR_WIDTH(32), .DATA_WIDTH(128), .OWNER_WIDTH(3)
    ) write_arbiter (
        .clk(core_clk), .rst_n(rst_n),
        .m_awid({bridge_awid, camera_awid}), .m_awaddr({bridge_awaddr, camera_awaddr}),
        .m_awlen({bridge_awlen, camera_awlen}), .m_awsize({bridge_awsize, camera_awsize}),
        .m_awburst({bridge_awburst, camera_awburst}), .m_awlock({bridge_awlock, camera_awlock}),
        .m_awcache({bridge_awcache, camera_awcache}), .m_awprot({bridge_awprot, camera_awprot}),
        .m_awqos({bridge_awqos, camera_awqos}), .m_awregion({bridge_awregion, camera_awregion}),
        .m_awvalid({bridge_awvalid, camera_awvalid}), .m_awready(all_awready),
        .m_wdata({bridge_wdata, camera_wdata}), .m_wstrb({bridge_wstrb, camera_wstrb}),
        .m_wlast({bridge_wlast, camera_wlast}), .m_wvalid({bridge_wvalid, camera_wvalid}),
        .m_wready(all_wready), .m_bid(all_bid), .m_bresp(all_bresp), .m_bvalid(all_bvalid),
        .m_bready({bridge_bready, camera_bready}),
        .s_awid(m_axi_write_awid), .s_awaddr(m_axi_write_awaddr),
        .s_awlen(m_axi_write_awlen), .s_awsize(m_axi_write_awsize),
        .s_awburst(m_axi_write_awburst), .s_awlock(m_axi_write_awlock),
        .s_awcache(m_axi_write_awcache), .s_awprot(m_axi_write_awprot),
        .s_awqos(m_axi_write_awqos), .s_awregion(m_axi_write_awregion),
        .s_awvalid(m_axi_write_awvalid), .s_awready(m_axi_write_awready),
        .s_wdata(m_axi_write_wdata), .s_wstrb(m_axi_write_wstrb),
        .s_wlast(m_axi_write_wlast), .s_wvalid(m_axi_write_wvalid), .s_wready(m_axi_write_wready),
        .s_bid(m_axi_write_bid), .s_bresp(m_axi_write_bresp),
        .s_bvalid(m_axi_write_bvalid), .s_bready(m_axi_write_bready),
        .busy(arbiter_busy), .owner(arbiter_owner), .error(arbiter_error),
        .error_flags(arbiter_error_flags)
    );
endmodule
