//============================================================================
// ovreg_axil_decode.v : AXI-Lite 5-way address decoder for the M01 window
//   (0x2000_0000, reached via axi_to_axi_lite from crossbar M01)
//
//   addr[11:10]=00, addr[9:8]=00 : ov5640_reg  (0x2000_0000~0x00FF)  CAM1
//   addr[11:10]=00, addr[9:8]=01 : prep_regs   (0x2000_0100~0x01FF, doc
//                                              +0x100 ~ +0x17C)
//   addr[11:10]=00, addr[9:8]=10 : ov5640_reg  (0x2000_0200~0x02FF)  CAM2
//   addr[11:10]=00, addr[9:8]=11 : prep_regs (default, legacy addr[8]=1)
//   addr[11:10]=01, addr[9]=0    : ov5640_reg  (0x2000_0400~0x05FF)  CAM3
//   addr[11:10]=01, addr[9]=1    : ov5640_reg  (0x2000_0600~0x07FF)  CAM4
//     (CAM3/CAM4 windows are 0x200 each: main regs +0x000 and SCCB +0x100)
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
    input   [1:0]  m2_rresp,

    // downstream slave 3 : ov5640_reg segment (CAM3, 0x2000_0400~0x04FF)
    //   selected by addr[ADDR_SEL_LSB+3 : ADDR_SEL_LSB+2] == 01
    output         m3_awvalid,
    input          m3_awready,
    output [31:0]  m3_awaddr,
    output         m3_wvalid,
    input          m3_wready,
    output [31:0]  m3_wdata,
    output [3:0]   m3_wstrb,
    input          m3_bvalid,
    output         m3_bready,
    input   [1:0]  m3_bresp,
    output         m3_arvalid,
    input          m3_arready,
    output [31:0]  m3_araddr,
    input          m3_rvalid,
    output         m3_rready,
    input  [31:0]  m3_rdata,
    input   [1:0]  m3_rresp,

    // downstream slave 4 : ov5640_reg segment (CAM4, 0x2000_0600~0x07FF)
    //   selected by addr[11:10]==01 and addr[9]==1 (0x600 main + 0x700 SCCB)
    output         m4_awvalid,
    input          m4_awready,
    output [31:0]  m4_awaddr,
    output         m4_wvalid,
    input          m4_wready,
    output [31:0]  m4_wdata,
    output [3:0]   m4_wstrb,
    input          m4_bvalid,
    output         m4_bready,
    input   [1:0]  m4_bresp,
    output         m4_arvalid,
    input          m4_arready,
    output [31:0]  m4_araddr,
    input          m4_rvalid,
    output         m4_rready,
    input  [31:0]  m4_rdata,
    input   [1:0]  m4_rresp
);

    // address select, captured at handshake
    // [CAM3] 4-bit: {addr[ADDR_SEL_LSB+3:LSB+2] (page, CAM3 when 01),
    //                addr[ADDR_SEL_LSB+1:LSB]   (segment within page)}
    function [3:0] runtime_route(input [31:0] addr);
        begin
            // Explicit full-address aliases: no low-page accidental collision.
            if(addr[31:8] == 24'h20000b) runtime_route = 4'h1;
            else if(addr[31:8] == 24'h20000c) runtime_route = 4'h0;
            else if(addr[31:8] == 24'h20000d) runtime_route = 4'h4;
            else if(addr[31:8] == 24'h20000e) runtime_route = 4'h6;
            else if(addr[31:8] == 24'h200009) runtime_route = 4'h4;
            else if(addr[31:8] == 24'h20000a) runtime_route = 4'h6;
            else runtime_route = addr[ADDR_SEL_LSB+3 : ADDR_SEL_LSB];
        end
    endfunction
    reg [3:0] aw_sel;
    always @(posedge clk) begin
        if (rst)
            aw_sel <= 4'b0000;
        else if (s_awvalid && s_awready)
            aw_sel <= runtime_route(s_awaddr);
    end

    // CDC host diagnostics: four unused, 16-byte aligned reads per 0x200 stride.
    // Route by the 3-bit camera index addr[11:9] (cam1=000, cam2=001,
    // cam3=010, cam4=011); sel code = {index, 1'b0}.
    wire cdc_read = (s_araddr[31:11] == (32'h20000000 >> 11)) &&
                   (s_araddr[11:9] < 4) &&
                   ((s_araddr[8:0] == 9'h190) || (s_araddr[8:0] == 9'h1a0) ||
                    (s_araddr[8:0] == 9'h1b0) || (s_araddr[8:0] == 9'h1c0));
    wire [3:0] ar_route = cdc_read ? {s_araddr[11:9], 1'b0} :
                         runtime_route(s_araddr);
    reg [3:0] ar_sel;
    always @(posedge clk) begin
        if (rst)
            ar_sel <= 4'b0000;
        else if (s_arvalid && s_arready)
            ar_sel <= ar_route;
    end

    // steering value for the current AW/W pair; falls back to the live address
    // while AW is pending
    wire [3:0] aw_sel_live = s_awvalid ? runtime_route(s_awaddr) : aw_sel;
    wire [3:0] ar_sel_live = s_arvalid ? ar_route : ar_sel;

    wire aw_page3 = (aw_sel_live[3:2] == 2'b01);   // CAM3/CAM4 page (0x2000_0400+)
    wire ar_page3 = (ar_sel_live[3:2] == 2'b01);

    // per-slave select strobes. Within the camera page addr[9] (= sel[1] here)
    // splits CAM3 (0x400 main / 0x500 SCCB) from CAM4 (0x600 main / 0x700 SCCB);
    // sel==11 within page 0 falls back to m1 = legacy prep routing.
    wire aw_m4 = aw_page3 &  aw_sel_live[1];
    wire aw_m3 = aw_page3 & ~aw_sel_live[1];
    wire aw_m0 = ~aw_page3 & (aw_sel_live[1:0] == 2'b00);
    wire aw_m2 = ~aw_page3 & (aw_sel_live[1:0] == 2'b10);
    wire aw_m1 = ~aw_page3 & ~aw_m0 & ~aw_m2;
    wire ar_m4 = ar_page3 &  ar_sel_live[1];
    wire ar_m3 = ar_page3 & ~ar_sel_live[1];
    wire ar_m0 = ~ar_page3 & (ar_sel_live[1:0] == 2'b00);
    wire ar_m2 = ~ar_page3 & (ar_sel_live[1:0] == 2'b10);
    wire ar_m1 = ~ar_page3 & ~ar_m0 & ~ar_m2;

    wire b_m4 = (aw_sel[3:2] == 2'b01) &  aw_sel[1];
    wire b_m3 = (aw_sel[3:2] == 2'b01) & ~aw_sel[1];
    wire b_m0 = (aw_sel[3:2] != 2'b01) & (aw_sel[1:0] == 2'b00);
    wire b_m2 = (aw_sel[3:2] != 2'b01) & (aw_sel[1:0] == 2'b10);
    wire b_m1 = (aw_sel[3:2] != 2'b01) & ~b_m0 & ~b_m2;
    wire r_m4 = (ar_sel[3:2] == 2'b01) &  ar_sel[1];
    wire r_m3 = (ar_sel[3:2] == 2'b01) & ~ar_sel[1];
    wire r_m0 = (ar_sel[3:2] != 2'b01) & (ar_sel[1:0] == 2'b00);
    wire r_m2 = (ar_sel[3:2] != 2'b01) & (ar_sel[1:0] == 2'b10);
    wire r_m1 = (ar_sel[3:2] != 2'b01) & ~r_m0 & ~r_m2;

    //----------------------------------------
    // AW channel
    //----------------------------------------
    assign m0_awvalid = s_awvalid & aw_m0;
    assign m1_awvalid = s_awvalid & aw_m1;
    assign m2_awvalid = s_awvalid & aw_m2;
    assign m3_awvalid = s_awvalid & aw_m3;
    assign m4_awvalid = s_awvalid & aw_m4;
    assign s_awready  = aw_m4 ? m4_awready : aw_m3 ? m3_awready :
                        aw_m0 ? m0_awready : (aw_m2 ? m2_awready : m1_awready);
    assign m0_awaddr  = s_awaddr;
    assign m1_awaddr  = s_awaddr;
    assign m2_awaddr  = s_awaddr;
    assign m3_awaddr  = s_awaddr;
    assign m4_awaddr  = s_awaddr;

    //----------------------------------------
    // W channel : follow the AW steering (single outstanding AXI-Lite write)
    //----------------------------------------
    assign m0_wvalid = s_wvalid & aw_m0;
    assign m1_wvalid = s_wvalid & aw_m1;
    assign m2_wvalid = s_wvalid & aw_m2;
    assign m3_wvalid = s_wvalid & aw_m3;
    assign m4_wvalid = s_wvalid & aw_m4;
    assign s_wready  = aw_m4 ? m4_wready : aw_m3 ? m3_wready :
                       aw_m0 ? m0_wready : (aw_m2 ? m2_wready : m1_wready);
    assign m0_wdata  = s_wdata;
    assign m1_wdata  = s_wdata;
    assign m2_wdata  = s_wdata;
    assign m3_wdata  = s_wdata;
    assign m4_wdata  = s_wdata;
    assign m0_wstrb  = s_wstrb;
    assign m1_wstrb  = s_wstrb;
    assign m2_wstrb  = s_wstrb;
    assign m3_wstrb  = s_wstrb;
    assign m4_wstrb  = s_wstrb;

    //----------------------------------------
    // B channel : route by the AW select captured for this write
    //----------------------------------------
    assign m0_bready = s_bready & b_m0;
    assign m1_bready = s_bready & b_m1;
    assign m2_bready = s_bready & b_m2;
    assign m3_bready = s_bready & b_m3;
    assign m4_bready = s_bready & b_m4;
    assign s_bvalid  = b_m4 ? m4_bvalid : b_m3 ? m3_bvalid :
                       b_m0 ? m0_bvalid : (b_m2 ? m2_bvalid : m1_bvalid);
    assign s_bresp   = b_m4 ? m4_bresp  : b_m3 ? m3_bresp  :
                       b_m0 ? m0_bresp  : (b_m2 ? m2_bresp  : m1_bresp);

    //----------------------------------------
    // AR channel
    //----------------------------------------
    assign m0_arvalid = s_arvalid & ar_m0;
    assign m1_arvalid = s_arvalid & ar_m1;
    assign m2_arvalid = s_arvalid & ar_m2;
    assign m3_arvalid = s_arvalid & ar_m3;
    assign m4_arvalid = s_arvalid & ar_m4;
    assign s_arready  = ar_m4 ? m4_arready : ar_m3 ? m3_arready :
                        ar_m0 ? m0_arready : (ar_m2 ? m2_arready : m1_arready);
    assign m0_araddr  = s_araddr;
    assign m1_araddr  = s_araddr;
    assign m2_araddr  = s_araddr;
    assign m3_araddr  = s_araddr;
    assign m4_araddr  = s_araddr;

    //----------------------------------------
    // R channel : route by the AR select captured for this read
    //----------------------------------------
    assign m0_rready = s_rready & r_m0;
    assign m1_rready = s_rready & r_m1;
    assign m2_rready = s_rready & r_m2;
    assign m3_rready = s_rready & r_m3;
    assign m4_rready = s_rready & r_m4;
    assign s_rvalid  = r_m4 ? m4_rvalid : r_m3 ? m3_rvalid :
                       r_m0 ? m0_rvalid : (r_m2 ? m2_rvalid : m1_rvalid);
    assign s_rdata   = r_m4 ? m4_rdata  : r_m3 ? m3_rdata  :
                       r_m0 ? m0_rdata  : (r_m2 ? m2_rdata  : m1_rdata);
    assign s_rresp   = r_m4 ? m4_rresp  : r_m3 ? m3_rresp  :
                       r_m0 ? m0_rresp  : (r_m2 ? m2_rresp  : m1_rresp);

endmodule
