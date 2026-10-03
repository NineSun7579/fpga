`timescale 1ns / 1ps
//===========================================================================
//  tb_sfp_link.v -- SFP 光口链路仿真: sfp_video_tx -> 行为信道(CTC 删/插)
//                   -> sfp_video_rx -> 黄金帧逐像素比对
//
//  覆盖点:
//    1) 数据字/控制字协议: 像素序列与 vs/hs 电平严格保序
//    2) CTC 压力: 控制字随机删除/复制 (P_DEL/P_DUP), 数据字绝不丢失
//    3) 帧边界: vs 上升沿时上一帧黄金像素必须恰好比对完
//    4) TX Rev3.1fix1(pix_pend 滚动) / fix2(idle 携带 vs/hs) 回归
//
//  判定: 打印 TB_PASS / TB_FAIL(n)
//===========================================================================
module tb_sfp_link;

    localparam W      = 160;      // 有效列 (偶数, 协议与行宽无关)
    localparam H      = 60;       // 有效行
    localparam BLANK  = 40;       // 行消隐拍数 (vid 域)
    localparam VSW    = 2;        // vs 高电平行数 (帧头)
    localparam VBLANK = 4;        // 帧尾消隐行
    localparam NFRAME = 3;
    localparam P_DEL  = 15;       // 控制字删除概率 %
    localparam P_DUP  = 15;       // 控制字复制概率 %

    //-----------------------------------------------------------------------
    // 时钟 / 复位 / 链路
    //-----------------------------------------------------------------------
    reg vid_clk = 0;
    reg fab_clk = 0;
    always #27.0134 vid_clk = ~vid_clk;    // 37.125MHz
    always #4.0    fab_clk = ~fab_clk;     // 125MHz

    reg vid_rst_n = 0, fab_rst_n = 0, link_ready = 0;
    initial begin
        #200  vid_rst_n = 1;
               fab_rst_n = 1;
        #500  link_ready = 1;
    end

    //-----------------------------------------------------------------------
    // 视频发生器 (vid 域): vs 脉冲 -> H 有效行 -> 帧尾消隐, 循环 NFRAME 帧
    //-----------------------------------------------------------------------
    reg [18:0] vid_data;
    reg        vs, hs, de;
    reg [15:0] pix;
    reg [1:0]  fst;      // 0=vs期 1=有效行 2=帧尾 3=停止(跑满 NFRAME 后静止)
    integer    frame, ly, x;

    function [15:0] mkpix(input integer f, input integer yy, input integer xx);
        mkpix = (f * 16'h1000 + yy * 16'h40 + xx) & 16'hFFFF;
    endfunction

    initial begin
        fst = 0; ly = 0; x = 0; frame = 0;
        vs = 0; hs = 0; de = 0; pix = 0;
    end

    always @(posedge vid_clk or negedge vid_rst_n) begin
        if (!vid_rst_n) begin
            fst <= 0; ly <= 0; x <= 0; frame <= 0;
            vs <= 0; hs <= 0; de <= 0; pix <= 0;
        end
        else begin
            vs <= 0; hs <= 0; de <= 0;
            case (fst)
            0: begin
                vs <= 1;
                x <= x + 1;
                if (x >= W + BLANK - 1) begin        // vs 期按行推进
                    x <= 0;
                    if (ly >= VSW-1) begin fst <= 1; ly <= 0; end
                    else ly <= ly + 1;
                end
            end
            1: begin
                hs <= 1;
                if (x < W) begin
                    de <= 1;
                    pix <= mkpix(frame, ly, x);
                    x <= x + 1;
                end
                else begin
                    x <= x + 1;
                    if (x >= W + BLANK - 1) begin
                        x <= 0;
                        if (ly >= H-1) begin fst <= 2; ly <= 0; end
                        else ly <= ly + 1;
                    end
                end
            end
            2: begin
                if (ly >= VBLANK-1) begin
                    ly <= 0;
                    if (frame >= NFRAME-1) fst <= 3;      // 跑满即停
                    else begin fst <= 0; frame <= frame + 1; end
                end
                else ly <= ly + 1;
            end
            3: begin /* 停止态: 全消隐 */ end
            endcase
        end
    end

    always @(posedge vid_clk) vid_data <= {vs, hs, de, pix};

    //-----------------------------------------------------------------------
    // 黄金像素采集 (vid 域, 与 TX FIFO 写入同一拍同一数据)
    //-----------------------------------------------------------------------
    reg [15:0] golden [0:NFRAME*W*H-1];
    integer    gwr = 0;
    always @(posedge vid_clk) begin
        if (vid_rst_n && link_ready && vid_data[16]) begin
            if (gwr < NFRAME*W*H) golden[gwr] <= vid_data[15:0];
            gwr <= gwr + 1;
        end
    end

    //-----------------------------------------------------------------------
    // DUT: 发送端
    //-----------------------------------------------------------------------
    wire [31:0] txd;
    wire [3:0]  txk;

    sfp_video_tx u_tx (
        .vid_clk   (vid_clk),
        .vid_rst_n (vid_rst_n),
        .vid_data  (vid_data),
        .fab_clk   (fab_clk),
        .fab_rst_n (fab_rst_n),
        .link_ready(link_ready),
        .txd       (txd),
        .txk       (txk)
    );

    //-----------------------------------------------------------------------
    // 行为信道 (fab 域): 8 深队列, 控制字按概率删/复制, 数据字恒透传
    //-----------------------------------------------------------------------
    reg [31:0] qd [0:7];
    reg [3:0]  qk [0:7];
    integer    qn = 0;          // 队列深度
    integer    qh = 0;          // 队头索引 (mod 8)
    reg [31:0] rxd;
    reg [3:0]  rxk;
    integer    seed = 100;
    integer    r, n_del = 0, n_dup = 0;

    always @(posedge fab_clk) begin
        if (!fab_rst_n) begin
            qn <= 0; qh <= 0;
            rxd <= 32'hBC0028BC; rxk <= 4'b1001;
        end
        else begin
            // ---- 出队 (1 字/拍) ----
            if (qn > 0) begin
                rxd <= qd[qh % 8];
                rxk <= qk[qh % 8];
                qh <= qh + 1;
                qn <= qn - 1;
            end
            else begin
                rxd <= 32'hBC0028BC; rxk <= 4'b1001;   // 信道建立期 idle
            end

            // ---- 入队决策 (采样本拍 TX 输出的边沿前值) ----
            // 删字仅在队列有积压时发生 (模拟真实 PCS 弹性缓冲: 缓冲非空才删, 不留空隙)
            // 复制在队列 <6 时才做 (防止 8 深队列回卷碰撞)
            r = ({$random(seed)} % 100);
            if (txk == 4'b1001 && r < P_DEL && qn >= 2) begin
                n_del = n_del + 1;                     // 丢弃该控制字
            end
            else if (txk == 4'b1001 && r < P_DEL + P_DUP && qn < 6) begin
                n_dup = n_dup + 1;                     // 复制一次
                qd[(qh + qn) % 8] <= txd;  qk[(qh + qn) % 8] <= txk;
                qd[(qh + qn + 1) % 8] <= txd; qk[(qh + qn + 1) % 8] <= txk;
                qn <= qn + 2 - (qn > 0 ? 1 : 0);
            end
            else begin
                qd[(qh + qn) % 8] <= txd;  qk[(qh + qn) % 8] <= txk;
                qn <= qn + 1 - (qn > 0 ? 1 : 0);
            end
        end
    end

    //-----------------------------------------------------------------------
    // DUT: 接收端
    //-----------------------------------------------------------------------
    wire        rx_en = fab_rst_n & link_ready;
    wire        o_vs, o_hs, o_de, o_overflow;
    wire [15:0] o_pix;

    sfp_video_rx u_rx (
        .i_clk     (fab_clk),
        .i_rst_n   (fab_rst_n),
        .i_en      (rx_en),
        .i_rxd     (rxd),
        .i_rxk     (rxk),
        .o_vs      (o_vs),
        .o_hs      (o_hs),
        .o_de      (o_de),
        .o_pix     (o_pix),
        .o_overflow(o_overflow)
    );

    //-----------------------------------------------------------------------
    // 检查器 (fab 域, 采样 RX 寄存器输出的边沿前值)
    //-----------------------------------------------------------------------
    integer cmp_idx  = 0;
    integer frame_chk = -1;     // 当前比对帧号, vs 上升沿 +1
    integer err      = 0;
    reg     vs_q = 0;
    integer done_cnt = 0;
    integer stray   = 0;   // 杂散像素计数(首帧前)
    reg     finished = 0;

    always @(posedge fab_clk) begin
        if (fab_rst_n && rx_en && !finished) begin
            // vs 上升沿: 帧边界完整性
            if (o_vs && !vs_q) begin
                if (frame_chk >= 0 && cmp_idx != W*H) begin
                    err = err + 1;
                    $display("[%0t] FRAME_LEN_ERR frame=%0d got=%0d exp=%0d",
                             $time, frame_chk, cmp_idx, W*H);
                end
                cmp_idx   <= 0;
                frame_chk <= frame_chk + 1;
            end
            vs_q <= o_vs;

            // 像素比对 (首帧 vs 上升沿之前的杂散像素静默丢弃: 链路建立时序
            // 允许第一帧不完整, golden 对齐从第一个 vs 上升沿开始)
            if (o_de) begin
                if (frame_chk < 0) begin
                    stray = stray + 1;
                end
                else if (frame_chk >= NFRAME) begin
                    err = err + 1;
                    $display("[%0t] DE_OUT_OF_FRAME frame=%0d", $time, frame_chk);
                end
                else if (cmp_idx >= W*H) begin
                    err = err + 1;
                    $display("[%0t] PIX_OVERFLOW frame=%0d idx=%0d", $time, frame_chk, cmp_idx);
                end
                else if (o_pix !== golden[frame_chk*W*H + cmp_idx]) begin
                    err = err + 1;
                    if (err < 20)
                        $display("[%0t] PIX_MISMATCH frame=%0d idx=%0d got=%04h exp=%04h",
                                 $time, frame_chk, cmp_idx, o_pix, golden[frame_chk*W*H + cmp_idx]);
                end
                if (cmp_idx < W*H) cmp_idx <= cmp_idx + 1;
            end

            if (o_overflow) begin
                err = err + 1;
                $display("[%0t] RX_FIFO_OVERFLOW", $time);
            end

            // 最后一帧像素比对完即进入收卷 (不再有下一次 vs 上升)
            if (frame_chk >= NFRAME-1 && cmp_idx >= W*H) begin
                done_cnt <= done_cnt + 1;
                if (done_cnt >= 1250) begin
                    finished = 1;
                end
            end
        end
    end

    //-----------------------------------------------------------------------
    // 汇总 / 看门狗
    //-----------------------------------------------------------------------
    always @(posedge fab_clk) begin
        if (finished && err == 0) begin
            $display("golden_pixels=%0d frames_done=%0d stray=%0d ctrl_del=%0d ctrl_dup=%0d",
                     gwr, NFRAME, stray, n_del, n_dup);
            $display("TB_PASS");
            $finish;
        end
        else if (finished && err > 0) begin
            $display("TB_FAIL err=%0d (golden=%0d frames=%0d del=%0d dup=%0d)",
                     err, gwr, frame_chk, n_del, n_dup);
            $finish;
        end
    end

    initial begin
        #10_000_000;   // 10ms 看门狗
        $display("TB_FAIL_TIMEOUT frame_chk=%0d cmp_idx=%0d gwr=%0d err=%0d",
                 frame_chk, cmp_idx, gwr, err);
        $finish;
    end

endmodule
