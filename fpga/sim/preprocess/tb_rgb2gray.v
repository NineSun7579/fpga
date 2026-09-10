`timescale 1ns/1ps
//============================================================================
// tb_rgb2gray.v : rgb2gray 单元仿真 (任务5)
//   golden: sim/preprocess/golden/{img.mem, exp_gray.mem}
//   判定  : 输出流与 golden 逐像素一致 (含随机 valid 间隔)
//   覆盖  : 像素总数、X 传播检查
//============================================================================
module tb_rgb2gray;

    localparam MAXPIX = 1 << 21;

    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [15:0]       img  [0:MAXPIX-1];
    reg  [7:0]        expg [0:MAXPIX-1];

    integer           W = 64, H = 36, N;
    integer           sent = 0, cnt = 0, err = 0;
    integer           stall;
    reg               s_valid = 1'b0;
    reg  [15:0]       s_rgb = 16'd0;
    wire [7:0]        m_gray;
    wire              m_valid;
    wire [15:0]       m_rgb_d;

    rgb2gray dut (
        .clk(clk), .rst_n(rst_n),
        .s_rgb565(s_rgb), .s_valid(s_valid),
        .m_gray(m_gray), .m_valid(m_valid), .m_rgb565_d(m_rgb_d)
    );

    initial begin
        if (!$value$plusargs("W=%d", W)) W = 64;
        if (!$value$plusargs("H=%d", H)) H = 36;
        $readmemh("golden/img.mem",       img);
        $readmemh("golden/exp_gray.mem",  expg);
        N = W * H;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
    end

    // 激励: 带随机间隔的 valid (验证 valid 门控不丢拍)
    // nxt_idx = 下一拍将呈现的像素序号 (含在途像素)
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

    // 比对
    always @(posedge clk) begin
        if (rst_n && m_valid) begin
            if (m_gray !== expg[cnt]) begin
                if (err < 10)
                    $display("[RGB2GRAY][ERR] idx=%0d got=%02h exp=%02h", cnt, m_gray, expg[cnt]);
                err = err + 1;
            end
            if (m_gray === 8'bx) begin
                $display("[RGB2GRAY][ERR] X 传播 idx=%0d", cnt);
                err = err + 1;
            end
            cnt = cnt + 1;
        end
    end

    initial begin
        wait (rst_n);
        wait (sent == N);
        repeat (8) @(posedge clk);
        if (cnt == N && err == 0)
            $display("[RGB2GRAY] TB_PASS  pixels=%0d", cnt);
        else
            $display("[RGB2GRAY] TB_FAIL  out=%0d/%0d err=%0d", cnt, N, err);
        $finish;
    end

    initial begin
        #200_000_000;
        $display("[RGB2GRAY] TB_FAIL  超时");
        $finish;
    end

endmodule
