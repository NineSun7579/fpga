//============================================================================
// ovreg_axil_decode.v : AXI-Lite 2-way address decoder for the M01 window
//   (0x2000_0000, reached via axi_to_axi_lite from crossbar M01)
//
//   addr[8] = 0 : ov5640_reg segment  (0x2000_0000 ~ 0x2000_00FF)
//   addr[8] = 1 : prep_regs segment   (0x2000_0100 ~ 0x2000_01FF, doc uses
//                                      +0x100 ~ +0x17C)
//
//   AW/W and AR are steered by the address captured at handshake; B/R are
//   routed back by the same captured bit. Single-outstanding per channel
//   (AXI-Lite semantics).
//============================================================================
module ovreg_axil_decode #(
    parameter ADDR_SEL_BIT = 8          // which addr bit selects the slave
)(
    input          clk,
    input          rst,                 // active high, synchronous to axi_clk

    // upstream (from axi_to_axi_lite, M01)
    input          s_awvalid,
    output         s_awready,
    input  [31:0]  s_awaddr,
    input          s_wvalid,
    output         s_wready,
    input  [31:0]  s_wdata,
    input  [3:0]   s_wstrb,
    output         s_bvalid,
    input          s_bready,
    output  [1:0]  s_bresp,
    input          s_arvalid,
    output         s_arready,
    input  [31:0]  s_araddr,
    output         s_rvalid,
    input          s_rready,
    output  [31:0] s_rdata,
    output  [1:0]  s_rresp,

    // downstream slave 0 : ov5640_reg segment
    output         m0_awvalid,
    input          m0_awready,
    output [31:0]  m0_awaddr,
    output         m0_wvalid,
    input          m0_wready,
    output [31:0]  m0_wdata,
    output [3:0]   m0_wstrb,
    input          m0_bvalid,
    output         m0_bready,
    input   [1:0]  m0_bresp,
    output         m0_arvalid,
    input          m0_arready,
    output [31:0]  m0_araddr,
    input          m0_rvalid,
    output         m0_rready,
    input  [31:0]  m0_rdata,
    input   [1:0]  m0_rresp,

    // downstream slave 1 : prep_regs segment
    output         m1_awvalid,
    input          m1_awready,
    output [31:0]  m1_awaddr,
    output         m1_wvalid,
    input          m1_wready,
    output [31:0]  m1_wdata,
    output [3:0]   m1_wstrb,
    input          m1_bvalid,
    output         m1_bready,
    input   [1:0]  m1_bresp,
    output         m1_arvalid,
    input          m1_arready,
    output [31:0]  m1_araddr,
    input          m1_rvalid,
    output         m1_rready,
    input  [31:0]  m1_rdata,
    input   [1:0]  m1_rresp
);

    // AW address select bit, captured at handshake
    reg aw_sel;
    always @(posedge clk) begin
        if (rst)
            aw_sel <= 1'b0;
        else if (s_awvalid && s_awready)
            aw_sel <= s_awaddr[ADDR_SEL_BIT];
    end

    // AR address select bit, captured at handshake
    reg ar_sel;
    always @(posedge clk) begin
        if (rst)
            ar_sel <= 1'b0;
        else if (s_arvalid && s_arready)
            ar_sel <= s_araddr[ADDR_SEL_BIT];
    end

    // steering bit for the current AW/W pair (valid from AW handshake until W
    // completes); falls back to the live address while AW is pending
    wire aw_sel_live = s_awvalid ? s_awaddr[ADDR_SEL_BIT] : aw_sel;
    // same for the AR channel
    wire ar_sel_live = s_arvalid ? s_araddr[ADDR_SEL_BIT] : ar_sel;

    //----------------------------------------
    // AW channel
    //----------------------------------------
    assign m0_awvalid = s_awvalid & ~aw_sel_live;
    assign m1_awvalid = s_awvalid &  aw_sel_live;
    assign s_awready  = aw_sel_live ? m1_awready : m0_awready;
    assign m0_awaddr  = s_awaddr;
    assign m1_awaddr  = s_awaddr;

    //----------------------------------------
    // W channel : follow the AW steering (single outstanding AXI-Lite write)
    //----------------------------------------
    assign m0_wvalid = s_wvalid & ~aw_sel_live;
    assign m1_wvalid = s_wvalid &  aw_sel_live;
    assign s_wready  = aw_sel_live ? m1_wready : m0_wready;
    assign m0_wdata  = s_wdata;
    assign m1_wdata  = s_wdata;
    assign m0_wstrb  = s_wstrb;
    assign m1_wstrb  = s_wstrb;

    //----------------------------------------
    // B channel : route by the AW select captured for this write
    //----------------------------------------
    assign m0_bready = s_bready & ~aw_sel;
    assign m1_bready = s_bready &  aw_sel;
    assign s_bvalid  = aw_sel ? m1_bvalid : m0_bvalid;
    assign s_bresp   = aw_sel ? m1_bresp  : m0_bresp;

    //----------------------------------------
    // AR channel
    //----------------------------------------
    assign m0_arvalid = s_arvalid & ~ar_sel_live;
    assign m1_arvalid = s_arvalid &  ar_sel_live;
    assign s_arready  = ar_sel_live ? m1_arready : m0_arready;
    assign m0_araddr  = s_araddr;
    assign m1_araddr  = s_araddr;

    //----------------------------------------
    // R channel : route by the AR select captured for this read
    //----------------------------------------
    assign m0_rready = s_rready & ~ar_sel;
    assign m1_rready = s_rready &  ar_sel;
    assign s_rvalid  = ar_sel ? m1_rvalid : m0_rvalid;
    assign s_rdata   = ar_sel ? m1_rdata  : m0_rdata;
    assign s_rresp   = ar_sel ? m1_rresp  : m0_rresp;

endmodule
