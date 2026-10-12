`timescale 1ns/1ps
// Isolated candidate. Verilog-2001; common clock/reset with the controller.
// A 16-byte physical slot represents ONE local 32-bit register, never four.
module fpga_v8_coop_axi128_endpoint #(
    parameter ID_WIDTH = 7,
    parameter [31:0] BASE_ADDR = 32'h40010000,
    parameter [31:0] WINDOW_BYTES = 32'h00001000
) (
    input wire clk, input wire rst_n,
    input wire [ID_WIDTH-1:0] s_axi_awid,
    input wire [31:0] s_axi_awaddr,
    input wire [7:0] s_axi_awlen,
    input wire [2:0] s_axi_awsize,
    input wire [1:0] s_axi_awburst,
    input wire s_axi_awlock,
    input wire [3:0] s_axi_awcache,
    input wire [2:0] s_axi_awprot,
    input wire [3:0] s_axi_awqos, input wire [3:0] s_axi_awregion,
    input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [127:0] s_axi_wdata,
    input wire [15:0] s_axi_wstrb,
    input wire s_axi_wlast, input wire s_axi_wvalid,
    output wire s_axi_wready,
    output reg [ID_WIDTH-1:0] s_axi_bid,
    output reg [1:0] s_axi_bresp,
    output wire s_axi_bvalid, input wire s_axi_bready,
    input wire [ID_WIDTH-1:0] s_axi_arid,
    input wire [31:0] s_axi_araddr,
    input wire [7:0] s_axi_arlen,
    input wire [2:0] s_axi_arsize,
    input wire [1:0] s_axi_arburst,
    input wire s_axi_arlock,
    input wire [3:0] s_axi_arcache,
    input wire [2:0] s_axi_arprot,
    input wire [3:0] s_axi_arqos, input wire [3:0] s_axi_arregion,
    input wire s_axi_arvalid, output wire s_axi_arready,
    output reg [ID_WIDTH-1:0] s_axi_rid,
    output reg [127:0] s_axi_rdata,
    output reg [1:0] s_axi_rresp,
    output wire s_axi_rlast, output wire s_axi_rvalid,
    input wire s_axi_rready,
    output wire [31:0] m_axil_awaddr,
    output wire [2:0] m_axil_awprot,
    output wire m_axil_awvalid, input wire m_axil_awready,
    output wire [31:0] m_axil_wdata,
    output wire [3:0] m_axil_wstrb,
    output wire m_axil_wvalid, input wire m_axil_wready,
    input wire [1:0] m_axil_bresp,
    input wire m_axil_bvalid, output wire m_axil_bready,
    output wire [31:0] m_axil_araddr,
    output wire [2:0] m_axil_arprot,
    output wire m_axil_arvalid, input wire m_axil_arready,
    input wire [31:0] m_axil_rdata,
    input wire [1:0] m_axil_rresp,
    input wire m_axil_rvalid, output wire m_axil_rready
);
    localparam [1:0] WC = 0, WS = 1, WB = 2, WF = 3;
    localparam [2:0] RC = 0, RS = 1, RR = 2, RF = 3, RE = 4;
    localparam CONFIG_VALID = (ID_WIDTH > 0) && (BASE_ADDR[3:0] == 0) &&
        (WINDOW_BYTES != 0) && (WINDOW_BYTES[3:0] == 0) &&
        (({1'b0, BASE_ADDR} + {1'b0, WINDOW_BYTES}) <= 33'h100000000);
    reg [1:0] wr_state;
    reg [2:0] rd_state;
    reg aw_held, w_held, w_last, w_bad;
    reg [31:0] aw_addr, ar_addr, w_data;
    reg [7:0] aw_len;
    reg [2:0] aw_size, aw_prot, ar_prot;
    reg [1:0] aw_burst;
    reg aw_lock;
    reg [3:0] w_strb;
    reg [8:0] w_remaining, r_remaining;
    reg ctrl_aw_pending, ctrl_w_pending;
    wire [31:0] aw_diff = aw_addr - BASE_ADDR;
    wire [31:0] ar_diff = ar_addr - BASE_ADDR;

    function eligible;
        input [31:0] addr;
        input [7:0] len;
        input [2:0] size;
        input [1:0] burst;
        reg [32:0] addr_end;
        begin
            addr_end = {1'b0, addr} + 33'd16;
            eligible = CONFIG_VALID && len == 0 && size == 4 &&
                (burst == 0 || burst == 1) && addr[3:0] == 0 &&
                addr[11:0] <= 12'hff0 && addr >= BASE_ADDR &&
                addr_end <= ({1'b0, BASE_ADDR} + {1'b0, WINDOW_BYTES});
        end
    endfunction

    assign s_axi_awready = rst_n && wr_state == WC && !aw_held;
    // First W may precede AW. This slot is not reused until its beat is counted.
    assign s_axi_wready = rst_n && wr_state == WC && !w_held;
    assign s_axi_bvalid = rst_n && wr_state == WF;
    assign m_axil_awaddr = aw_diff >> 2;
    assign m_axil_awprot = aw_prot;
    assign m_axil_awvalid = rst_n && wr_state == WS && ctrl_aw_pending;
    assign m_axil_wdata = w_data;
    assign m_axil_wstrb = w_strb;
    assign m_axil_wvalid = rst_n && wr_state == WS && ctrl_w_pending;
    assign m_axil_bready = rst_n && wr_state == WB;
    assign s_axi_arready = rst_n && rd_state == RC;
    assign m_axil_araddr = ar_diff >> 2;
    assign m_axil_arprot = ar_prot;
    assign m_axil_arvalid = rst_n && rd_state == RS;
    assign m_axil_rready = rst_n && rd_state == RR;
    assign s_axi_rvalid = rst_n && (rd_state == RF || rd_state == RE);
    assign s_axi_rlast = (rd_state == RE) ? (r_remaining == 1) : 1'b1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_state <= WC;
            aw_held <= 0; w_held <= 0; w_last <= 0; w_bad <= 0;
            aw_addr <= BASE_ADDR; aw_len <= 0; aw_size <= 0;
            aw_burst <= 0; aw_lock <= 0; aw_prot <= 0;
            w_data <= 0; w_strb <= 0; w_remaining <= 0;
            ctrl_aw_pending <= 0; ctrl_w_pending <= 0;
            s_axi_bid <= 0; s_axi_bresp <= 0;
            rd_state <= RC; ar_addr <= BASE_ADDR; ar_prot <= 0;
            r_remaining <= 0; s_axi_rid <= 0;
            s_axi_rdata <= 0; s_axi_rresp <= 0;
        end else begin
            if (s_axi_awvalid && s_axi_awready) begin
                aw_held <= 1;
                s_axi_bid <= s_axi_awid;
                aw_addr <= s_axi_awaddr; aw_len <= s_axi_awlen;
                aw_size <= s_axi_awsize; aw_burst <= s_axi_awburst;
                aw_lock <= s_axi_awlock; aw_prot <= s_axi_awprot;
                w_remaining <= {1'b0, s_axi_awlen} + 9'd1;
                w_bad <= 0;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                w_held <= 1;
                w_data <= s_axi_wdata[31:0];
                w_strb <= s_axi_wstrb[3:0];
                w_last <= s_axi_wlast;
            end
            if (wr_state == WC && aw_held && w_held) begin
                w_held <= 0;
                // Diagnose early/missing WLAST but always drain AWLEN+1 beats.
                if (w_last != (w_remaining == 1)) w_bad <= 1;
                if (w_remaining == 1) begin
                    if (eligible(aw_addr, aw_len, aw_size, aw_burst) &&
                        !w_bad && w_last) begin
                        ctrl_aw_pending <= 1;
                        ctrl_w_pending <= 1;
                        wr_state <= WS;
                    end else begin
                        s_axi_bresp <= 2'b10;
                        wr_state <= WF;
                    end
                    w_remaining <= 0;
                end else w_remaining <= w_remaining - 9'd1;
            end
            if (wr_state == WS) begin
                if (m_axil_awvalid && m_axil_awready) ctrl_aw_pending <= 0;
                if (m_axil_wvalid && m_axil_wready) ctrl_w_pending <= 0;
                if ((!ctrl_aw_pending || m_axil_awready) &&
                    (!ctrl_w_pending || m_axil_wready)) wr_state <= WB;
            end
            if (m_axil_bvalid && m_axil_bready) begin
                s_axi_bresp <= m_axil_bresp;
                wr_state <= WF;
            end
            if (s_axi_bvalid && s_axi_bready) begin
                wr_state <= WC;
                aw_held <= 0;
                w_bad <= 0;
            end

            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rid <= s_axi_arid;
                ar_addr <= s_axi_araddr; ar_prot <= s_axi_arprot;
                r_remaining <= {1'b0, s_axi_arlen} + 9'd1;
                if (eligible(s_axi_araddr, s_axi_arlen, s_axi_arsize,
                             s_axi_arburst)) rd_state <= RS;
                else begin
                    s_axi_rdata <= 0; s_axi_rresp <= 2'b10;
                    rd_state <= RE;
                end
            end
            if (m_axil_arvalid && m_axil_arready) rd_state <= RR;
            if (m_axil_rvalid && m_axil_rready) begin
                s_axi_rdata <= {96'd0, m_axil_rdata};
                s_axi_rresp <= m_axil_rresp;
                rd_state <= RF;
            end
            if (s_axi_rvalid && s_axi_rready) begin
                if (rd_state == RF || r_remaining == 1) begin
                    rd_state <= RC; r_remaining <= 0;
                end else r_remaining <= r_remaining - 9'd1;
            end
        end
    end
    // LOCK/CACHE/QOS/REGION have no local semantics. LOCK never returns EXOKAY.
    // Invalid static configurations reject every transaction; runner validates
    // the published configuration before simulation. No cancellation/timeout.
endmodule
