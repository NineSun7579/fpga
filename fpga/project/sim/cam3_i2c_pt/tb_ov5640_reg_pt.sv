`timescale 1ns/1ps
// Functional test for the host SCCB passthrough registers in ov5640_reg
// (BASE_ADDR = 0x2000_0400, i.e. the CAM3 segment).
module tb_ov5640_reg_pt;

    localparam [31:0] BASE      = 32'h2000_0400;
    localparam [31:0] R_CMD     = BASE + 32'h100;   // 0x2000_0500
    localparam [31:0] R_RD      = BASE + 32'h110;   // 0x2000_0510
    localparam [31:0] R_STAT    = BASE + 32'h120;   // 0x2000_0520

    reg clk = 0, rst = 1;
    always #5 clk = ~clk;

    reg         awvalid = 0, wvalid = 0, bready = 1;
    reg  [31:0] awaddr  = 0, wdata  = 0;
    reg         arvalid = 0, rready = 1;
    reg  [31:0] araddr  = 0;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [31:0] rdata;
    wire [1:0]  bresp, rresp;

    wire        pt_req_toggle;
    wire [15:0] pt_addr;
    wire [7:0]  pt_wdata;
    wire        pt_rw;
    reg  [7:0]  pt_rdata = 0;
    reg         pt_ack = 0;
    reg         pt_done_toggle = 0;

    ov5640_reg #(.BASE_ADDR(BASE)) dut (
        .clk(clk), .rst(rst),
        .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_awaddr(awaddr),
        .s_axi_wvalid(wvalid),   .s_axi_wready(wready),   .s_axi_wdata(wdata),
        .s_axi_wstrb(4'hF),
        .s_axi_bvalid(bvalid),   .s_axi_bready(bready),   .s_axi_bresp(bresp),
        .s_axi_arvalid(arvalid), .s_axi_arready(arready), .s_axi_araddr(araddr),
        .s_axi_rvalid(rvalid),   .s_axi_rready(rready),   .s_axi_rdata(rdata),
        .s_axi_rresp(rresp),
        .cam_addr_1(), .cam_addr_2(), .xdma_ack(), .cam_en(),
        .dbg_cam_words(32'd0), .dbg_vsyncs(32'd0), .dbg_hsyncs(32'd0),
        .dbg_href_raw(32'd0),  .dbg_vsync_raw(32'd0), .dbg_beat_cnt(32'd0),
        .dbg_beat_last(32'd0), .dbg_cmd_cnt(32'd0), .dbg_axi_sticky(32'd0),
        .dbg_axi_stat(32'd0),  .dbg_b_cnt(32'd0), .dbg_aw_cnt(32'd0),
        .dbg_w_cnt(32'd0), .dbg_axi_cnt(32'd0), .dbg_zdin(32'd0),
        .dbg_zout(32'd0), .dbg_axi_num(32'd0), .dbg_state(32'd0),
        .dbg_last_cnt(32'd0), .dbg_wd_cnt(32'd0), .dbg_xdma_req(2'd0),
        .dbg_i2c_status(32'd0), .dbg_pclk_cnt(32'd0), .dbg_sys_status(32'd0),
        .dbg_clk_status(32'd0),
        .pt_req_toggle(pt_req_toggle), .pt_addr(pt_addr), .pt_wdata(pt_wdata),
        .pt_rw(pt_rw), .pt_rdata(pt_rdata), .pt_ack(pt_ack),
        .pt_done_toggle(pt_done_toggle)
    );

    integer errors = 0;
    reg [31:0] rd;

    task check(input [255:0] name, input [31:0] got, input [31:0] exp);
        begin
            if (got !== exp) begin
                $display("FAIL %0s: got 0x%08X exp 0x%08X", name, got, exp);
                errors = errors + 1;
            end else begin
                $display("PASS %0s = 0x%08X", name, got);
            end
        end
    endtask

    task axi_write(input [31:0] a, input [31:0] d);
        integer guard;
        begin
            @(posedge clk); #1;
            awaddr = a; wdata = d; awvalid = 1; wvalid = 1;
            @(posedge clk); #1;
            awvalid = 0; wvalid = 0;
            guard = 0;
            while (!bvalid && guard < 50) begin @(posedge clk); #1; guard = guard + 1; end
            @(posedge clk); #1;
        end
    endtask

    task axi_read(input [31:0] a, output [31:0] d);
        integer guard;
        begin
            @(posedge clk); #1;
            araddr = a; arvalid = 1;
            @(posedge clk); #1;
            arvalid = 0;
            guard = 0;
            while (!rvalid && guard < 50) begin @(posedge clk); #1; guard = guard + 1; end
            d = rdata;
            @(posedge clk); #1;
        end
    endtask

    task sensor_done(input [7:0] data, input ack);
        begin
            @(posedge clk); #1;
            pt_rdata = data; pt_ack = ack;
            @(posedge clk); #1;
            pt_done_toggle = ~pt_done_toggle;
            repeat (3) @(posedge clk); #1;
        end
    endtask

    initial begin
        rst = 1;
        repeat (5) @(posedge clk);
        #1 rst = 0;
        repeat (3) @(posedge clk); #1;

        $display("--- initial readback ---");
        axi_read(R_RD, rd);   check("RD initial", rd, 32'h0000_0000);
        axi_read(R_STAT, rd); check("STAT initial", rd, 32'h0000_0000);

        $display("--- read command: 0x300A ---");
        axi_write(R_CMD, {7'h00, 1'b1, 16'h300A, 8'h00});
        #1;
        check("pt_addr after rd-cmd", pt_addr, 32'h0000_300A);
        check("pt_rw after rd-cmd",   pt_rw,   32'h1);
        check("pt_wdata after rd-cmd", pt_wdata, 32'h0);

        sensor_done(8'h56, 1'b0);
        axi_read(R_RD, rd);   check("RD after 0x300A=0x56", rd, 32'h0000_0056);
        axi_read(R_STAT, rd); check("STAT done/ack0", rd, 32'h0000_0002);

        $display("--- write command: 0x3019 = 0x02 (flash on) ---");
        axi_write(R_CMD, {7'h00, 1'b0, 16'h3019, 8'h02});
        #1;
        check("pt_addr after wr-cmd", pt_addr, 32'h0000_3019);
        check("pt_rw after wr-cmd",   pt_rw,   32'h0);
        check("pt_wdata after wr-cmd", pt_wdata, 32'h02);
        axi_read(R_STAT, rd); check("STAT cleared on new cmd", rd, 32'h0000_0000);

        sensor_done(8'h00, 1'b0);
        axi_read(R_STAT, rd); check("STAT done after wr", rd, 32'h0000_0002);

        $display("--- NACK reporting ---");
        axi_write(R_CMD, {7'h00, 1'b1, 16'h300B, 8'h00});
        sensor_done(8'h00, 1'b1);
        axi_read(R_STAT, rd); check("STAT ack=1 (NACK)", rd, 32'h0000_0003);
        axi_read(R_RD, rd);   check("RD after NACK", rd, 32'h0000_0000);

        $display("--- toggle flips once per command ---");
        check("pt_req_toggle toggled 3x", pt_req_toggle, 32'h1);

        if (errors == 0) $display("PASS ov5640_reg SCCB passthrough");
        else             $display("FAIL ov5640_reg SCCB passthrough (%0d)", errors);
        $finish;
    end

    initial begin
        #200000;
        $display("FAIL timeout");
        $finish;
    end
endmodule
