// ============================================================================
// ddr_w_arb.v -- [WARB 2026-09-19] minimal 2-master DDR write arbiter.
// [CAM3 2026-09-26] extended to 3 masters (cam3 engine joins as master 2).
//
// WHY: the Forencich axi_crossbar's M00 write path leaks its per-master W-channel
// select across handoffs (bench-proven in sim/wedge: after S01's burst tail the
// M00 w_select_valid latches forever, S04's beats are never released, and both
// camera engines wedge after 1-2 bursts). This module replaces the crossbar on
// the DDR write path for the camera engines.
//
// DESIGN: single-outstanding end-to-end, matching the DDR3 IP user-port contract
// (no wvalid, unthrottleable wready, one burst processed at a time):
//   IDLE  : present one master's AW (round-robin tie-break); the accept from the
//           port glue locks OWNER for the whole burst.
//   BUSY  : only OWNER's W stream reaches the glue; the fabric-minted B (from
//           wusero_last) is routed back to OWNER; its accept frees the slot and
//           advances the round-robin.
// AXI-legal: awvalid/wvalid are held with stable payload until accepted; the
// non-owner masters' awready/wready stay low, so their bursts cannot start.
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

    // ---- master 2 (cam3 DMA) ----
    input  wire [3:0]   m2_awid,
    input  wire [31:0]  m2_awaddr,
    input  wire [7:0]   m2_awlen,
    input  wire [2:0]   m2_awsize,
    input  wire [1:0]   m2_awburst,
    input  wire         m2_awlock,
    input  wire [3:0]   m2_awcache,
    input  wire [2:0]   m2_awprot,
    input  wire         m2_awvalid,
    output wire         m2_awready,
    input  wire [127:0] m2_wdata,
    input  wire [15:0]  m2_wstrb,
    input  wire         m2_wlast,
    input  wire         m2_wvalid,
    output wire         m2_wready,
    output wire [3:0]   m2_bid,
    output wire [1:0]   m2_bresp,
    output wire         m2_bvalid,
    input  wire         m2_bready,

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

    reg        busy;    // an AW is locked in (waiting for its B)
    reg  [1:0] owner;    // which master owns the slot (0/1/2)
    reg  [1:0] rr;       // round-robin preference for the next idle grant

    // [WARBFIX 2026-09-26] AW selection is latched. The previous version drove
    // the slave AW payload from purely combinational grants, so when a higher
    // priority master asserted AWVALID during downstream AWREADY backpressure,
    // the shared AWVALID stayed high while AWADDR/AWID changed mid-handshake.
    // The slave (DDR3 IP) could then latch a torn/wrong descriptor, dropping or
    // misrouting an integer number of beats -> cam2 frame rotation, cam3 tearing.
    // Now the winner is frozen (sel/sel_valid) until AWREADY accepts it, so the
    // payload is stable for the whole handshake (AXI4 1.2.3).
    reg        sel_valid;
    reg  [1:0] sel;

    // grant decision: only when idle; round-robin among the requesting masters.
    // rr points at the master that gets the slot when several request at once.
    wire req0 = m0_awvalid, req1 = m1_awvalid, req2 = m2_awvalid;

    // one-shot round-robin pick, used only to seed the latched selection
    wire pick0 = req0 & ((rr == 2'd0) | (rr == 2'd1 & ~req1 & ~req2) | (rr == 2'd2 & ~req2));
    wire pick1 = req1 & ((rr == 2'd1) | (rr == 2'd2 & ~req2 & ~req0) | (rr == 2'd0 & ~req0));
    wire pick2 = req2 & ((rr == 2'd2) | (rr == 2'd0 & ~req0 & ~req1) | (rr == 2'd1 & ~req1));
    wire pick_v = pick0 | pick1 | pick2;
    wire [1:0] pick_sel = pick2 ? 2'd2 : pick1 ? 2'd1 : 2'd0;

    // effective selection: the latched winner if any, else the fresh pick
    wire eff_valid = ~busy & (sel_valid | pick_v);
    wire [1:0] eff_sel = sel_valid ? sel : pick_sel;

    // AW datapath (latched winner's request)
    assign s_awid    = eff_sel == 2'd2 ? m2_awid    : eff_sel == 2'd1 ? m1_awid    : m0_awid;
    assign s_awaddr  = eff_sel == 2'd2 ? m2_awaddr  : eff_sel == 2'd1 ? m1_awaddr  : m0_awaddr;
    assign s_awlen   = eff_sel == 2'd2 ? m2_awlen   : eff_sel == 2'd1 ? m1_awlen   : m0_awlen;
    assign s_awsize  = eff_sel == 2'd2 ? m2_awsize  : eff_sel == 2'd1 ? m1_awsize  : m0_awsize;
    assign s_awburst = eff_sel == 2'd2 ? m2_awburst : eff_sel == 2'd1 ? m1_awburst : m0_awburst;
    assign s_awlock  = eff_sel == 2'd2 ? m2_awlock  : eff_sel == 2'd1 ? m1_awlock  : m0_awlock;
    assign s_awcache = eff_sel == 2'd2 ? m2_awcache : eff_sel == 2'd1 ? m1_awcache : m0_awcache;
    assign s_awprot  = eff_sel == 2'd2 ? m2_awprot  : eff_sel == 2'd1 ? m1_awprot  : m0_awprot;
    assign s_awvalid = eff_valid;

    assign m0_awready = eff_valid & (eff_sel == 2'd0) & s_awready;
    assign m1_awready = eff_valid & (eff_sel == 2'd1) & s_awready;
    assign m2_awready = eff_valid & (eff_sel == 2'd2) & s_awready;

    // W datapath (only the owner's beats can flow)
    assign s_wdata  = owner == 2'd2 ? m2_wdata : owner == 2'd1 ? m1_wdata : m0_wdata;
    assign s_wstrb  = owner == 2'd2 ? m2_wstrb : owner == 2'd1 ? m1_wstrb : m0_wstrb;
    assign s_wlast  = owner == 2'd2 ? m2_wlast : owner == 2'd1 ? m1_wlast : m0_wlast;
    assign s_wvalid = busy & (owner == 2'd2 ? m2_wvalid : owner == 2'd1 ? m1_wvalid : m0_wvalid);

    assign m0_wready = busy & (owner == 2'd0) & s_wready;
    assign m1_wready = busy & (owner == 2'd1) & s_wready;
    assign m2_wready = busy & (owner == 2'd2) & s_wready;

    // B path: single outstanding -> the owner gets the fabric-minted response
    assign m0_bvalid = busy & (owner == 2'd0) & s_bvalid;
    assign m1_bvalid = busy & (owner == 2'd1) & s_bvalid;
    assign m2_bvalid = busy & (owner == 2'd2) & s_bvalid;
    assign m0_bid    = s_bid;
    assign m1_bid    = s_bid;
    assign m2_bid    = s_bid;
    assign m0_bresp  = s_bresp;
    assign m1_bresp  = s_bresp;
    assign m2_bresp  = s_bresp;
    assign s_bready  = busy & (owner == 2'd2 ? m2_bready : owner == 2'd1 ? m1_bready : m0_bready);

    always @(posedge clk) begin
        if (rst) begin
            busy      <= 1'b0;
            owner     <= 2'd0;
            rr        <= 2'd0;
            sel_valid <= 1'b0;
            sel       <= 2'd0;
        end
        else begin
            if (!busy && eff_valid && s_awready) begin
                // lock the slot to the accepted master; next idle grant favors
                // the following master in round-robin order
                busy      <= 1'b1;
                owner     <= eff_sel;
                rr        <= (eff_sel == 2'd2) ? 2'd0 : (eff_sel == 2'd1) ? 2'd2 : 2'd1;
                sel_valid <= 1'b0;
            end
            else if (!busy && !sel_valid && pick_v) begin
                // freeze the winner so its AW payload cannot change while
                // AWREADY is low (was the AW stability violation)
                sel_valid <= 1'b1;
                sel       <= pick_sel;
            end
            else if (busy && s_bvalid && s_bready) begin
                busy <= 1'b0;
            end
        end
    end

endmodule
