`timescale 1ns/1ps
//============================================================================
// tb_preprocess_top.v : 整链仿真 (含 FIFO 反压 / 旁路 / 4 种模式)
//   +MODE=0..3  色化+白边 / 仅色化 / 仅灰度 / 仅边缘
//   +MODE=9     RAW 旁路 (1:1 全像素)
//   激励: img.mem 全帧; 模式0..3 帧尾补 1 哑像素 (Sobel 上游契约);
//         下游随机 m_ready 反压 -> FIFO 反压 -> 上游 s_ready 保持
//============================================================================
module tb_preprocess_top;

    localparam MAXPIX = 1 << 21;

    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [15:0]       img  [0:MAXPIX-1];
    reg  [15:0]       expm [0:MAXPIX-1];

    integer           W = 64, H = 36, N, NOUT, MODE = 0;
    integer           sent = 0, cnt = 0, err = 0;
    reg               s_valid = 1'b0;
    reg  [15:0]       s_rgb = 16'd0;
    reg               s_frame_sync = 1'b0;
    reg               m_ready = 1'b1;
    wire              s_ready;
    wire [15:0]       m_rgb;
    wire              m_valid, m_frame_sync;
    wire              out_frame_start;
    wire              ev_valid, ev_edge;
    wire [7:0]        ev_center;
    wire              cid_valid;
    wire [1:0]        cid;

    // 寄存器组直连 (默认值与 prep_regs 复位值一致)
    reg               r_bypass = 1'b0;
    reg  [1:0]        r_mode   = 2'd0;
    reg  [11:0]       r_width  = 12'd64;
    reg  [7:0]        r_tsat = 8'd96, r_thue = 8'd64,
                      r_tval = 8'd160, r_tlow = 8'd160;
    reg  [10:0]       r_tedge = 11'd128;

    preprocess_top #(.MAX_WIDTH(1920), .FIFO_DEPTH(512)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_rgb565(s_rgb), .s_valid(s_valid), .s_ready(s_ready),
        .s_frame_sync(s_frame_sync),
        .m_ready(m_ready), .m_rgb565(m_rgb), .m_valid(m_valid),
        .m_frame_sync(m_frame_sync),
        .reg_bypass(r_bypass), .reg_mode(r_mode), .reg_img_width(r_width),
        .reg_thr_sat(r_tsat), .reg_thr_hue(r_thue),
        .reg_thr_val(r_tval), .reg_thr_low(r_tlow), .reg_thr_edge(r_tedge),
        .out_frame_start(out_frame_start),
        .edge_stream_valid(ev_valid), .edge_stream_edge(ev_edge),
        .edge_stream_center(ev_center),
        .color_id_valid(cid_valid), .color_id(cid)
    );

    initial begin
        if (!$value$plusargs("W=%d",    W))    W = 64;
        if (!$value$plusargs("H=%d",    H))    H = 36;
        if (!$value$plusargs("MODE=%d", MODE)) MODE = 0;
        $readmemh("golden/img.mem", img);
        if (MODE == 9) begin
            r_bypass = 1'b1;                          // 旁路模式必须切到 RAW 直通
            $readmemh("golden/exp_bypass.mem", expm);
        end
        else
            $readmemh($sformatf("golden/exp_top_mode%0d.mem", MODE), expm);
        N    = W * H;
        NOUT = (MODE == 9) ? N : (W - 2) * (H - 2);
        r_width = W[11:0];               // DUT 行宽配置必须与激励一致
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);
        s_frame_sync = 1'b1;
        @(posedge clk);
        s_frame_sync = 1'b0;
    end

    //------------------------------------------------------------------
    // 单一驱动进程 (strict valid-only 契约):
    //   s_valid=1 一拍=一个新像素; s_ready=0 期间 valid 必须先归零
    //------------------------------------------------------------------
    wire        need_more     = (MODE == 9) ? (sent <  N) : (sent <= N);
    wire        need_more_nxt = (MODE == 9) ? (sent+1 <  N) : (sent+1 <= N);
    wire [15:0] nxt     = ((sent   == N) && (MODE != 9)) ? 16'hAA55 : img[sent];
    wire [15:0] nxt_aft = ((sent+1 == N) && (MODE != 9)) ? 16'hAA55 : img[sent+1];

    reg  [31:0] start_delay = 20;

    always @(posedge clk) begin
        if (!rst_n || s_frame_sync) begin
            s_valid <= 1'b0;
        end else if (start_delay > 0) begin
            start_delay <= start_delay - 1;
            s_valid     <= 1'b0;
        end else if (s_valid) begin
            sent <= sent + 1;                        // 本拍已消费
            if (need_more_nxt && s_ready) begin
                s_valid <= 1'b1;
                s_rgb   <= nxt_aft;
            end else begin
                s_valid <= 1'b0;                     // 无空间: 回到 idle 等待
            end
        end else if (need_more && s_ready) begin
            s_valid <= 1'b1;
            s_rgb   <= nxt;
        end
    end

    // 下游随机反压 (1/2 概率拉低, 挤压输出 FIFO)
    always @(posedge clk) begin
        m_ready <= ($random & 32'h1) != 0;
    end

    // 反压覆盖统计
    integer stall_cnt = 0;
    always @(posedge clk) begin
        if (rst_n && !s_ready) stall_cnt = stall_cnt + 1;
    end

    // 比对 (仅在握手完成 m_valid && m_ready 时采样, 否则保持会重复计数)
    always @(posedge clk) begin
        if (rst_n && m_valid && m_ready) begin
            if (m_rgb !== expm[cnt]) begin
                if (err < 10)
                    $display("[TOP][ERR] mode=%0d idx=%0d got=%04h exp=%04h",
                             MODE, cnt, m_rgb, expm[cnt]);
                err = err + 1;
            end
            if (m_rgb === 16'bx) begin
                $display("[TOP][ERR] X 传播 idx=%0d", cnt);
                err = err + 1;
            end
            cnt = cnt + 1;
        end
    end

    initial begin
        wait (rst_n);
        wait (sent >= ((MODE == 9) ? N : N + 1));
        wait (cnt == NOUT);              // 等 FIFO 全部排空再判定
        repeat (16) @(posedge clk);
        $display("[TOP] mode=%0d 输出=%0d/%0d err=%0d 反压拍=%0d",
                 MODE, cnt, NOUT, err, stall_cnt);
        if (cnt == NOUT && err == 0 && stall_cnt > 0)
            $display("[TOP] TB_PASS  mode=%0d", MODE);
        else if (cnt == NOUT && err == 0)
            $display("[TOP] TB_PASS(无反压覆盖) mode=%0d", MODE);
        else
            $display("[TOP] TB_FAIL  mode=%0d", MODE);
        $finish;
    end

    initial begin
        #1_000_000_000;
        $display("[TOP] TB_FAIL  超时 mode=%0d sent=%0d cnt=%0d", MODE, sent, cnt);
        $finish;
    end
endmodule
