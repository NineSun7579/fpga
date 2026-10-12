`timescale 1ns/1ps
//============================================================================
// tb_cam4_decode.sv : 5-way ovreg_axil_decode routing TB (cam1..cam4 + prep)
//
//   DUT: BFM -> ovreg_axil_decode -> 5 marker stub slaves
//     m0 = cam1 regs   0x2000_0000 (and legacy prep window on page 0)
//     m1 = prep regs   0x2000_0100
//     m2 = cam2 regs   0x2000_0200
//     m3 = cam3 regs   0x2000_0400 / 0x0500 (SCCB)
//     m4 = cam4 regs   0x2000_0600 / 0x0700 (SCCB)
//
//   Every stub returns a distinct marker (0x5A5A00xx) so the READ DATA
//   identifies exactly which downstream port answered. This covers:
//     * the addr[9] CAM3/CAM4 split inside the camera page (0x400..0x7FF)
//     * the legacy prep fallback (page 0, addr[9:8]=11)
//     * the CDC diagnostic override which routes by addr[11:9] instead of
//       addr[9:8] (so 0x2000_0190 -> cam1, 0x2000_0390 -> cam2, ...)
//============================================================================
module stub_slave #(parameter [7:0] MARK = 8'h00) (
    input  wire        clk,
    input  wire        rst,
    input  wire        awvalid,
    output wire        awready,
    input  wire [31:0] awaddr,
    input  wire        wvalid,
    output wire        wready,
    input  wire [31:0] wdata,
    input  wire [3:0]  wstrb,
    output wire        bvalid,
    input  wire        bready,
    output wire [1:0]  bresp,
    input  wire        arvalid,
    output wire        arready,
    input  wire [31:0] araddr,
    output wire        rvalid,
    input  wire        rready,
    output wire [31:0] rdata,
    output wire [1:0]  rresp
);
    reg rvalid_r = 1'b0;
    reg bvalid_r = 1'b0;
    always @(posedge clk) begin
        if (rst) begin
            rvalid_r <= 1'b0;
            bvalid_r <= 1'b0;
        end else begin
            if (arvalid && arready)      rvalid_r <= 1'b1;
            else if (rvalid_r && rready) rvalid_r <= 1'b0;
            if (awvalid && awready && wvalid && wready) bvalid_r <= 1'b1;
            else if (bvalid_r && bready)                 bvalid_r <= 1'b0;
        end
    end
    assign awready = ~bvalid_r;
    assign wready  = ~bvalid_r;
    assign arready = ~rvalid_r;
    assign bvalid  = bvalid_r;
    assign rvalid  = rvalid_r;
    assign bresp   = 2'b00;
    assign rresp   = 2'b00;
    assign rdata   = {24'h5A5A00, MARK};
endmodule

module tb_cam4_decode;
    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    reg          awvalid = 1'b0, wvalid = 1'b0, bready = 1'b0;
    reg          arvalid = 1'b0, rready = 1'b0;
    reg  [31:0]  awaddr = 32'd0, wdata = 32'd0, araddr = 32'd0;
    reg  [3:0]   wstrb = 4'hF;
    wire         awready, wready, bvalid, arready, rvalid;
    wire  [1:0]  bresp, rresp;
    wire [31:0]  rdata;

    wire         m_awvalid [0:4];
    wire         m_awready [0:4];
    wire [31:0]  m_awaddr  [0:4];
    wire         m_wvalid  [0:4];
    wire         m_wready  [0:4];
    wire [31:0]  m_wdata   [0:4];
    wire  [3:0]  m_wstrb   [0:4];
    wire         m_bvalid  [0:4];
    wire         m_bready  [0:4];
    wire  [1:0]  m_bresp   [0:4];
    wire         m_arvalid [0:4];
    wire         m_arready [0:4];
    wire [31:0]  m_araddr  [0:4];
    wire         m_rvalid  [0:4];
    wire         m_rready  [0:4];
    wire [31:0]  m_rdata   [0:4];
    wire  [1:0]  m_rresp   [0:4];

    ovreg_axil_decode dut (
        .clk(clk), .rst(rst),
        .s_awvalid(awvalid), .s_awready(awready), .s_awaddr(awaddr),
        .s_wvalid(wvalid), .s_wready(wready), .s_wdata(wdata), .s_wstrb(wstrb),
        .s_bvalid(bvalid), .s_bready(bready), .s_bresp(bresp),
        .s_arvalid(arvalid), .s_arready(arready), .s_araddr(araddr),
        .s_rvalid(rvalid), .s_rready(rready), .s_rdata(rdata), .s_rresp(rresp),
        .m0_awvalid(m_awvalid[0]), .m0_awready(m_awready[0]), .m0_awaddr(m_awaddr[0]),
        .m0_wvalid(m_wvalid[0]), .m0_wready(m_wready[0]), .m0_wdata(m_wdata[0]), .m0_wstrb(m_wstrb[0]),
        .m0_bvalid(m_bvalid[0]), .m0_bready(m_bready[0]), .m0_bresp(m_bresp[0]),
        .m0_arvalid(m_arvalid[0]), .m0_arready(m_arready[0]), .m0_araddr(m_araddr[0]),
        .m0_rvalid(m_rvalid[0]), .m0_rready(m_rready[0]), .m0_rdata(m_rdata[0]), .m0_rresp(m_rresp[0]),
        .m1_awvalid(m_awvalid[1]), .m1_awready(m_awready[1]), .m1_awaddr(m_awaddr[1]),
        .m1_wvalid(m_wvalid[1]), .m1_wready(m_wready[1]), .m1_wdata(m_wdata[1]), .m1_wstrb(m_wstrb[1]),
        .m1_bvalid(m_bvalid[1]), .m1_bready(m_bready[1]), .m1_bresp(m_bresp[1]),
        .m1_arvalid(m_arvalid[1]), .m1_arready(m_arready[1]), .m1_araddr(m_araddr[1]),
        .m1_rvalid(m_rvalid[1]), .m1_rready(m_rready[1]), .m1_rdata(m_rdata[1]), .m1_rresp(m_rresp[1]),
        .m2_awvalid(m_awvalid[2]), .m2_awready(m_awready[2]), .m2_awaddr(m_awaddr[2]),
        .m2_wvalid(m_wvalid[2]), .m2_wready(m_wready[2]), .m2_wdata(m_wdata[2]), .m2_wstrb(m_wstrb[2]),
        .m2_bvalid(m_bvalid[2]), .m2_bready(m_bready[2]), .m2_bresp(m_bresp[2]),
        .m2_arvalid(m_arvalid[2]), .m2_arready(m_arready[2]), .m2_araddr(m_araddr[2]),
        .m2_rvalid(m_rvalid[2]), .m2_rready(m_rready[2]), .m2_rdata(m_rdata[2]), .m2_rresp(m_rresp[2]),
        .m3_awvalid(m_awvalid[3]), .m3_awready(m_awready[3]), .m3_awaddr(m_awaddr[3]),
        .m3_wvalid(m_wvalid[3]), .m3_wready(m_wready[3]), .m3_wdata(m_wdata[3]), .m3_wstrb(m_wstrb[3]),
        .m3_bvalid(m_bvalid[3]), .m3_bready(m_bready[3]), .m3_bresp(m_bresp[3]),
        .m3_arvalid(m_arvalid[3]), .m3_arready(m_arready[3]), .m3_araddr(m_araddr[3]),
        .m3_rvalid(m_rvalid[3]), .m3_rready(m_rready[3]), .m3_rdata(m_rdata[3]), .m3_rresp(m_rresp[3]),
        .m4_awvalid(m_awvalid[4]), .m4_awready(m_awready[4]), .m4_awaddr(m_awaddr[4]),
        .m4_wvalid(m_wvalid[4]), .m4_wready(m_wready[4]), .m4_wdata(m_wdata[4]), .m4_wstrb(m_wstrb[4]),
        .m4_bvalid(m_bvalid[4]), .m4_bready(m_bready[4]), .m4_bresp(m_bresp[4]),
        .m4_arvalid(m_arvalid[4]), .m4_arready(m_arready[4]), .m4_araddr(m_araddr[4]),
        .m4_rvalid(m_rvalid[4]), .m4_rready(m_rready[4]), .m4_rdata(m_rdata[4]), .m4_rresp(m_rresp[4])
    );

    stub_slave #(.MARK(8'h10)) s0 (
        .clk(clk), .rst(rst),
        .awvalid(m_awvalid[0]), .awready(m_awready[0]), .awaddr(m_awaddr[0]),
        .wvalid(m_wvalid[0]), .wready(m_wready[0]), .wdata(m_wdata[0]), .wstrb(m_wstrb[0]),
        .bvalid(m_bvalid[0]), .bready(m_bready[0]), .bresp(m_bresp[0]),
        .arvalid(m_arvalid[0]), .arready(m_arready[0]), .araddr(m_araddr[0]),
        .rvalid(m_rvalid[0]), .rready(m_rready[0]), .rdata(m_rdata[0]), .rresp(m_rresp[0]));
    stub_slave #(.MARK(8'h20)) s1 (
        .clk(clk), .rst(rst),
        .awvalid(m_awvalid[1]), .awready(m_awready[1]), .awaddr(m_awaddr[1]),
        .wvalid(m_wvalid[1]), .wready(m_wready[1]), .wdata(m_wdata[1]), .wstrb(m_wstrb[1]),
        .bvalid(m_bvalid[1]), .bready(m_bready[1]), .bresp(m_bresp[1]),
        .arvalid(m_arvalid[1]), .arready(m_arready[1]), .araddr(m_araddr[1]),
        .rvalid(m_rvalid[1]), .rready(m_rready[1]), .rdata(m_rdata[1]), .rresp(m_rresp[1]));
    stub_slave #(.MARK(8'h30)) s2 (
        .clk(clk), .rst(rst),
        .awvalid(m_awvalid[2]), .awready(m_awready[2]), .awaddr(m_awaddr[2]),
        .wvalid(m_wvalid[2]), .wready(m_wready[2]), .wdata(m_wdata[2]), .wstrb(m_wstrb[2]),
        .bvalid(m_bvalid[2]), .bready(m_bready[2]), .bresp(m_bresp[2]),
        .arvalid(m_arvalid[2]), .arready(m_arready[2]), .araddr(m_araddr[2]),
        .rvalid(m_rvalid[2]), .rready(m_rready[2]), .rdata(m_rdata[2]), .rresp(m_rresp[2]));
    stub_slave #(.MARK(8'h40)) s3 (
        .clk(clk), .rst(rst),
        .awvalid(m_awvalid[3]), .awready(m_awready[3]), .awaddr(m_awaddr[3]),
        .wvalid(m_wvalid[3]), .wready(m_wready[3]), .wdata(m_wdata[3]), .wstrb(m_wstrb[3]),
        .bvalid(m_bvalid[3]), .bready(m_bready[3]), .bresp(m_bresp[3]),
        .arvalid(m_arvalid[3]), .arready(m_arready[3]), .araddr(m_araddr[3]),
        .rvalid(m_rvalid[3]), .rready(m_rready[3]), .rdata(m_rdata[3]), .rresp(m_rresp[3]));
    stub_slave #(.MARK(8'h50)) s4 (
        .clk(clk), .rst(rst),
        .awvalid(m_awvalid[4]), .awready(m_awready[4]), .awaddr(m_awaddr[4]),
        .wvalid(m_wvalid[4]), .wready(m_wready[4]), .wdata(m_wdata[4]), .wstrb(m_wstrb[4]),
        .bvalid(m_bvalid[4]), .bready(m_bready[4]), .bresp(m_bresp[4]),
        .arvalid(m_arvalid[4]), .arready(m_arready[4]), .araddr(m_araddr[4]),
        .rvalid(m_rvalid[4]), .rready(m_rready[4]), .rdata(m_rdata[4]), .rresp(m_rresp[4]));

    integer err = 0;

    task chk_rd(input [31:0] a, input [31:0] exp);
        reg [31:0] d;
        begin
            @(negedge clk); araddr = a; arvalid = 1'b1;
            @(posedge clk); while (!arready) @(posedge clk);
            @(negedge clk); arvalid = 1'b0;
            while (!rvalid) @(posedge clk);
            d = rdata;
            if (rresp !== 2'b00 || d !== exp) begin
                $display("[C4DEC][ERR] rd %08h got %08h exp %08h rresp=%b", a, d, exp, rresp);
                err = err + 1;
            end else begin
                $display("[C4DEC] ok rd %08h -> %08h", a, d);
            end
            rready = 1'b1; @(negedge clk); rready = 1'b0;
        end
    endtask

    task chk_wr(input [31:0] a, input [31:0] d);
        begin
            @(negedge clk); awaddr = a; wdata = d; wstrb = 4'hF; awvalid = 1'b1; wvalid = 1'b1;
            @(posedge clk); while (!(awready && wready)) @(posedge clk);
            @(negedge clk); awvalid = 1'b0; wvalid = 1'b0;
            while (!bvalid) @(posedge clk);
            if (bresp !== 2'b00) begin
                $display("[C4DEC][ERR] wr %08h bad bresp=%b", a, bresp);
                err = err + 1;
            end
            bready = 1'b1; @(negedge clk); bready = 1'b0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst = 1'b0;
        repeat (2) @(negedge clk);

        // --- normal window routing (marker names the serving port) ---
        chk_rd(32'h2000_0000, 32'h5A5A0010); // cam1
        chk_rd(32'h2000_0100, 32'h5A5A0020); // prep
        chk_rd(32'h2000_0200, 32'h5A5A0030); // cam2
        chk_rd(32'h2000_0300, 32'h5A5A0020); // prep (legacy page0 addr[9:8]=11)
        chk_rd(32'h2000_0400, 32'h5A5A0040); // cam3 main
        chk_rd(32'h2000_0500, 32'h5A5A0040); // cam3 SCCB
        chk_rd(32'h2000_0600, 32'h5A5A0050); // cam4 main
        chk_rd(32'h2000_0700, 32'h5A5A0050); // cam4 SCCB

        // --- CDC diagnostic override: route by addr[11:9], ignore addr[9:8] ---
        chk_rd(32'h2000_0190, 32'h5A5A0010); // cam1 (normal route would be m1)
        chk_rd(32'h2000_0390, 32'h5A5A0030); // cam2 (normal route would be m1)
        chk_rd(32'h2000_0590, 32'h5A5A0040); // cam3
        chk_rd(32'h2000_0790, 32'h5A5A0050); // cam4
        chk_rd(32'h2000_01A0, 32'h5A5A0010);
        chk_rd(32'h2000_01B0, 32'h5A5A0010);
        chk_rd(32'h2000_01C0, 32'h5A5A0010);
        chk_rd(32'h2000_07C0, 32'h5A5A0050);

        // --- non-CDC offsets keep the normal route ---
        chk_rd(32'h2000_0080, 32'h5A5A0010); // cam1
        chk_rd(32'h2000_0180, 32'h5A5A0020); // prep
        chk_rd(32'h2000_0380, 32'h5A5A0020); // prep
        chk_rd(32'h2000_0680, 32'h5A5A0050); // cam4

        // --- write path (B routing) on cam1/cam3/cam4 ---
        chk_wr(32'h2000_0080, 32'h0080_0000);
        chk_wr(32'h2000_0480, 32'h0100_0000);
        chk_wr(32'h2000_0680, 32'h0140_0000);

        if (err == 0) $display("[C4DEC] TB_PASS");
        else          $display("[C4DEC] TB_FAIL  err=%0d", err);
        $finish;
    end

    initial begin
        #200_000;
        $display("[C4DEC] TB_FAIL timeout");
        $finish;
    end
endmodule
