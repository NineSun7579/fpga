//============================================================================
// ovreg_axil_decode.v : AXI-Lite 3-way address decoder for the M01 window
//   (0x2000_0000, reached via axi_to_axi_lite from crossbar M01)
//
//   addr[9:8] = 00 : ov5640_reg segment  (0x2000_0000 ~ 0x2000_00FF)  CAM1
//   addr[9:8] = 01 : prep_regs segment   (0x2000_0100 ~ 0x2000_01FF, doc uses
//                                       +0x100 ~ +0x17C)
//   addr[9:8] = 10 : ov5640_reg segment  (0x2000_0200 ~ 0x2000_02FF)  CAM2
//   addr[9:8] = 11 : prep_regs (default, preserves legacy addr[8]=1 routing)
//
//   AW/W and AR are steered by the address captured at handshake; B/R are
//   routed back by the same captured value. Single-outstanding per channel
//   (AXI-Lite semantics).
//============================================================================
module ovreg_axil_decode #(
    parameter ADDR_SEL_LSB = 8          // addr[LSB+1:LSB] selects the slave
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

    // downstream slave 0 : ov5640_reg segment (CAM1)
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
    input   [1:0]  m1_rresp,

    // downstream slave 2 : ov5640_reg segment (CAM2, 0x2000_0200~0x02FF)
    output         m2_awvalid,
    input          m2_awready,
    output [31:0]  m2_awaddr,
    output         m2_wvalid,
    input          m2_wready,
    output [31:0]  m2_wdata,
    output [3:0]   m2_wstrb,
    input          m2_bvalid,
    output         m2_bready,
    input   [1:0]  m2_bresp,
    output         m2_arvalid,
    input          m2_arready,
    output [31:0]  m2_araddr,
    input          m2_rvalid,
    output         m2_rready,
    input  [31:0]  m2_rdata,
    input   [1:0]  m2_rresp
);

    // address select, captured at handshake
    reg [1:0] aw_sel;
    always @(posedge clk) begin
        if (rst)
            aw_sel <= 2'b00;
        else if (s_awvalid && s_awready)
            aw_sel <= s_awaddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB];
    end

    reg [1:0] ar_sel;
    always @(posedge clk) begin
        if (rst)
            ar_sel <= 2'b00;
        else if (s_arvalid && s_arready)
            ar_sel <= s_araddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB];
    end

    // steering value for the current AW/W pair; falls back to the live address
    // while AW is pending
    wire [1:0] aw_sel_live = s_awvalid ? s_awaddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB] : aw_sel;
    wire [1:0] ar_sel_live = s_arvalid ? s_araddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB] : ar_sel;

    // per-slave select strobes (sel==11 falls back to m1 = legacy prep routing)
    wire aw_m0 = (aw_sel_live == 2'b00);
    wire aw_m2 = (aw_sel_live == 2'b10);
    wire aw_m1 = ~aw_m0 & ~aw_m2;
    wire ar_m0 = (ar_sel_live == 2'b00);
    wire ar_m2 = (ar_sel_live == 2'b10);
    wire ar_m1 = ~ar_m0 & ~ar_m2;

    wire b_m0 = (aw_sel == 2'b00);
    wire b_m2 = (aw_sel == 2'b10);
    wire b_m1 = ~b_m0 & ~b_m2;
    wire r_m0 = (ar_sel == 2'b00);
    wire r_m2 = (ar_sel == 2'b10);
    wire r_m1 = ~r_m0 & ~r_m2;

    //----------------------------------------
    // AW channel
    //----------------------------------------
    assign m0_awvalid = s_awvalid & aw_m0;
    assign m1_awvalid = s_awvalid & aw_m1;
    assign m2_awvalid = s_awvalid & aw_m2;
    assign s_awready  = aw_m0 ? m0_awready : (aw_m2 ? m2_awready : m1_awready);
    assign m0_awaddr  = s_awaddr;
    assign m1_awaddr  = s_awaddr;
    assign m2_awaddr  = s_awaddr;

    //----------------------------------------
    // W channel : follow the AW steering (single outstanding AXI-Lite write)
    //----------------------------------------
    assign m0_wvalid = s_wvalid & aw_m0;
    assign m1_wvalid = s_wvalid & aw_m1;
    assign m2_wvalid = s_wvalid & aw_m2;
    assign s_wready  = aw_m0 ? m0_wready : (aw_m2 ? m2_wready : m1_wready);
    assign m0_wdata  = s_wdata;
    assign m1_wdata  = s_wdata;
    assign m2_wdata  = s_wdata;
    assign m0_wstrb  = s_wstrb;
    assign m1_wstrb  = s_wstrb;
    assign m2_wstrb  = s_wstrb;

    //----------------------------------------
    // B channel : route by the AW select captured for this write
    //----------------------------------------
    assign m0_bready = s_bready & b_m0;
    assign m1_bready = s_bready & b_m1;
    assign m2_bready = s_bready & b_m2;
    assign s_bvalid  = b_m0 ? m0_bvalid : (b_m2 ? m2_bvalid : m1_bvalid);
    assign s_bresp   = b_m0 ? m0_bresp  : (b_m2 ? m2_bresp  : m1_bresp);

    //----------------------------------------
    // AR channel
    //----------------------------------------
    assign m0_arvalid = s_arvalid & ar_m0;
    assign m1_arvalid = s_arvalid & ar_m1;
    assign m2_arvalid = s_arvalid & ar_m2;
    assign s_arready  = ar_m0 ? m0_arready : (ar_m2 ? m2_arready : m1_arready);
    assign m0_araddr  = s_araddr;
    assign m1_araddr  = s_araddr;
    assign m2_araddr  = s_araddr;

    //----------------------------------------
    // R channel : route by the AR select captured for this read
    //----------------------------------------
    assign m0_rready = s_rready & r_m0;
    assign m1_rready = s_rready & r_m1;
    assign m2_rready = s_rready & r_m2;
    assign s_rvalid  = r_m0 ? m0_rvalid : (r_m2 ? m2_rvalid : m1_rvalid);
    assign s_rdata   = r_m0 ? m0_rdata  : (r_m2 ? m2_rdata  : m1_rdata);
    assign s_rresp   = r_m0 ? m0_rresp  : (r_m2 ? m2_rresp  : m1_rresp);

endmodule
