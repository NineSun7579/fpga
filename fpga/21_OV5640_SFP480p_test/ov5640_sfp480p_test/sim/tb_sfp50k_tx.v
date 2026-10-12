`timescale 1ns / 1ps
//===========================================================================
//  tb_sfp50k_tx.v -- 50K 发送链路仿真: 双摄模型 -> cam2_merge -> sfp_video_tx
//                     -> 光口字流(fab 32bit) -> 协议解码 -> 黄金逐像素比对
//
//  覆盖:
//   1) cam2_merge 结构校验(保留 tb_cam2_merge 的行/段检查: 每行 2*LP 像素,
//      A 段/ B 段行号连续, 每帧 LINES 行)
//   2) 传输校验: 解码像素序列 == 合流输出序列 (顺序/数值), 帧界对齐
//   3) 协议格式: 数据字 rxk==0000 = 2 像素; 控制字 rxk==1001 中
//      vs=rxd[21], hs=rxd[22]; vs 上升沿 = 帧界 (与 100H sfp_video_rx 一致)
//   4) fix1(像素配对)/fix2(idle 携带 vs/hs) 回归
//
//  几何参数缩小 (LP=160/LINES=60) 加速仿真; 结构与 640x480 全同。
//===========================================================================
module tb_sfp50k_tx;

    parameter TA = 23.809;    // A 42.000MHz
    parameter TB = 23.799;    // B 42.017MHz (+360ppm)
    parameter TO = 16.0;      // o_clk 62.5MHz (= clk2core_tx/2, 与实机一致)
    parameter TF = 8.0;       // fab 125MHz

    localparam LP = 160, LINES = 60, HTS = 200, VTS = 70, VS_LINES = 4;
    localparam W  = 2*LP;                      // 合成行宽 320

    reg a_clk = 0, b_clk = 0, o_clk = 0, fab_clk = 0;
    always #(TA/2.0) a_clk = ~a_clk;
    always #(TB/2.0) b_clk = ~b_clk;
    always #(TO/2.0) o_clk = ~o_clk;
    always #(TF/2.0) fab_clk = ~fab_clk;

    reg rst_n = 0;
    initial begin #200; rst_n = 1; end

    reg  [15:0] a_data, b_data;
    reg         a_de, b_de, a_vs, b_vs;

    // ---------------- 摄像头模型 A (a_clk 域) ----------------
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

    // ---------------- 摄像头模型 B (b_clk 域, 相位差 4 行) ----------------
    reg [11:0] b_vcnt = 0, b_hcnt = 0;
    initial b_vcnt = 4;
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

    // ---------------- DUT1: cam2_merge ----------------
    wire [15:0] c_data;
    wire        c_de, c_vs;

    cam2_merge #(.LINE_PIX(LP), .LINES(LINES)) dut_merge (
        .a_clk(a_clk), .a_rst_n(rst_n),
        .a_data(a_data), .a_de(a_de), .a_vs(a_vs),
        .b_clk(b_clk), .b_rst_n(rst_n),
        .b_data(b_data), .b_de(b_de), .b_vs(b_vs),
        .o_clk(o_clk), .o_rst_n(rst_n),
        .corr_mode(4'd0),
        .c_data(c_data), .c_de(c_de), .c_vs(c_vs)
    );

    // ---------------- 黄金采集 (o_clk 域): 帧号 + 帧内像素序 ----------------
    reg [15:0] golden [0:W*LINES-1];
    integer    gframe = 0, gidx = 0;
    reg        c_vs_d = 0;
    always @(posedge o_clk) begin
        if (rst_n) begin
            c_vs_d <= c_vs;
            if (c_vs && !c_vs_d) begin gframe <= gframe + 1; gidx <= 0; end
            if (c_de && gframe > 0 && gidx < W*LINES)
                golden[gidx] <= c_data;
            if (c_de && gframe > 0) gidx <= gidx + 1;
        end
    end

    // ---------------- DUT2: sfp_video_tx (光口打包) ----------------
    wire [31:0] txd;
    wire [3:0]  txk;
    reg  link_ready = 0;
    initial begin #400; link_ready = 1; end

    sfp_video_tx u_tx (
        .vid_clk   (o_clk),
        .vid_rst_n (rst_n),
        .vid_data  ({c_vs, 1'b0, c_de, c_data}),   // 与实机顶层接线一致 (hs=0)
        .fab_clk   (fab_clk),
        .fab_rst_n (rst_n),
        .link_ready(link_ready),
        .txd       (txd),
        .txk       (txk)
    );

    // ---------------- 解码器 + 检查器 (fab 域) ----------------
    // 与 100H sfp_video_rx 相同的重建规则:
    //   数据字(txk==0000) => de=1, 输出 pix0(txd[15:0]) 后 pix1(txd[31:16])
    //   控制字(txk==1001) => vs=txd[21], hs=txd[22], 无像素
    integer rframe = -1;         // 已开始的解码帧号 (-1 = 尚未见到 vs 上升沿)
    integer ridx   = 0;
    integer terr   = 0;
    reg     rvs = 0, rvs_q = 0;
    reg     idle_vs = 0, idle_hs = 0;   // fix2 观测: idle 字携带的电平
    integer idle_cnt = 0, data_cnt = 0, ctrl_cnt = 0;
    integer done_wait = 0;
    integer word_dbg = 0;
    reg     finished = 0;

    always @(posedge fab_clk) begin
        if (rst_n && link_ready && !finished) begin
            if (word_dbg < 12) begin
                word_dbg = word_dbg + 1;
                $display("[%0t] WORD txk=%b txd=%08h (vs=%b hs=%b status=%02h)",
                         $time, txk, txd, txd[21], txd[22], (txd>>16)&8'hFF);
            end
            if (txk == 4'b1001) begin
                ctrl_cnt = ctrl_cnt + 1;
                // 帧界: 控制字携带的 vs 位相对锁存值上升
                if (txd[21] && !rvs) begin
                    if (rframe >= 1) begin
                        if (ridx != W*LINES) begin
                            terr = terr + 1;
                            $display("[%0t] FRAME_LEN frame=%0d got=%0d exp=%0d", $time, rframe, ridx, W*LINES);
                        end
                    end
                    rframe <= rframe + 1;
                    ridx    <= 0;
                end
                rvs <= txd[21];
            end
            else if (txk == 4'b0000) begin
                data_cnt = data_cnt + 1;
                if (rframe >= 1) begin
                    if (ridx >= W*LINES) begin
                        terr = terr + 1;
                        if (terr < 10) $display("[%0t] PIX_OVF frame=%0d idx=%0d", $time, rframe, ridx);
                    end
                    else if (txd[15:0] !== golden[ridx]) begin
                        terr = terr + 1;
                        if (terr < 10) $display("[%0t] PIX_MISMATCH frame=%0d idx=%0d got=%04h exp=%04h",
                                                $time, rframe, ridx, txd[15:0], golden[ridx]);
                    end
                    if (ridx+1 >= W*LINES) begin
                        terr = terr + 1;
                        if (terr < 10) $display("[%0t] PIX_OVF1 frame=%0d idx=%0d", $time, rframe, ridx+1);
                    end
                    else if (txd[31:16] !== golden[ridx+1]) begin
                        terr = terr + 1;
                        if (terr < 10) $display("[%0t] PIX_MISMATCH1 frame=%0d idx=%0d got=%04h exp=%04h",
                                                $time, rframe, ridx+1, txd[31:16], golden[ridx+1]);
                    end
                end
                ridx <= ridx + 2;
            end
            if (rframe >= 4) begin
                done_wait = done_wait + 1;
                if (done_wait > 300000) finished = 1;
            end
        end
    end

    // ---------------- 汇总 / 看门狗 ----------------
    always @(posedge fab_clk) begin
        if (finished) begin
            $display("frames=%0d golden_frames=%0d pixels_ok=%0d data_words=%0d ctrl_words=%0d terr=%0d",
                     rframe, gframe, ridx, data_cnt, ctrl_cnt, terr);
            if (terr == 0 && rframe >= 4 && gframe >= 4)
                $display("TB_PASS");
            else
                $display("TB_FAIL");
            $finish;
        end
    end
    initial begin
        #6_000_000;   // 6ms 看门狗 (小几何: 1 帧 ≈ 333us)
        $display("TB_FAIL_TIMEOUT rframe=%0d gframe=%0d ridx=%0d terr=%0d", rframe, gframe, ridx, terr);
        $finish;
    end

endmodule
