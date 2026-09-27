`timescale 1ns / 1ps
// tb_cam2_merge.v : 双摄拼接模块仿真 (快域公共时钟版)
//   两个合成摄像头模型(640x480, HTS=1000像素时钟, VTS=705, vsync高电平在消隐),
//   o_clk=100MHz。检查: 每段640像素、A段行号连续递增、B段为B格式、
//   帧内480行、帧间 de 总数 = 480*1280。
module tb_cam2_merge;

    parameter TA = 23.809;    // A 42.000MHz
    parameter TB = 23.799;    // B 42.017MHz (+360ppm 频差)
    parameter TO = 10.0;      // o_clk 100MHz

    reg a_clk = 0, b_clk = 0, o_clk = 0;
    always #(TA/2.0) a_clk = ~a_clk;
    always #(TB/2.0) b_clk = ~b_clk;
    always #(TO/2.0) o_clk = ~o_clk;

    reg rst_n = 0;
    initial begin
        #200;
        rst_n = 1;
    end

    localparam LP = 640, LINES = 480, HTS = 1000, VTS = 705, VS_LINES = 4;

    reg  [15:0] a_data, b_data;
    reg         a_de, b_de, a_vs, b_vs;

    // A 摄像头 (a_clk 域)
    reg [11:0] a_vcnt = 0, a_hcnt = 0;
    wire a_active = (a_vcnt >= VS_LINES) && (a_vcnt < VS_LINES + LINES);
    wire a_de_raw = a_active && (a_hcnt < LP);
    wire a_vs_raw = (a_vcnt < VS_LINES);
    reg  a_de_o = 0, a_vs_o = 0;
    reg [15:0] a_pix;
    wire [11:0] a_yline = a_vcnt - VS_LINES;
    wire [15:0] a_pix_raw = (a_active && a_de_raw) ? {a_yline[3:0], a_hcnt[11:0]} : 16'hDEAD;
    always @(posedge a_clk) begin
        a_de_o <= a_de_raw; a_vs_o <= a_vs_raw; a_pix <= a_pix_raw;
        if (a_hcnt == HTS-1) begin a_hcnt <= 0; a_vcnt <= (a_vcnt==VTS-1)? 0 : a_vcnt+1; end
        else a_hcnt <= a_hcnt + 1;
    end
    always @* begin a_de = a_de_o; a_vs = a_vs_o; a_data = a_pix; end

    // B 摄像头 (b_clk 域), 相位差半帧
    reg [11:0] b_vcnt = 0, b_hcnt = 0;
    initial b_vcnt = 479;
    wire b_active = (b_vcnt >= VS_LINES) && (b_vcnt < VS_LINES + LINES);
    wire b_de_raw = b_active && (b_hcnt < LP);
    wire b_vs_raw = (b_vcnt < VS_LINES);
    reg  b_de_o = 0, b_vs_o = 0;
    reg [15:0] b_pix;
    wire [11:0] b_yline = b_vcnt - VS_LINES;
    wire [15:0] b_pix_raw = (b_active && b_de_raw) ? {4'b1000, b_yline[3:0], b_hcnt[7:0]} : 16'hBEEF;
    always @(posedge b_clk) begin
        b_de_o <= b_de_raw; b_vs_o <= b_vs_raw; b_pix <= b_pix_raw;
        if (b_hcnt == HTS-1) begin b_hcnt <= 0; b_vcnt <= (b_vcnt==VTS-1)? 0 : b_vcnt+1; end
        else b_hcnt <= b_hcnt + 1;
    end
    always @* begin b_de = b_de_o; b_vs = b_vs_o; b_data = b_pix; end

    // ---------------- DUT ----------------
    wire [15:0] c_data;
    wire        c_de, c_vs;

    cam2_merge #(.LINE_PIX(LP), .LINES(LINES)) dut (
        .a_clk(a_clk), .a_rst_n(rst_n),
        .a_data(a_data), .a_de(a_de), .a_vs(a_vs),
        .b_clk(b_clk), .b_rst_n(rst_n),
        .b_data(b_data), .b_de(b_de), .b_vs(b_vs),
        .o_clk(o_clk), .o_rst_n(rst_n),
        .c_data(c_data), .c_de(c_de), .c_vs(c_vs)
    );

    // ---------------- 检查器 (o_clk 域) ----------------
    integer frame_cnt = 0;
    integer line_cnt  = 0;
    integer run_len   = 0;
    integer run_id    = 0;
    integer de_total  = 0;
    integer errors    = 0;
    integer line_cnt_prev = 0, de_total_prev = 0;
    integer dbg_runs = 0;
    integer a_expect = 0;      // A 段期望行号 (允许跳行但记录)
    integer a_skips  = 0;
    reg [15:0] raw;
    reg [15:0] first_raw;
    reg vs_d = 0;

    always @(posedge o_clk) begin
        if (rst_n) begin
            if (c_vs && !vs_d) begin
                frame_cnt = frame_cnt + 1;
                if (frame_cnt > 1) begin
                    if (line_cnt_prev != LINES) begin
                        $display("ERROR [%0t]: frame %0d had %0d lines (expect %0d)", $time, frame_cnt-1, line_cnt_prev, LINES);
                        errors = errors + 1;
                    end
                    if (de_total_prev != LINES*1280) begin
                        $display("ERROR [%0t]: frame %0d de_total=%0d (expect %0d)", $time, frame_cnt-1, de_total_prev, LINES*1280);
                        errors = errors + 1;
                    end
                end
                line_cnt = 0; run_id = 0; de_total = 0;
            end
            vs_d <= c_vs;

            if (c_de) begin
                de_total = de_total + 1;
                run_len = run_len + 1;
                raw = {c_data[4:0], c_data[10:5], c_data[15:11]};
                if (run_len == 1 && run_id == 0) begin
                    line_cnt = line_cnt + 1;
                    if (raw[15:12] != a_expect[3:0]) begin
                        $display("NOTE [%0t]: merged line %0d A-line jumped to %0d (skipped %0d)", $time, line_cnt, raw[15:12], (raw[15:12]-a_expect[3:0]));
                        a_skips = a_skips + 1;
                    end
                    a_expect = raw[15:12] + 1;
                end
                if (run_id == 0) begin
                    if (raw[15:12] != (a_expect-1)) begin
                        $display("ERROR [%0t]: A-seg raw %h line %0d mismatch", $time, raw, line_cnt);
                        errors = errors + 1;
                    end
                end else begin
                    if (raw[15:12] != 4'b1000) begin
                        $display("ERROR [%0t]: B-seg raw %h line %0d not B-format", $time, raw, line_cnt);
                        errors = errors + 1;
                    end
                end
            end else if (run_len > 0) begin
                if (run_len != LP) begin
                    $display("ERROR [%0t]: run len %0d (expect %0d) line %0d seg %0d", $time, run_len, LP, line_cnt, run_id);
                    errors = errors + 1;
                end
                if (dbg_runs < 12) begin
                    $display("RUN[%0d] [%0t] line %0d seg %s len %0d first_raw %h", dbg_runs, $time, line_cnt, (run_id==0)?"A":"B", run_len, first_raw);
                    dbg_runs = dbg_runs + 1;
                end
                run_len = 0;
                run_id = run_id ^ 1;
            end
            if (c_de && run_len == 1) first_raw = raw;
        end
    end

    always @(posedge o_clk) begin
        line_cnt_prev <= line_cnt;   // 帧尾快照
        de_total_prev <= de_total;
    end

    always @(posedge c_vs) $display("CVS_RISE [%0t] pair=%0d state=%0d", $time, dut.pair_cnt, dut.state);

    initial begin
        #20_000_000;   // 20ms ≈ 1.2帧
        $display("=== 20ms: frames=%0d errors=%0d a_skips=%0d ===", frame_cnt, errors, a_skips);
        #17_000_000;   // 共37ms ≈ 2.2帧
        $display("=== SUMMARY: frames=%0d errors=%0d a_skips=%0d ===", frame_cnt, errors, a_skips);
        if (errors == 0 && frame_cnt >= 2) $display("TEST PASS");
        else $display("TEST FAIL");
        $finish;
    end
endmodule
