`timescale 1ns/1ps
//============================================================================
// vip_kf.v -- adaptive temporal (inter-frame) simplified Kalman / IIR filter
//
// 对每个像素位置 (row,col) 做逐通道时域递归, 相当于"稳态卡尔曼"的简化:
//
//     K = P / (P + R)            (卡尔曼增益, 由过程/测量噪声比决定)
//     out = x + K * (z - x)      (状态更新, x=上一帧滤波值, z=本帧输入)
//
// 本实现把 K 量化为 4 档, 由"新息" |z-x| 与阈值 THR0/THR1/THR2 比较选择 --
// 新息大 => 目标在动/边缘 => 提高 K (快速跟随, 防拖影);
// 新息小 => 静止/平坦区   => 降低 K (强平滑, 降噪).
//
//     d < THR0 : K=1/4  -> out = (3*x + z) >> 2   (强平滑)
//     d < THR1 : K=1/2  -> out = (x + z)   >> 1
//     d < THR2 : K=3/4  -> out = (x + 3*z) >> 2   (弱平滑)
//     else     : K=1    -> out = z                (完全跟随)
//
// R[4:0] / G[5:0] / B[4:0] 三通道各自独立运算, 结果打包成 RGB565.
// 所有运算为无符号整数/移位, 位精确可复现 (无乘除, 无浮点).
//
// 帧契约:
//   * in_pixel 为 RGB565, 每帧 W*H 个有效像素, in_vsync 为该帧首标志脉冲.
//   * 首帧 (frame_seen==0) 为 passthrough: 直接输出输入, 同时写入帧存,
//     用于建立时域状态, 避免与未初始化帧存混合.
//   * en=0 时纯旁路 (不做时域滤波), 仍写回原值.
//   * 上一帧通过 prev_raddr/prev_ren 以光栅序读出, 期望 prev_rdata 在
//     LAT 拍后有效 (与外部同步 RAM 的读延迟一致).
//   * 滤波结果除输出流外, 同时由 wr_en/wr_addr/wr_data 写回帧存,
//     作为下一帧的 x. (乒乓由外部帧存管理, 本模块不感知 bank.)
//
// 注: 本模块不反压输入; 输入须在有效像素期每拍一个 (与 vip 输出契约一致).
//============================================================================
module vip_kf #(
    parameter integer W    = 640,
    parameter integer H    = 480,
    parameter integer AW   = 19,   // $clog2(W*H)
    parameter integer LAT  = 1     // 帧存读延迟(拍), 同步 RAM 通常为 1
)(
    input  wire          clk,
    input  wire          rst,

    input  wire          en,          // 1=时域滤波, 0=旁路
    input  wire [5:0]    thr0,        // K=1/4 上界 (新息门限)
    input  wire [5:0]    thr1,        // K=1/2 上界
    input  wire [5:0]    thr2,        // K=3/4 上界

    // 本帧相机像素流
    input  wire          in_valid,
    input  wire [15:0]   in_pixel,
    input  wire          in_vsync,

    // 上一帧(滤波结果)读出: 光栅序, 读延迟 LAT
    output wire          prev_ren,
    output wire [AW-1:0] prev_raddr,
    input  wire [15:0]   prev_rdata,

    // 滤波输出流
    output reg           out_valid,
    output reg  [15:0]   out_pixel,
    output reg           out_vsync,

    // 滤波结果写回帧存 (下一帧的 x)
    output reg           wr_en,
    output reg  [AW-1:0] wr_addr,
    output reg  [15:0]   wr_data
);

    //------------------------------------------------------------------
    // 对齐流水 regs (先声明, 供后续逻辑使用)
    //------------------------------------------------------------------
    reg [15:0]   p_pix [0:LAT-1];
    reg [AW-1:0] p_idx [0:LAT-1];
    reg          p_val [0:LAT-1];
    reg          p_vs  [0:LAT-1];

    //------------------------------------------------------------------
    // 像素序号: 帧内光栅计数 (与输入 valid 同步推进, vsync 复位)
    //------------------------------------------------------------------
    reg [AW-1:0] pix_idx;
    always @(posedge clk) begin
        if (rst)           pix_idx <= {AW{1'b0}};
        else if (in_vsync) pix_idx <= {AW{1'b0}};
        else if (in_valid) pix_idx <= pix_idx + 1'b1;
    end

    // vsync 上升沿: 帧首单拍脉冲 (输入 vsync 可能持续多拍, 输出只允许一拍)
    reg vs_d;
    always @(posedge clk) begin
        if (rst) vs_d <= 1'b0;
        else     vs_d <= in_vsync;
    end
    wire vs_rise = in_vsync & ~vs_d;

    // 首帧标志: 首帧 passthrough (建立状态), 第二次 vsync 脉冲起开始滤波
    reg [1:0] vs_cnt;
    always @(posedge clk) begin
        if (rst)                      vs_cnt <= 2'd0;
        else if (p_vs[LAT-1])         vs_cnt <= vs_cnt + 2'd1;
    end

    reg first_frame;
    always @(posedge clk) begin
        if (rst)                                        first_frame <= 1'b1;
        else if (p_vs[LAT-1] && vs_cnt == 2'd1)         first_frame <= 1'b0;
    end

    // 帧存读请求 (首帧无需读)
    assign prev_ren   = in_valid & en & ~first_frame;
    assign prev_raddr = pix_idx;

    //------------------------------------------------------------------
    // 对齐流水: 把 valid/pixel/index/vsync 延迟 LAT 拍, 与 prev_rdata 对齐
    //------------------------------------------------------------------
    integer i;
    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < LAT; i = i + 1) begin
                p_pix[i] <= 16'd0;
                p_idx[i] <= {AW{1'b0}};
                p_val[i] <= 1'b0;
                p_vs [i] <= 1'b0;
            end
        end else begin
            p_pix[0] <= in_pixel;
            p_idx[0] <= pix_idx;
            p_val[0] <= in_valid;
            p_vs [0] <= vs_rise;
            for (i = 1; i < LAT; i = i + 1) begin
                p_pix[i] <= p_pix[i-1];
                p_idx[i] <= p_idx[i-1];
                p_val[i] <= p_val[i-1];
                p_vs [i] <= p_vs [i-1];
            end
        end
    end

    //------------------------------------------------------------------
    // 运算与输出
    //------------------------------------------------------------------
    wire          calc_valid = p_val[LAT-1];
    wire          calc_vs    = p_vs [LAT-1];
    wire [15:0]   calc_z     = p_pix[LAT-1];
    wire [AW-1:0] calc_idx   = p_idx[LAT-1];

    //------------------------------------------------------------------
    // 三通道独立更新 (组合): 稳态卡尔曼增益 4 档
    //   d = |z-x|;  d<t0 -> K=1/4 ; d<t1 -> K=1/2 ; d<t2 -> K=3/4 ; else K=1
    //------------------------------------------------------------------
    wire [6:0] zr = {1'b0, calc_z[15:11]};
    wire [6:0] zg = {1'b0, calc_z[10:5]};
    wire [6:0] zb = {1'b0, calc_z[4:0]};
    wire [6:0] xr = {1'b0, prev_rdata[15:11]};
    wire [6:0] xg = {1'b0, prev_rdata[10:5]};
    wire [6:0] xb = {1'b0, prev_rdata[4:0]};

    reg  [5:0] rr, gg, bb;
    reg  [5:0] dr, dg, db;
    always @* begin
        dr = (zr >= xr) ? (zr - xr) : (xr - zr);
        dg = (zg >= xg) ? (zg - xg) : (xg - zg);
        db = (zb >= xb) ? (zb - xb) : (xb - zb);

        if      (dr < thr0) rr = (3*xr + zr) >> 2;
        else if (dr < thr1) rr = (xr + zr)   >> 1;
        else if (dr < thr2) rr = (xr + 3*zr) >> 2;
        else                rr = zr;

        if      (dg < thr0) gg = (3*xg + zg) >> 2;
        else if (dg < thr1) gg = (xg + zg)   >> 1;
        else if (dg < thr2) gg = (xg + 3*zg) >> 2;
        else                gg = zg;

        if      (db < thr0) bb = (3*xb + zb) >> 2;
        else if (db < thr1) bb = (xb + zb)   >> 1;
        else if (db < thr2) bb = (xb + 3*zb) >> 2;
        else                bb = zb;
    end

    wire [15:0] kf_out = { rr[4:0], gg[5:0], bb[4:0] };

    wire        apply    = en & ~first_frame;
    wire [15:0] calc_out = apply ? kf_out : calc_z;

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 1'b0;
            out_pixel <= 16'd0;
            out_vsync <= 1'b0;
            wr_en     <= 1'b0;
            wr_addr   <= {AW{1'b0}};
            wr_data   <= 16'd0;
        end else begin
            out_vsync <= calc_vs;
            out_valid <= calc_valid & ~calc_vs;
            out_pixel <= calc_out;
            wr_en     <= calc_valid;
            wr_addr   <= calc_idx;
            wr_data   <= calc_out;
        end
    end

endmodule
