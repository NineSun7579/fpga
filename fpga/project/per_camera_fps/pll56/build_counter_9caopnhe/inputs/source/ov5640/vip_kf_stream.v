`timescale 1ns/1ps
//============================================================================
// vip_kf_stream.v -- vip_kf + DDR previous-frame line prefetcher.
//
// Wraps vip_kf (adaptive temporal Kalman / IIR, per-pixel) with a DDR read
// engine that streams the PREVIOUS frame back from the other ping-pong bank,
// line by line, so the "x" state (last frame's filtered pixel) is available
// in raster order without an on-chip full-frame buffer.
//
// How it works
// ------------
//  * Camera pixels arrive raster-order, W valid pixels per line.
//  * Row/col counters track the current input position.
//  * At vsync        -> prefetch row 0 into line buffer 0.
//    At start of row r -> prefetch row r+1 into line buffer (r+1)&1.
//    (a one-line read-ahead; each 1280-byte line read is ~1us vs ~11us line)
//  * axi_dma_read issues one 1280-byte AXI read per line; its 128-bit beats
//    are written straight into the 80 x 128b line buffer (no serial unpack).
//  * vip_kf reads the current row's buffer through prev_ren/prev_raddr, which
//    this module answers with the same 1-cycle synchronous-RAM latency
//    vip_kf expects (lane select uses the registered column).
//
// prev_base must point at the buffer holding the PREVIOUS frame (i.e. the
// other ping-pong bank), and must be stable for the whole frame.
//
// All logic is single-clock (the project runs video_clk == axi_clk).
//============================================================================
module vip_kf_stream #(
    parameter integer W            = 640,
    parameter integer H            = 480,
    parameter integer AW           = 19,     // vip_kf frame-index width
    parameter integer AXI_ID_WIDTH = 4,
    parameter integer AXI_DATA_W   = 128,
    parameter integer BURST_LEN    = 8,
    // RD_EN=0 -> previous-frame DDR read engine disabled (prev state = 0).
    // Kept as a parameter so the read path can be isolated from the pixel
    // transform during bring-up.
    parameter integer RD_EN        = 1
)(
    input  wire                    clk,
    input  wire                    rst,

    input  wire                    en,
    input  wire [5:0]              thr0,
    input  wire [5:0]              thr1,
    input  wire [5:0]              thr2,

    input  wire                    in_valid,
    input  wire [15:0]             in_pixel,
    input  wire                    in_vsync,

    input  wire [31:0]             prev_base,   // byte address, previous frame

    // ---- AXI read master (goes to a free crossbar slave port) ----
    output wire [AXI_ID_WIDTH-1:0] m_axi_arid,
    output wire [31:0]             m_axi_araddr,
    output wire [7:0]              m_axi_arlen,
    output wire [2:0]              m_axi_arsize,
    output wire [1:0]              m_axi_arburst,
    output wire                    m_axi_arlock,
    output wire [3:0]              m_axi_arcache,
    output wire [2:0]              m_axi_arprot,
    output wire                    m_axi_arvalid,
    input  wire                    m_axi_arready,
    input  wire [AXI_ID_WIDTH-1:0] m_axi_rid,
    input  wire [AXI_DATA_W-1:0]   m_axi_rdata,
    input  wire [1:0]              m_axi_rresp,
    input  wire                    m_axi_rlast,
    input  wire                    m_axi_rvalid,
    output wire                    m_axi_rready,

    // ---- filtered pixel stream out ----
    output wire                    out_valid,
    output wire [15:0]             out_pixel,
    output wire                    out_vsync
);

    localparam integer LW  = W / 8;             // 128-bit words per line (80)
    localparam integer LWA = 7;                 // ceil(log2(LW)) = 7
    localparam integer BYTES_PER_LINE = W * 2;  // 1280
    localparam [31:0]  BYTES_PER_LINE32 = W * 2;

    // AXI read-engine stream (declared up front: used by the request FSM below)
    wire                    m_cmd_ready;
    wire                    m_r_valid;
    wire                    m_r_ready;
    wire [AXI_DATA_W-1:0]   m_r_data;

    //------------------------------------------------------------------
    // row / col tracking
    //------------------------------------------------------------------
    reg vs_d;
    always @(posedge clk) if (rst) vs_d <= 1'b0; else vs_d <= in_vsync;
    wire vs_rise = in_vsync & ~vs_d;

    reg [9:0]  row;   // 0..H-1
    reg [9:0]  col;   // 0..W-1
    always @(posedge clk) begin
        if (rst) begin
            row <= 10'd0; col <= 10'd0;
        end else if (vs_rise) begin
            row <= 10'd0; col <= 10'd0;
        end else if (in_valid) begin
            if (col == W-1) begin
                col <= 10'd0;
                if (row != H-1) row <= row + 10'd1;
            end else begin
                col <= col + 10'd1;
            end
        end
    end

    wire line_start = in_valid & (col == 10'd0);
    wire next_ok    = (row != H-1);

    //------------------------------------------------------------------
    // read-request / fetch-row bookkeeping
    //------------------------------------------------------------------
    reg  [9:0] fetch_row;
    reg        req;               // a command is waiting to be issued
    wire       rd_req     = req & RD_EN;
    wire       issue_fire = rd_req & m_cmd_ready;

    always @(posedge clk) begin
        if (rst) fetch_row <= 10'd0;
        else if (vs_rise)               fetch_row <= 10'd0;
        else if (line_start && next_ok && !req) fetch_row <= row + 10'd1;
    end

    always @(posedge clk) begin
        if (rst) req <= 1'b0;
        else begin
            if (issue_fire) req <= 1'b0;                 // consume
            if (vs_rise || (line_start && next_ok && !req)) req <= 1'b1;  // (set wins)
        end
    end

    //------------------------------------------------------------------
    // line buffer: 2 banks x 80 x 128b  (simple 1W1R RAM)
    //   bank select = row[0]; write bank = fetch_row[0]
    //------------------------------------------------------------------
    reg [AXI_DATA_W-1:0] lbram [0:2*LW-1];
    reg [LWA:0]          fill_base;   // 0 or LW
    reg [LWA:0]          fill_idx;    // 0..LW-1 (LW=80 needs 7 bits)

    always @(posedge clk) begin
        if (rst)              fill_base <= {(LWA+1){1'b0}};
        else if (issue_fire)  fill_base <= fetch_row[0] ? LW[LWA:0] : {(LWA+1){1'b0}};
    end

    wire        fill_wr = m_r_valid & m_r_ready;
    always @(posedge clk) begin
        if (rst)            fill_idx <= {(LWA+1){1'b0}};
        else if (issue_fire) fill_idx <= {(LWA+1){1'b0}};    // restart per line
        else if (fill_wr)    fill_idx <= fill_idx + 1'b1;
    end
    always @(posedge clk) begin
        if (fill_wr) lbram[fill_base + fill_idx] <= m_r_data;
    end

    // read port: synchronous RAM read at LAT=1. The address is combinational
    // from the *current* row/col, so data is valid exactly one cycle after
    // prev_ren; the lane select is registered in step with the RAM output.
    reg [2:0]    rd_lane;
    reg [AXI_DATA_W-1:0] rd_q;

    wire kf_prev_ren;
    wire [LWA:0] lb_ra = (row[0] ? LW[LWA:0] : {(LWA+1){1'b0}}) + {1'b0, col[9:3]};
    always @(posedge clk) if (kf_prev_ren) rd_lane <= col[2:0];
    always @(posedge clk) rd_q <= lbram[lb_ra];

    wire [15:0] kf_prev_rdata = RD_EN ? rd_q[{rd_lane, 4'b0} +: 16] : 16'd0;

    //------------------------------------------------------------------
    // AXI read engine
    //------------------------------------------------------------------
    wire [31:0] cmd_addr = prev_base + (fetch_row * BYTES_PER_LINE32);

    axi_dma_read #(
        .BURST_LEN  (BURST_LEN),
        .ID_WIDTH   (AXI_ID_WIDTH),
        .DATA_WIDTH (AXI_DATA_W)
    ) u_rd (
        .clk            (clk),
        .rst            (rst),
        .cmd_valid      (rd_req),
        .cmd_addr       (cmd_addr),
        .cmd_len        (BYTES_PER_LINE32),
        .cmd_id         ({AXI_ID_WIDTH{1'b0}}),
        .cmd_ready      (m_cmd_ready),
        .data_out       (m_r_data),
        .data_out_valid (m_r_valid),
        .data_out_last  (),
        .data_out_ready (m_r_ready),
        .m_axi_arid     (m_axi_arid),
        .m_axi_araddr   (m_axi_araddr),
        .m_axi_arlen    (m_axi_arlen),
        .m_axi_arsize   (m_axi_arsize),
        .m_axi_arburst  (m_axi_arburst),
        .m_axi_arlock   (m_axi_arlock),
        .m_axi_arcache  (m_axi_arcache),
        .m_axi_arprot   (m_axi_arprot),
        .m_axi_arvalid  (m_axi_arvalid),
        .m_axi_arready  (m_axi_arready),
        .m_axi_rid      (m_axi_rid),
        .m_axi_rdata    (m_axi_rdata),
        .m_axi_rresp    (m_axi_rresp),
        .m_axi_rlast    (m_axi_rlast),
        .m_axi_rvalid   (m_axi_rvalid),
        .m_axi_rready   (m_axi_rready)
    );
    assign m_r_ready = 1'b1;   // always accept a beat into the line buffer

    //------------------------------------------------------------------
    // vip_kf core
    //------------------------------------------------------------------
    vip_kf #(
        .W   (W),
        .H   (H),
        .AW  (AW),
        .LAT (1)
    ) u_kf (
        .clk        (clk),
        .rst        (rst),
        .en         (en),
        .thr0       (thr0),
        .thr1       (thr1),
        .thr2       (thr2),
        .in_valid   (in_valid),
        .in_pixel   (in_pixel),
        .in_vsync   (in_vsync),
        .prev_ren   (kf_prev_ren),
        .prev_raddr (),
        .prev_rdata (kf_prev_rdata),
        .out_valid  (out_valid),
        .out_pixel  (out_pixel),
        .out_vsync  (out_vsync),
        .wr_en      (),
        .wr_addr    (),
        .wr_data    ()
    );

endmodule
