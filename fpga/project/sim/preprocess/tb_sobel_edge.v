`timescale 1ns/1ps
//============================================================================
// tb_sobel_edge.v : Sobel 边缘单元仿真
//   激励: golden/exp_gray.mem 全帧灰度 (按栅格流入) + 帧尾 1 哑像素
//         (上游契约: 每帧 H*W+1 像素, 使最后一列内部窗口完成)
//   比对: m_edge vs exp_edge.mem, m_center vs exp_center.mem (内部像素序列)
//============================================================================
module tb_sobel_edge;

    localparam MAXPIX = 1 << 21;

    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [7:0]        gray_in [0:MAXPIX-1];
    reg  [7:0]        expc    [0:MAXPIX-1];
    reg  [7:0]        expe    [0:MAXPIX-1];

    integer           W = 64, H = 36, N, NOUT;
    integer           sent = 0, cnt = 0, err = 0, hit_edge = 0;
    integer           stall;
    integer           fd_edge, fd_center;   // HW output dump -> golden/hw_out_{edge,center}.mem
    reg               s_valid = 1'b0;
    reg  [7:0]        s_gray = 8'd0;
    reg               s_frame_sync = 1'b0;
    wire              m_edge;
    wire [7:0]        m_center;
    wire              m_valid;

    sobel_edge #(.MAX_WIDTH(1920)) dut (
        .clk(clk), .rst_n(rst_n),
        .img_width(W[11:0]), .thr_edge(11'd128),
        .s_gray(s_gray), .s_valid(s_valid), .s_frame_sync(s_frame_sync),
        .m_edge(m_edge), .m_center(m_center), .m_valid(m_valid)
    );

    initial begin
        if (!$value$plusargs("W=%d", W)) W = 64;
        if (!$value$plusargs("H=%d", H)) H = 36;
        $readmemh("golden/exp_gray.mem",  gray_in);
        $readmemh("golden/exp_center.mem", expc);
        $readmemh("golden/exp_edge.mem",   expe);
        fd_edge   = $fopen("golden/hw_out_edge.mem", "w");
        fd_center = $fopen("golden/hw_out_center.mem", "w");
        N    = W * H;
        NOUT = (W - 2) * (H - 2);
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);
        s_frame_sync = 1'b1;
        @(posedge clk);
        s_frame_sync = 1'b0;
    end

    // 激励: 全帧 N+1 像素 (含帧尾哑像素), 随机间隔
    // start_delay 保证 frame_sync 先于数据 (计数器清零先于首像素)
    wire [31:0] nxt_idx = sent + (s_valid ? 1 : 0);
    reg  [31:0] start_delay = 20;
    always @(posedge clk) begin
        if (!rst_n) begin
            s_valid <= 1'b0;
        end else if (start_delay > 0) begin
            start_delay <= start_delay - 1;
            s_valid     <= 1'b0;
        end else if (!s_frame_sync) begin
            stall = $random;
            s_valid <= (nxt_idx <= N) && ((stall & 32'h3) != 0);
            if (s_valid) sent <= sent + 1;
            if (nxt_idx <= N) s_gray <= (nxt_idx == N) ? 8'hAA : gray_in[nxt_idx];
        end
    end

    always @(posedge clk) begin
        if (rst_n && m_valid) begin
            if (m_edge !== expe[cnt][0] || m_center !== expc[cnt]) begin
                if (err < 10) begin
                    $display("[SOBEL][ERR] idx=%0d got=e%0d/c%02h exp=e%0d/c%02h",
                             cnt, m_edge, m_center, expe[cnt][0], expc[cnt]);
                end
                err = err + 1;
            end
            $fwrite(fd_edge,   "%01h
", m_edge);
            $fwrite(fd_center, "%02h
", m_center);
            if (m_edge) hit_edge = hit_edge + 1;
            cnt = cnt + 1;
        end
    end

    initial begin
        wait (rst_n);
        wait (sent == N + 1);
        repeat (8) @(posedge clk);
        $display("[SOBEL] 覆盖: 边缘命中=%0d/%0d", hit_edge, cnt);
        $fclose(fd_edge); $fclose(fd_center);
        if (cnt == NOUT && err == 0)
            $display("[SOBEL] TB_PASS  outputs=%0d", cnt);
        else
            $display("[SOBEL] TB_FAIL  out=%0d/%0d err=%0d", cnt, NOUT, err);
        $finish;
    end

    initial begin
        #500_000_000;
        $display("[SOBEL] TB_FAIL  超时");
        $finish;
    end

endmodule
