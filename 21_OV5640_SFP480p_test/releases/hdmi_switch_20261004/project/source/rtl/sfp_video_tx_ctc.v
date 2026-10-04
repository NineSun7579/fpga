`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company : Meyesemi demo modified
// Module  : sfp_video_tx (CTC-enabled version for 100H RX GE mode)
//
// Description : 将 640x480@60 RGB565 视频流打包为 HSST(8B10B) 串行码流,
//               经 SFP0(光口0, HSST CH2) 发送。
//
// [2026-10-01 CTC FIX] 增加 GE CTC (Clock Tolerance Compensation) 支持:
//   100H RX 配置为 RXPCS_CTC="GE" (千兆以太网模式), 要求 TX 端按 8 拍循环
//   在第 6 拍插入 skip 有序集。本版本修复了原始 sfp_video_tx.v 不符合 GE
//   标准的问题 (回环测试正常但板间通信失败)。
//
// ============================ 链路协议规格 (供接收端实现) =====================
//  链路: HSST CH2, 5Gbps, 8B10B, fabric 接口 32bit @ 125MHz (时钟即 o_p_clk2core_tx_2)。
//  字节序: i_txd_2[7:0] 为线上第一个字节 (byte0), byte3 最后发送。
//  txk[n] 置 1 表示对应字节为 K 码。接收端以 K28.5 (0xBC) 逗号做字对齐,
//  依据 rxk[3:0] 区分字型:
//
//  1) 数据字 (rxk == 4'b0000) -- 携带 2 个有效像素:
//        txd = {pix1[15:0], pix0[15:0]}
//        byte0/1 = 先发像素 pix0 (RGB565: bit15..11=R, bit10..5=G, bit4..0=B)
//        byte2/3 = 后发像素 pix1
//        每收到一个数据字 => de 脉冲有效, 依次输出 pix0、pix1
//
//  2) 控制字 (rxk == 4'b1001) -- 空闲/状态字, 不携带像素:
//        txd = {8'hBC, {1'b0,hs,vs,5'b0}, 8'h28, 8'hBC}
//        byte0 = K28.5 (逗号, 字对齐)
//        byte1 = D28.2 (0x28, 满足 GE 模式 CTC 的 skip 有序集)
//        byte2 = 状态: bit0=vs, bit1=hs (控制字中 de 恒为 0)
//        byte3 = K28.5
//        vs/hs 电平随状态字节连续更新; 消隐期间连续发送控制字。
//
//  3) [NEW] Skip 有序集 (rxk == 4'b0101, GE CTC 每 8 拍第 6 拍强制插入):
//        txd = {D28.2, K28.5, D28.2, K28.5} = 32'h28BC_28BC
//        用于 RX 侧 CTC FIFO 跳变补偿时钟容差, 100H RX 必须接收此序列。
//
//  接收端重构规则: 数据字 => 输出 2 个像素 (de=1); 控制字 => 不输出像素,
//  锁存 vs/hs 电平; skip 有序集 => CTC 处理, 不影响像素流。
//  帧边界以 vs 上升沿为准, 每帧 640x480 有效像素。
// ==============================================================================
//////////////////////////////////////////////////////////////////////////////////
`define UD #1

module sfp_video_tx (
    // 像素域 (25MHz)
    input                    vid_clk        ,   // 像素时钟 (PLL clkout0, 25MHz)
    input                    vid_rst_n      ,
    input  [18:0]            vid_data       ,   // {vs,hs,de,rgb565[15:0]}
    // fabric 域 (125MHz, HSST o_p_clk2core_tx_2)
    input                    fab_clk        ,
    input                    fab_rst_n      ,
    input                    link_ready     ,   // HSST PLL lock & TX lane done (free_clk 域)
    output reg [31:0]        txd            ,   // -> i_txd_2
    output reg [3:0]         txk                // -> i_txk_2
);

    //--------------------------------------------------------------------------
    // 跨时钟域 FIFO: 25M 像素流 -> 125M 打包
    //   empty 为寄存器输出; 只要非空每拍弹出一个字, 与打包决策同拍完成。
    //--------------------------------------------------------------------------
    wire                     fifo_empty;
    wire [18:0]              fifo_rdata;
    wire                     fifo_pop = ~fifo_empty;

    video_async_fifo #(
        .WIDTH (19),
        .DEPTH (512)
    ) u_fifo (
        .wr_clk   (vid_clk      ),
        .wr_rst_n (vid_rst_n    ),
        .wr_en    (1'b1         ),
        .wr_data  (vid_data     ),
        .full     (             ),
        .rd_clk   (fab_clk      ),
        .rd_rst_n (fab_rst_n    ),
        .rd_en    (fifo_pop     ),
        .rd_data  (fifo_rdata   ),
        .empty    (fifo_empty   )
    );

    //--------------------------------------------------------------------------
    // link_ready 两级同步到 fabric 域
    //--------------------------------------------------------------------------
    reg [1:0] ready_sync;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n)
            ready_sync <= `UD 2'b00;
        else
            ready_sync <= `UD {ready_sync[0], link_ready};
    end
    wire tx_go = ready_sync[1];

    //--------------------------------------------------------------------------
    // [CTC FIX] GE 模式 8 拍相位计数器 (每 8 拍第 6 拍插入 skip)
    //--------------------------------------------------------------------------
    reg [2:0] ctc_phase;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n)
            ctc_phase <= `UD 3'd0;
        else if (!tx_go)
            ctc_phase <= `UD 3'd0;
        else
            ctc_phase <= `UD ctc_phase + 3'd1;  // 0..7 循环
    end

    // Skip 有序集: {D28.2, K28.5, D28.2, K28.5} (GE CTC 标准)
    localparam [31:0] SKIP_WORD = 32'h28BC_28BC;
    localparam [3:0]  SKIP_K    = 4'b0101;

    //--------------------------------------------------------------------------
    // 打包状态机
    //   vid_data = {vs,hs,de,pix}: de=1 的像素两两组成数据字;
    //   de=0 的字仅取其 vs/hs 状态发控制字; FIFO 空发空闲控制字。
    //   [CTC FIX] 在 ctc_phase==6 时强制插入 skip, 暂停正常打包一拍。
    //--------------------------------------------------------------------------
    wire head_vs = fifo_rdata[18];
    wire head_hs = fifo_rdata[17];
    wire head_de = fifo_rdata[16];

    reg        pix_pend;                       // 已锁存半个数据字
    reg [15:0] pix0;

    // 控制字: byte3=K28.5, byte2=状态(vs@[21]/hs@[22]), byte1=D28.2, byte0=K28.5
    wire [31:0] ctrl_word = {8'hBC, 1'b0, head_hs, head_vs, 5'b0, 8'h28, 8'hBC};
    wire [3:0]  ctrl_k    = 4'b1001;

    // 空闲字: 携带最近锁存的 vs/hs (避免 FIFO 空时电平毛刺)
    reg  last_vs, last_hs;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n) begin
            last_vs <= 1'b0;
            last_hs <= 1'b0;
        end
        else if (fifo_pop && (ctc_phase != 3'd6)) begin  // [CTC FIX] skip 拍不更新
            last_vs <= `UD head_vs;
            last_hs <= `UD head_hs;
        end
    end
    wire [31:0] idle_word = {8'hBC, 1'b0, last_hs, last_vs, 5'b0, 8'h28, 8'hBC};

    // [CTC FIX] FIFO 弹出控制: skip 拍暂停弹出
    wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);

    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n) begin
            txd        <= `UD idle_word;
            txk        <= `UD 4'b1001;
            pix_pend   <= `UD 1'b0;
            pix0       <= `UD 16'b0;
        end
        else begin
            // [CTC FIX] 相位 6: 强制发送 skip 有序集, 暂停正常打包
            if (ctc_phase == 3'd6) begin
                txd <= `UD SKIP_WORD;
                txk <= `UD SKIP_K;
                // pix_pend 和 pix0 保持不变, 下拍继续处理
            end
            else if (!tx_go) begin
                // 链路未就绪: 只发空闲控制字 (FIFO 侧继续按 empty 弹出丢弃)
                txd <= `UD idle_word;
                txk <= `UD 4'b1001;
                pix_pend <= `UD 1'b0;
            end
            else if (fifo_pop_gated) begin
                if (!pix_pend) begin
                    if (head_de) begin
                        pix_pend <= `UD 1'b1;      // 锁存前半字, 下拍组成数据字
                        pix0     <= `UD fifo_rdata[15:0];
                    end
                    txd <= `UD ctrl_word;          // 期间发控制字(携带 vs/hs)
                    txk <= `UD ctrl_k;
                end
                else begin
                    pix_pend <= `UD 1'b0;          // 数据字发完清零
                    if (head_de) begin
                        txd <= `UD {fifo_rdata[15:0], pix0};  // 数据字: {pix1,pix0}
                        txk <= `UD 4'b0000;
                    end
                    else begin
                        txd <= `UD ctrl_word;
                        txk <= `UD ctrl_k;
                    end
                end
            end
            else begin
                txd <= `UD idle_word;              // FIFO 空: 空闲控制字
                txk <= `UD 4'b1001;
            end
        end
    end

endmodule
