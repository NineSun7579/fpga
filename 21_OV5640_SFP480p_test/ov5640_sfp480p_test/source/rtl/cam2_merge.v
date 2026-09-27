`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company : Meyesemi demo modified
// Module  : cam2_merge
// Description : 双目摄像头逐行拼接 (参考 fpga/git 工程的 "每摄 CDC FIFO + 公共快域" 架构):
//   CMOS1(A)/CMOS2(B) 各自 42MHz 像素域 -> 独立异步 FIFO -> 公共快时钟域 o_clk
//   (建议接 DDR core_clk 100MHz, 快于 2x 像素时钟)。
//   公共域内 A/B 各两块行缓存乒乓, 状态机严格交替输出:
//     合成行 = A 行 640 拍 + 间隙 + B 行 640 拍, 行内 de 连续, 行间有间隙,
//   满足 fram_buf 写侧 x_cnt/y_cnt 要求。消费在快域进行, 永远快于生产,
//   不存在追赶/跳行; 双摄时钟频差由 FIFO+乒乓自然吸收。
//   B 侧每帧只投递前 LINES 个有效行, 防止频差累积。
//////////////////////////////////////////////////////////////////////////////////
`define UD #1

module cam2_merge #(
    parameter LINE_PIX = 12'd640,                 // 单路行有效像素
    parameter LINES    = 12'd480                  // 每帧行数
)(
    // A 路域 (cmos1_pclk_16bit, 42MHz)
    input                    a_clk               ,
    input                    a_rst_n             ,
    input  [15:0]            a_data              ,// RGB565 (raw, 原序)
    input                    a_de                ,
    input                    a_vs                ,
    // B 路域 (cmos2_pclk_16bit, 42MHz)
    input                    b_clk               ,
    input                    b_rst_n             ,
    input  [15:0]            b_data              ,
    input                    b_de                ,
    input                    b_vs                ,
    // 输出域 (o_clk, 快时钟, 建议 DDR core_clk 100MHz)
    input                    o_clk               ,
    input                    o_rst_n             ,
    output reg [15:0]        c_data              ,
    output reg               c_de                ,
    output reg                c_vs
);
    //--------------------------------------------------------------------------
    // 输入寄存 (时序裕量) + RGB565 通道重排 {B,G,R}->{R,G,B}
    //--------------------------------------------------------------------------
    reg  [15:0] a_data_r;
    reg         a_de_r;
    reg  [15:0] b_data_r;
    reg         b_de_r;

    always @(posedge a_clk or negedge a_rst_n) begin
        if (!a_rst_n) begin
            a_data_r <= `UD 16'd0;
            a_de_r   <= `UD 1'b0;
        end
        else begin
            a_data_r <= `UD {a_data[4:0],a_data[10:5],a_data[15:11]};
            a_de_r   <= `UD a_de;
        end
    end

    always @(posedge b_clk or negedge b_rst_n) begin
        if (!b_rst_n) begin
            b_data_r <= `UD 16'd0;
            b_de_r   <= `UD 1'b0;
        end
        else begin
            b_data_r <= `UD {b_data[4:0],b_data[10:5],b_data[15:11]};
            b_de_r   <= `UD b_de;
        end
    end

    //--------------------------------------------------------------------------
    // B 域: 每帧只投递前 LINES 个有效行
    //--------------------------------------------------------------------------
    reg  [11:0]  b_line_cnt;
    reg          b_de_1d;
    wire         b_line_start = b_de_r & ~b_de_1d;

    always @(posedge b_clk or negedge b_rst_n) begin
        if (!b_rst_n) begin
            b_line_cnt <= `UD 12'd0;
            b_de_1d    <= `UD 1'b0;
        end
        else begin
            b_de_1d <= `UD b_de_r;
            if (b_vs)
                b_line_cnt <= `UD 12'd0;
            else if (b_line_start)
                b_line_cnt <= `UD b_line_cnt + 12'd1;
        end
    end

    wire b_push = b_de_r & (b_line_cnt < LINES);

    //--------------------------------------------------------------------------
    // 每摄异步 FIFO -> o_clk 公共域
    //   载荷 17bit: {eol, pix}. 像素拍 {0,pix}; 行尾 (de 下降沿) 推 {1,0}.
    //   消费端靠 EOL 显式分行, 不依赖 FIFO 空判定 (快域消费时行中会瞬时见底).
    //--------------------------------------------------------------------------
    wire        afifo_empty, bfifo_empty;
    wire [16:0] afifo_rdata, bfifo_rdata;
    wire        apop, bpop;

    reg a_de_d, b_push_d;
    always @(posedge a_clk or negedge a_rst_n) begin
        if (!a_rst_n) a_de_d <= `UD 1'b0; else a_de_d <= `UD a_de_r;
    end
    always @(posedge b_clk or negedge b_rst_n) begin
        if (!b_rst_n) b_push_d <= `UD 1'b0; else b_push_d <= `UD b_push;
    end
    wire a_push_eol = a_de_d & ~a_de_r;
    wire b_push_eol = b_push_d & ~b_push;

    video_async_fifo #(.WIDTH(17), .DEPTH(1024)) u_afifo (
        .wr_clk(a_clk), .wr_rst_n(a_rst_n),
        .wr_en(a_de_r | a_push_eol), .wr_data({a_push_eol, a_data_r}), .full(),
        .rd_clk(o_clk), .rd_rst_n(o_rst_n),
        .rd_en(apop), .rd_data(afifo_rdata), .empty(afifo_empty)
    );

    video_async_fifo #(.WIDTH(17), .DEPTH(1024)) u_bfifo (
        .wr_clk(b_clk), .wr_rst_n(b_rst_n),
        .wr_en(b_push | b_push_eol), .wr_data({b_push_eol, b_data_r}), .full(),
        .rd_clk(o_clk), .rd_rst_n(o_rst_n),
        .rd_en(bpop), .rd_data(bfifo_rdata), .empty(bfifo_empty)
    );

    //--------------------------------------------------------------------------
    // 合成输出状态机编码与帧计数
    //   严格 A/B 交替; 每完成 LINES 对行进入 S_VSYNC 自产帧同步
    //   (与摄像头 vsync 解耦, 帧界不因 B 消隐截断)。
    //   S_WAIT_B 超时 (WTO_RELOAD) 重挂当前 B 页 = 重复上一 B 行,
    //   B 消隐/相位漂移期不阻塞 A。
    //--------------------------------------------------------------------------
    localparam S_WAIT_A = 3'd0,
               S_RD_A   = 3'd1,
               S_GAP_AB = 3'd2,
               S_WAIT_B = 3'd3,
               S_RD_B   = 3'd4,
               S_GAP_BA = 3'd5,
               S_VSYNC  = 3'd6,
               S_COPY   = 3'd7;
    reg  [2:0]  state;
    reg  [1:0]  gap_cnt;
    reg  [12:0] pair_cnt;
    reg  [12:0] wto_cnt;
    localparam WTO_RELOAD = 13'd2400;             // ~24us(一行) @100MHz
    reg         b_ever;                           // B 曾产出过整行 (防误重挂)
    reg         b_rep;                            // B 干涸重复指示
    reg  [1:0]  b_vs_sync;                        // b_vs 两级同步 (识别 B 消隐)
    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n) b_vs_sync <= `UD 2'b00;
        else          b_vs_sync <= `UD {b_vs_sync[0], b_vs};
    end

    //--------------------------------------------------------------------------
    // 公共域行捕获: A/B 各两块行缓存乒乓
    //   填充: FIFO 非空即弹; 像素写缓存; EOL 令牌时整行(计满)结页, 残行丢弃。
    //   消费与填充同域不同页, 互不干扰。
    //--------------------------------------------------------------------------
    reg [15:0] a_mem0 [0:LINE_PIX-1];
    reg [15:0] a_mem1 [0:LINE_PIX-1];
    reg [15:0] b_mem0 [0:LINE_PIX-1];
    reg [15:0] b_memL [0:LINE_PIX-1];              // 最后消费行的快照
    reg [15:0] b_mem1 [0:LINE_PIX-1];

    reg        a_ready [0:1];
    reg        b_ready [0:1];
    reg        a_page, b_page;                    // 正在填充的页
    reg        a_cur, b_cur;                      // 待消费的页
    reg [10:0] a_fcnt, b_fcnt;
    reg [10:0] a_rcnt, b_rcnt;

    wire aconsume = (state == S_RD_A) & (a_rcnt == LINE_PIX - 11'd1);
    wire bconsume = (state == S_RD_B) & (b_rcnt == LINE_PIX - 11'd1);
    wire afill_en = ~a_ready[a_page];             // 当前填充页未就绪才可写
    assign apop   = ~afifo_empty & afill_en;
    wire bfill_en = ~b_ready[b_page];
    assign bpop   = ~bfifo_empty & bfill_en;

    // A 填充与结页
    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n) begin
            a_fcnt     <= `UD 11'd0;
            a_page     <= `UD 1'b0;
            a_ready[0] <= `UD 1'b0;
            a_ready[1] <= `UD 1'b0;
        end
        else begin
            if (aconsume)
                a_ready[a_cur] <= `UD 1'b0;
            if (apop) begin
                if (afifo_rdata[16]) begin            // EOL: 行结束
                    if (a_fcnt == LINE_PIX) begin
                        a_ready[a_page] <= `UD 1'b1;  // 整行有效, 结页
                        a_page          <= `UD ~a_page;
                    end
                    a_fcnt <= `UD 11'd0;              // 残行丢弃
                end
                else begin
                    if (a_page) a_mem1[a_fcnt[9:0]] <= `UD afifo_rdata[15:0];
                    else        a_mem0[a_fcnt[9:0]] <= `UD afifo_rdata[15:0];
                    a_fcnt <= `UD a_fcnt + 11'd1;
                end
            end
        end
    end

    // B 填充与结页
    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n) begin
            b_fcnt     <= `UD 11'd0;
            b_page     <= `UD 1'b0;
            b_ready[0] <= `UD 1'b0;
            b_ready[1] <= `UD 1'b0;
        end
        else begin
            if (bconsume)
                b_ready[b_cur] <= `UD 1'b0;
            if (bpop) begin
                if (bfifo_rdata[16]) begin            // EOL: 行结束
                    if (b_fcnt == LINE_PIX) begin
                        b_ready[b_page] <= `UD 1'b1;
                        b_page          <= `UD ~b_page;
                    end
                    b_fcnt <= `UD 11'd0;
                end
                else begin
                    if (b_page) b_mem1[b_fcnt[9:0]] <= `UD bfifo_rdata[15:0];
                    else        b_mem0[b_fcnt[9:0]] <= `UD bfifo_rdata[15:0];
                    b_fcnt <= `UD b_fcnt + 11'd1;
                end
            end
        end
    end

    //--------------------------------------------------------------------------
    // 合成输出状态机 (o_clk, 严格 A/B 交替; 快域消费, 由生产节拍定速)
    //   WAIT_A -> RD_A -> GAP_AB -> (WAIT_B) -> RD_B -> GAP_BA -> WAIT_A
    // 干涸判定: 距上次 B 整行完成超过 ~26us (一行 23.8us + 裕量) 即认为 B 消隐,
    // 用 64 拍短超时快速重复; 正常行间等待用 30us 长超时兜底。
    reg  [12:0] since_beol;
    wire        b_page_done = bpop & bfifo_rdata[16] & (b_fcnt == LINE_PIX);
    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n)            since_beol <= `UD 13'd0;
        else if (b_page_done)    since_beol <= `UD 13'd0;
        else                     since_beol <= `UD since_beol + 13'd1;
    end
    wire [12:0] wto_th = (since_beol > 13'd2600) ? 13'd64 : 13'd3000;

    //--------------------------------------------------------------------------
    // 行数据选择 (B 干涸重复时读快照 b_memL)
    always @(posedge o_clk) begin
        if (state == S_RD_A) begin
            if (a_cur) c_data <= `UD a_mem1[a_rcnt[9:0]];
            else       c_data <= `UD a_mem0[a_rcnt[9:0]];
        end
        else if (state == S_RD_B) begin
            if (b_rep)      c_data <= `UD b_memL[b_rcnt[9:0]];
            else if (b_cur) c_data <= `UD b_mem1[b_rcnt[9:0]];
            else            c_data <= `UD b_mem0[b_rcnt[9:0]];
        end
    end

    reg [9:0] cpy_cnt;
    reg       cpy_src;

    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n) begin
            c_de     <= `UD 1'b0;
            c_vs     <= `UD 1'b0;
            gap_cnt  <= `UD 2'd0;
            a_rcnt   <= `UD 11'd0;
            b_rcnt   <= `UD 11'd0;
            a_cur    <= `UD 1'b0;
            b_cur    <= `UD 1'b0;
            pair_cnt <= `UD 13'd0;
            wto_cnt  <= `UD 13'd0;
            b_rep    <= `UD 1'b0;
            cpy_cnt  <= `UD 10'd0;
            cpy_src  <= `UD 1'b0;
            state    <= `UD S_WAIT_A;
        end
        else begin
            case (state)
            S_WAIT_A: begin
                c_de <= `UD 1'b0;
                if (a_ready[a_cur]) begin
                    a_rcnt <= `UD 11'd0;
                    state  <= `UD S_RD_A;
                end
            end
            S_RD_A: begin
                c_de   <= `UD 1'b1;
                a_rcnt <= `UD a_rcnt + 11'd1;
                if (a_rcnt == LINE_PIX - 11'd1) begin
                    a_cur   <= `UD ~a_cur;
                    gap_cnt <= `UD 2'd0;
                    state   <= `UD S_GAP_AB;
                end
            end
            S_GAP_AB: begin
                c_de    <= `UD 1'b0;
                gap_cnt <= `UD gap_cnt + 2'd1;
                if (gap_cnt == 2'd3) begin
                    if (b_ready[b_cur]) begin
                        b_rcnt  <= `UD 11'd0;
                        b_rep   <= `UD 1'b0;
                        state   <= `UD S_RD_B;
                    end
                    else begin
                        wto_cnt <= `UD 13'd0;
                        state   <= `UD S_WAIT_B;
                    end
                end
            end
            S_WAIT_B: begin
                c_de <= `UD 1'b0;
                if (b_ready[b_cur]) begin
                    b_rcnt  <= `UD 11'd0;
                    b_rep   <= `UD 1'b0;
                    state   <= `UD S_RD_B;
                end
                else if (b_ever & (wto_cnt >= wto_th)) begin
                    // B 干涸 (B 消隐/相位漂移): 读最后行快照, 不阻塞 A
                    b_rcnt  <= `UD 11'd0;
                    b_rep   <= `UD 1'b1;
                    wto_cnt <= `UD 13'd0;
                    state   <= `UD S_RD_B;
                end
                else begin
                    wto_cnt <= `UD wto_cnt + 13'd1;
                end
            end
            S_RD_B: begin
                c_de   <= `UD 1'b1;
                b_rcnt <= `UD b_rcnt + 11'd1;
                if (b_rcnt == LINE_PIX - 11'd1) begin
                    gap_cnt <= `UD 2'd0;
                    if (!b_rep) begin
                        b_cur  <= `UD ~b_cur;
                        cpy_src<= `UD b_cur;        // 快照刚消费的行
                        cpy_cnt<= `UD 10'd0;
                        state  <= `UD S_COPY;       // 拷贝到 b_memL
                    end
                    else begin
                        if (pair_cnt == LINES - 13'd1)
                            state <= `UD S_VSYNC;   // 一帧 480 对完成
                        else begin
                            pair_cnt <= `UD pair_cnt + 13'd1;
                            state    <= `UD S_GAP_BA;
                        end
                    end
                end
            end
            S_COPY: begin
                // 把刚消费的 B 行快照到 b_memL (640 拍, 供干涸时重复)
                c_de <= `UD 1'b0;
                if (cpy_src) b_memL[cpy_cnt] <= b_mem1[cpy_cnt];
                else         b_memL[cpy_cnt] <= b_mem0[cpy_cnt];
                if (cpy_cnt == LINE_PIX - 10'd1) begin
                    cpy_cnt <= `UD 10'd0;
                    if (pair_cnt == LINES - 13'd1)
                        state <= `UD S_VSYNC;       // 一帧 480 对完成
                    else begin
                        pair_cnt <= `UD pair_cnt + 13'd1;
                        state    <= `UD S_GAP_BA;
                    end
                end
                else begin
                    cpy_cnt <= `UD cpy_cnt + 10'd1;
                end
            end
            S_GAP_BA: begin
                c_de    <= `UD 1'b0;
                gap_cnt <= `UD gap_cnt + 2'd1;
                if (gap_cnt == 2'd3)
                    state <= `UD S_WAIT_A;
            end
            S_VSYNC: begin
                // 自产帧同步: 每完成 LINES 对行输出一个 vsync 脉冲
                c_vs    <= `UD 1'b1;
                c_de    <= `UD 1'b0;
                gap_cnt <= `UD gap_cnt + 2'd1;
                if (gap_cnt == 2'd3) begin
                    c_vs    <= `UD 1'b0;
                    pair_cnt<= `UD 13'd0;
                    gap_cnt <= `UD 2'd0;
                    state   <= `UD S_WAIT_A;
                end
            end
            default: state <= `UD S_WAIT_A;
            endcase
        end
    end

    //--------------------------------------------------------------------------
    // B 曾产出过整行标志 (干涸重复的前提, 防上电初期读空快照)
    //--------------------------------------------------------------------------
    always @(posedge o_clk or negedge o_rst_n) begin
        if (!o_rst_n)
            b_ever <= `UD 1'b0;
        else if (bpop & bfifo_rdata[16] & (b_fcnt == LINE_PIX))
            b_ever <= `UD 1'b1;
    end

endmodule
