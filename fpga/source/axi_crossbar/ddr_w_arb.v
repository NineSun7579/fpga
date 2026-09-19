// ============================================================================
// ddr_w_arb.v -- [WARB 2026-09-19] minimal 2-master DDR write arbiter.
//
// WHY: the Forencich axi_crossbar's M00 write path leaks its per-master W-channel
// select across handoffs (bench-proven in sim/wedge: after S01's burst tail the
// M00 w_select_valid latches forever, S04's beats are never released, and both
// camera engines wedge after 1-2 bursts). This module replaces the crossbar on
// the DDR write path for the two camera engines.
//
// DESIGN: single-outstanding end-to-end, matching the DDR3 IP user-port contract
// (no wvalid, unthrottleable wready, one burst processed at a time):
//   IDLE  : present one master's AW (round-robin tie-break); the accept from the
//           port glue locks OWNER for the whole burst.
//   BUSY  : only OWNER's W stream reaches the glue; the fabric-minted B (from
//           wusero_last) is routed back to OWNER; its accept frees the slot and
//           flips the round-robin bit.
// AXI-legal: awvalid/wvalid are held with stable payload until accepted; the
// non-owner master's awready/wready stay low, so its burst cannot start.
// ============================================================================
`timescale 1ns/1ps
module ddr_w_arb (
    input  wire         clk,
    input  wire         rst,

    // ---- master 0 (cam1 DMA) ----
    input  wire [3:0]   m0_awid,
    input  wire [31:0]  m0_awaddr,
    input  wire [7:0]   m0_awlen,
    input  wire [2:0]   m0_awsize,
    input  wire [1:0]   m0_awburst,
    input  wire         m0_awlock,
    input  wire [3:0]   m0_awcache,
    input  wire [2:0]   m0_awprot,
    input  wire         m0_awvalid,
    output wire         m0_awready,
    input  wire [127:0] m0_wdata,
    input  wire [15:0]  m0_wstrb,
    input  wire         m0_wlast,
    input  wire         m0_wvalid,
    output wire         m0_wready,
    output wire [3:0]   m0_bid,
    output wire [1:0]   m0_bresp,
    output wire         m0_bvalid,
    input  wire         m0_bready,

    // ---- master 1 (cam2 DMA) ----
    input  wire [3:0]   m1_awid,
    input  wire [31:0]  m1_awaddr,
    input  wire [7:0]   m1_awlen,
    input  wire [2:0]   m1_awsize,
    input  wire [1:0]   m1_awburst,
    input  wire         m1_awlock,
    input  wire [3:0]   m1_awcache,
    input  wire [2:0]   m1_awprot,
    input  wire         m1_awvalid,
    output wire         m1_awready,
    input  wire [127:0] m1_wdata,
    input  wire [15:0]  m1_wstrb,
    input  wire         m1_wlast,
    input  wire         m1_wvalid,
    output wire         m1_wready,
    output wire [3:0]   m1_bid,
    output wire [1:0]   m1_bresp,
    output wire         m1_bvalid,
    input  wire         m1_bready,

    // ---- slave (DDR3 port glue) ----
    output wire [3:0]   s_awid,
    output wire [31:0]  s_awaddr,
    output wire [7:0]   s_awlen,
    output wire [2:0]   s_awsize,
    output wire [1:0]   s_awburst,
    output wire         s_awlock,
    output wire [3:0]   s_awcache,
    output wire [2:0]   s_awprot,
    output wire         s_awvalid,
    input  wire         s_awready,
    output wire [127:0] s_wdata,
    output wire [15:0]  s_wstrb,
    output wire         s_wlast,
    output wire         s_wvalid,
    input  wire         s_wready,
    input  wire [3:0]   s_bid,
    input  wire [1:0]   s_bresp,
    input  wire         s_bvalid,
    output wire         s_bready
);

    reg  busy;      // an AW is locked in (waiting for its B)
    reg  owner;     // 0 = master0 owns the slot, 1 = master1
    reg  rr;        // round-robin tie-break for the next idle grant

    // grant decision: only when idle; alternate when both masters ask
    wire aw_gnt_m1 = ~busy & m1_awvalid & ( rr | ~m0_awvalid);
    wire aw_gnt_m0 = ~busy & m0_awvalid & ~(m1_awvalid & rr);

    // AW datapath (granted master's request)
    assign s_awid    = aw_gnt_m1 ? m1_awid    : m0_awid;
    assign s_awaddr  = aw_gnt_m1 ? m1_awaddr  : m0_awaddr;
    assign s_awlen   = aw_gnt_m1 ? m1_awlen   : m0_awlen;
    assign s_awsize  = aw_gnt_m1 ? m1_awsize  : m0_awsize;
    assign s_awburst = aw_gnt_m1 ? m1_awburst : m0_awburst;
    assign s_awlock  = aw_gnt_m1 ? m1_awlock  : m0_awlock;
    assign s_awcache = aw_gnt_m1 ? m1_awcache : m0_awcache;
    assign s_awprot  = aw_gnt_m1 ? m1_awprot  : m0_awprot;
    assign s_awvalid = aw_gnt_m0 | aw_gnt_m1;

    assign m0_awready = aw_gnt_m0 & s_awready;
    assign m1_awready = aw_gnt_m1 & s_awready;

    // W datapath (only the owner's beats can flow)
    assign s_wdata  = owner ? m1_wdata : m0_wdata;
    assign s_wstrb  = owner ? m1_wstrb : m0_wstrb;
    assign s_wlast  = owner ? m1_wlast : m0_wlast;
    assign s_wvalid = busy & (owner ? m1_wvalid : m0_wvalid);

    assign m0_wready = busy & ~owner & s_wready;
    assign m1_wready = busy &  owner & s_wready;

    // B path: single outstanding -> the owner gets the fabric-minted response
    assign m0_bvalid = busy & ~owner & s_bvalid;
    assign m1_bvalid = busy &  owner & s_bvalid;
    assign m0_bid    = s_bid;
    assign m1_bid    = s_bid;
    assign m0_bresp  = s_bresp;
    assign m1_bresp  = s_bresp;
    assign s_bready  = busy & (owner ? m1_bready : m0_bready);

    always @(posedge clk) begin
        if (rst) begin
            busy  <= 1'b0;
            owner <= 1'b0;
            rr    <= 1'b0;
        end
        else begin
            if (!busy && (aw_gnt_m0 | aw_gnt_m1) && s_awready) begin
                busy  <= 1'b1;
                owner <= aw_gnt_m1;
                rr    <= aw_gnt_m0;         // next idle grant favors the other master
            end
            else if (busy && s_bvalid && s_bready) begin
                busy  <= 1'b0;
            end
        end
    end

endmodule
