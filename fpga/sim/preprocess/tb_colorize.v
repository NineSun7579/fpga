`timescale 1ns/1ps
//============================================================================
// tb_colorize.v : 标准色化单元仿真 (rgb2gray + colorize 链, 与顶层同构)
//   golden: golden/{img.mem, exp_gray.mem, exp_color.mem, exp_id.mem}
//   覆盖  : 三标准色命中/未命中计数、灰度命中、阈值边界像素命中数
//============================================================================
module tb_colorize;

    localparam MAXPIX = 1 << 21;

    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [15:0]       img  [0:MAXPIX-1];
    reg  [7:0]        expg [0:MAXPIX-1];
    reg  [15:0]       expc [0:MAXPIX-1];
    reg  [1:0]        expid[0:MAXPIX-1];

    integer           W = 64, H = 36, N;
    integer           sent = 0, cnt = 0, err = 0;
    integer           hit_gray = 0, hit_red = 0, hit_yel = 0, hit_grn = 0;
    integer           stall;
    reg               s_valid = 1'b0;
    reg  [15:0]       s_rgb = 16'd0;
    wire [7:0]        gray;
    wire              gray_valid;
    wire [15:0]       rgb_d1, c_rgb;
    wire [1:0]        c_id;
    wire              c_valid;

    // 阈值: 与 golden_gen.py 默认一致
    localparam [7:0]  THR_SAT = 8'd96, THR_HUE = 8'd64,
                      THR_VAL = 8'd160, THR_LOW = 8'd160;

    rgb2gray u_gray (
        .clk(clk), .rst_n(rst_n),
        .s_rgb565(s_rgb), .s_valid(s_valid),
        .m_gray(gray), .m_valid(gray_valid), .m_rgb565_d(rgb_d1)
    );

    colorize u_color (
        .clk(clk), .rst_n(rst_n),
        .thr_sat(THR_SAT), .thr_hue(THR_HUE),
        .thr_val(THR_VAL), .thr_low(THR_LOW),
        .s_rgb565(rgb_d1), .s_gray(gray), .s_valid(gray_valid),
        .m_rgb565(c_rgb), .m_color_id(c_id), .m_valid(c_valid)
    );

    initial begin
        if (!$value$plusargs("W=%d", W)) W = 64;
        if (!$value$plusargs("H=%d", H)) H = 36;
        $readmemh("golden/img.mem",    img);
        $readmemh("golden/exp_gray.mem",  expg);
        $readmemh("golden/exp_color.mem", expc);
        $readmemh("golden/exp_id.mem",    expid);
        N = W * H;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
    end

    wire [31:0] nxt_idx = sent + (s_valid ? 1 : 0);
    always @(posedge clk) begin
        if (!rst_n) begin
            s_valid <= 1'b0;
        end else begin
            stall = $random;
            s_valid <= (nxt_idx < N) && ((stall & 32'h3) != 0);
            if (s_valid) sent <= sent + 1;
            if (nxt_idx < N) s_rgb <= img[nxt_idx];
        end
    end

    always @(posedge clk) begin
        if (rst_n && c_valid) begin
            if (c_rgb !== expc[cnt] || c_id !== expid[cnt]) begin
                if (err < 10)
                    $display("[COLOR][ERR] idx=%0d got=%04h/%0d exp=%04h/%0d",
                             cnt, c_rgb, c_id, expc[cnt], expid[cnt]);
                err = err + 1;
            end
            if (c_rgb === 16'bx) begin
                $display("[COLOR][ERR] X 传播 idx=%0d", cnt);
                err = err + 1;
            end
            case (c_id)
                2'd0: hit_gray = hit_gray + 1;
                2'd1: hit_red  = hit_red  + 1;
                2'd2: hit_yel  = hit_yel  + 1;
                2'd3: hit_grn  = hit_grn  + 1;
            endcase
            cnt = cnt + 1;
        end
    end

    initial begin
        wait (rst_n);
        wait (sent == N);
        repeat (8) @(posedge clk);
        $display("[COLOR] 覆盖: gray=%0d red=%0d yellow=%0d green=%0d",
                 hit_gray, hit_red, hit_yel, hit_grn);
        if (hit_red == 0 || hit_yel == 0 || hit_grn == 0) begin
            $display("[COLOR] TB_FAIL  功能覆盖点未命中(三标准色必须全命中)");
        end else if (cnt == N && err == 0)
            $display("[COLOR] TB_PASS  pixels=%0d", cnt);
        else
            $display("[COLOR] TB_FAIL  out=%0d/%0d err=%0d", cnt, N, err);
        $finish;
    end

    initial begin
        #200_000_000;
        $display("[COLOR] TB_FAIL  超时");
        $finish;
    end

endmodule
