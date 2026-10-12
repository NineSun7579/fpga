`timescale 1ns/1ps
// Isolated AXI4 write candidate: m0..m5 cameras, m6 preprocessing.
// Slot i occupies [i*FIELD_WIDTH +: FIELD_WIDTH] in every packed port.
// See README.md for staging, common-reset and protocol-error contracts.
module fpga_v8_ddr_write_arbiter #(
    parameter integer MASTER_COUNT = 7,
    parameter integer ID_WIDTH = 4,
    parameter integer ADDR_WIDTH = 32,
    parameter integer DATA_WIDTH = 128,
    parameter integer OWNER_WIDTH = (MASTER_COUNT > 1) ? $clog2(MASTER_COUNT) : 1
) (
    input  wire clk,
    input  wire rst_n,
    input  wire [MASTER_COUNT*ID_WIDTH-1:0] m_awid,
    input  wire [MASTER_COUNT*ADDR_WIDTH-1:0] m_awaddr,
    input  wire [MASTER_COUNT*8-1:0] m_awlen,
    input  wire [MASTER_COUNT*3-1:0] m_awsize,
    input  wire [MASTER_COUNT*2-1:0] m_awburst,
    input  wire [MASTER_COUNT-1:0] m_awlock,
    input  wire [MASTER_COUNT*4-1:0] m_awcache,
    input  wire [MASTER_COUNT*3-1:0] m_awprot,
    input  wire [MASTER_COUNT*4-1:0] m_awqos,
    input  wire [MASTER_COUNT*4-1:0] m_awregion,
    input  wire [MASTER_COUNT-1:0] m_awvalid,
    output wire [MASTER_COUNT-1:0] m_awready,
    input  wire [MASTER_COUNT*DATA_WIDTH-1:0] m_wdata,
    input  wire [MASTER_COUNT*(DATA_WIDTH/8)-1:0] m_wstrb,
    input  wire [MASTER_COUNT-1:0] m_wlast,
    input  wire [MASTER_COUNT-1:0] m_wvalid,
    output wire [MASTER_COUNT-1:0] m_wready,
    output wire [MASTER_COUNT*ID_WIDTH-1:0] m_bid,
    output wire [MASTER_COUNT*2-1:0] m_bresp,
    output wire [MASTER_COUNT-1:0] m_bvalid,
    input  wire [MASTER_COUNT-1:0] m_bready,
    output wire [ID_WIDTH-1:0] s_awid,
    output wire [ADDR_WIDTH-1:0] s_awaddr,
    output wire [7:0] s_awlen,
    output wire [2:0] s_awsize,
    output wire [1:0] s_awburst,
    output wire s_awlock,
    output wire [3:0] s_awcache,
    output wire [2:0] s_awprot,
    output wire [3:0] s_awqos,
    output wire [3:0] s_awregion,
    output wire s_awvalid,
    input  wire s_awready,
    output wire [DATA_WIDTH-1:0] s_wdata,
    output wire [DATA_WIDTH/8-1:0] s_wstrb,
    output wire s_wlast,
    output wire s_wvalid,
    input  wire s_wready,
    input  wire [ID_WIDTH-1:0] s_bid,
    input  wire [1:0] s_bresp,
    input  wire s_bvalid,
    output wire s_bready,
    output wire busy,
    output wire [OWNER_WIDTH-1:0] owner,
    output wire error,
    output reg [4:0] error_flags
);
    localparam [1:0] IDLE = 2'd0, ADDRESS = 2'd1,
                     DATA = 2'd2, RESPONSE = 2'd3;
    reg [1:0] state;
    reg [OWNER_WIDTH-1:0] owner_reg, rr_next;
    reg [ID_WIDTH-1:0] awid_reg;
    reg [ADDR_WIDTH-1:0] awaddr_reg;
    reg [7:0] awlen_reg;
    reg [2:0] awsize_reg;
    reg [1:0] awburst_reg;
    reg awlock_reg;
    reg [3:0] awcache_reg;
    reg [2:0] awprot_reg;
    reg [3:0] awqos_reg, awregion_reg;
    // Nine bits deliberately represent all AXI4 lengths, including 256 beats.
    reg [8:0] beats_left;
    reg pick_valid;
    reg [OWNER_WIDTH-1:0] pick;
    integer offset, candidate;

    always @* begin
        pick_valid = 1'b0;
        pick = {OWNER_WIDTH{1'b0}};
        candidate = 0;
        for (offset = 0; offset < MASTER_COUNT; offset = offset + 1) begin
            candidate = rr_next + offset;
            if (candidate >= MASTER_COUNT)
                candidate = candidate - MASTER_COUNT;
            if (!pick_valid && m_awvalid[candidate]) begin
                pick_valid = 1'b1;
                pick = candidate;
            end
        end
    end

    assign busy = rst_n && (state != IDLE);
    assign owner = owner_reg; // Meaningful only when busy is asserted.
    assign error = |error_flags;
    assign s_awid = awid_reg;
    assign s_awaddr = awaddr_reg;
    assign s_awlen = awlen_reg;
    assign s_awsize = awsize_reg;
    assign s_awburst = awburst_reg;
    assign s_awlock = awlock_reg;
    assign s_awcache = awcache_reg;
    assign s_awprot = awprot_reg;
    assign s_awqos = awqos_reg;
    assign s_awregion = awregion_reg;
    assign s_awvalid = rst_n && (state == ADDRESS);
    assign s_wvalid = rst_n && (state == DATA) && m_wvalid[owner_reg];
    assign s_wdata = (state == DATA) ?
                     m_wdata[owner_reg*DATA_WIDTH +: DATA_WIDTH] : {DATA_WIDTH{1'b0}};
    assign s_wstrb = (state == DATA) ?
                     m_wstrb[owner_reg*(DATA_WIDTH/8) +: DATA_WIDTH/8] : {(DATA_WIDTH/8){1'b0}};
    assign s_wlast = (state == DATA) && m_wlast[owner_reg];
    // Gate BVALID as well as BREADY. An early B must never retire upstream.
    assign s_bready = rst_n && (state == RESPONSE) && m_bready[owner_reg];
    assign m_bid = {MASTER_COUNT{s_bid}};
    assign m_bresp = {MASTER_COUNT{s_bresp}};
    genvar i;
    generate for (i = 0; i < MASTER_COUNT; i = i + 1) begin : master_routes
        assign m_awready[i] = s_awvalid && (owner_reg == i) && s_awready;
        assign m_wready[i] = rst_n && (state == DATA) && (owner_reg == i) && s_wready;
        assign m_bvalid[i] = rst_n && (state == RESPONSE) && (owner_reg == i) && s_bvalid;
    end endgenerate

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            owner_reg <= 0;
            rr_next <= 0;
            awid_reg <= 0;
            awaddr_reg <= 0;
            awlen_reg <= 0;
            awsize_reg <= 0;
            awburst_reg <= 0;
            awlock_reg <= 0;
            awcache_reg <= 0;
            awprot_reg <= 0;
            awqos_reg <= 0;
            awregion_reg <= 0;
            beats_left <= 0;
            error_flags <= 0;
        end else begin
            if (s_bvalid && state != RESPONSE)
                error_flags[3] <= 1'b1;
            if (state == RESPONSE && s_bvalid) begin
                if (s_bid != awid_reg)
                    error_flags[1] <= 1'b1;
                if (s_bresp != 2'b00)
                    error_flags[2] <= 1'b1;
            end
            case (state)
                IDLE: if (pick_valid) begin
                    // Selection is not acceptance: no upstream READY here.
                    // Snapshot every field before first presenting slave VALID.
                    owner_reg <= pick;
                    awid_reg <= m_awid[pick*ID_WIDTH +: ID_WIDTH];
                    awaddr_reg <= m_awaddr[pick*ADDR_WIDTH +: ADDR_WIDTH];
                    awlen_reg <= m_awlen[pick*8 +: 8];
                    awsize_reg <= m_awsize[pick*3 +: 3];
                    awburst_reg <= m_awburst[pick*2 +: 2];
                    awlock_reg <= m_awlock[pick];
                    awcache_reg <= m_awcache[pick*4 +: 4];
                    awprot_reg <= m_awprot[pick*3 +: 3];
                    awqos_reg <= m_awqos[pick*4 +: 4];
                    awregion_reg <= m_awregion[pick*4 +: 4];
                    beats_left <= {1'b0, m_awlen[pick*8 +: 8]} + 9'd1;
                    state <= ADDRESS;
                end
                ADDRESS: begin
                    // Contract diagnostic only; never cancel a presented AW.
                    if (!m_awvalid[owner_reg] ||
                        m_awid[owner_reg*ID_WIDTH +: ID_WIDTH] != awid_reg ||
                        m_awaddr[owner_reg*ADDR_WIDTH +: ADDR_WIDTH] != awaddr_reg ||
                        m_awlen[owner_reg*8 +: 8] != awlen_reg ||
                        m_awsize[owner_reg*3 +: 3] != awsize_reg ||
                        m_awburst[owner_reg*2 +: 2] != awburst_reg ||
                        m_awlock[owner_reg] != awlock_reg ||
                        m_awcache[owner_reg*4 +: 4] != awcache_reg ||
                        m_awprot[owner_reg*3 +: 3] != awprot_reg ||
                        m_awqos[owner_reg*4 +: 4] != awqos_reg ||
                        m_awregion[owner_reg*4 +: 4] != awregion_reg)
                        error_flags[4] <= 1'b1;
                    if (s_awready)
                        state <= DATA;
                end
                DATA: if (s_wvalid && s_wready) begin
                    if (s_wlast != (beats_left == 9'd1))
                        error_flags[0] <= 1'b1;
                    beats_left <= beats_left - 9'd1;
                    if (beats_left == 9'd1)
                        state <= RESPONSE;
                end
                RESPONSE: if (s_bvalid && s_bready) begin
                    rr_next <= (owner_reg == MASTER_COUNT-1) ?
                               {OWNER_WIDTH{1'b0}} : owner_reg + 1'b1;
                    state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
