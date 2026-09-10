`timescale 1ns/1ps
//============================================================================
// tb_prep_regs.v : 扩展寄存器组 AXI-Lite 仿真
//   覆盖: 复位默认值 / 全字段写读 / 模式折叠 (color_en/edge_en) / INJ 单拍脉冲
//         / 按键粘滞+W1C / LED / 四节点打点+清零 / 未映射地址 / 背靠背写
//============================================================================
module tb_prep_regs;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg         awvalid = 1'b0;
    wire        awready;
    reg  [31:0] awaddr = 32'd0;
    reg         wvalid = 1'b0;
    wire        wready;
    reg  [31:0] wdata = 32'd0;
    reg  [3:0]  wstrb = 4'hF;
    wire        bvalid;
    reg         bready = 1'b0;
    wire [1:0]  bresp;
    reg         arvalid = 1'b0;
    wire        arready;
    reg  [31:0] araddr = 32'd0;
    wire        rvalid;
    reg         rready = 1'b0;
    wire [31:0] rdata;
    wire [1:0]  rresp;

    wire        prep_bypass;
    wire [1:0]  prep_mode;
    wire [11:0] prep_img_width;
    wire [7:0]  prep_thr_sat, prep_thr_hue, prep_thr_val, prep_thr_low;
    wire [10:0] prep_thr_edge;
    wire [7:0]  prep_roi_top, prep_roi_bot, prep_row_thr, prep_dash_thr;
    wire [31:0] inj_addr, inj_len, inj_fid;
    wire        inj_start, inj_done_clr;
    reg         inj_busy = 1'b0, inj_done = 1'b0;
    reg  [15:0] inj_done_fid = 16'h1234;
    reg         pipe_frame_sync = 1'b0, pipe_fifo_afull = 1'b0, npu_busy = 1'b0;
    reg  [7:0]  out_frame_cnt = 8'd0;
    reg  [3:0]  btn_toggle_evt = 4'd0;
    reg  [3:0]  btn_level_sync = 4'd0;
    wire [3:0]  btn_sticky, btn_sticky_clr;
    wire [3:0]  led_ctrl;
    reg  [1:0]  lane_left_type = 2'd1, lane_right_type = 2'd2;
    reg         lane_left_valid = 1'b1, lane_right_valid = 1'b1, lane_frame_upd = 1'b0;
    reg         ts_cap = 1'b0, ts_prep = 1'b0, ts_npu = 1'b0, ts_dma = 1'b0;
    wire [31:0] ts0, ts1, ts2, ts3;

    prep_regs #(.TICK_DIV(4)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_awaddr(awaddr),
        .s_axi_wvalid(wvalid), .s_axi_wready(wready), .s_axi_wdata(wdata),
        .s_axi_wstrb(wstrb), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_bresp(bresp),
        .s_axi_arvalid(arvalid), .s_axi_arready(arready), .s_axi_araddr(araddr),
        .s_axi_rvalid(rvalid), .s_axi_rready(rready), .s_axi_rdata(rdata),
        .s_axi_rresp(rresp),
        .prep_bypass(prep_bypass), .prep_mode(prep_mode),
        .prep_img_width(prep_img_width),
        .prep_thr_sat(prep_thr_sat), .prep_thr_hue(prep_thr_hue),
        .prep_thr_val(prep_thr_val), .prep_thr_low(prep_thr_low),
        .prep_thr_edge(prep_thr_edge),
        .prep_lane_roi_top(prep_roi_top), .prep_lane_roi_bot(prep_roi_bot),
        .prep_lane_row_thr(prep_row_thr), .prep_lane_dash_thr(prep_dash_thr),
        .inj_addr(inj_addr), .inj_len(inj_len), .inj_frame_id(inj_fid),
        .inj_start(inj_start), .inj_done_clr(inj_done_clr),
        .inj_busy(inj_busy), .inj_done(inj_done), .inj_done_fid(inj_done_fid),
        .pipe_frame_sync(pipe_frame_sync), .pipe_fifo_afull(pipe_fifo_afull),
        .npu_busy(npu_busy), .out_frame_cnt(out_frame_cnt),
        .btn_toggle_evt(btn_toggle_evt), .btn_level_sync(btn_level_sync),
        .btn_sticky(btn_sticky), .btn_sticky_clr(btn_sticky_clr),
        .led_ctrl(led_ctrl),
        .lane_left_type(lane_left_type), .lane_right_type(lane_right_type),
        .lane_left_valid(lane_left_valid), .lane_right_valid(lane_right_valid),
        .lane_frame_upd(lane_frame_upd),
        .ts_cap_pulse(ts_cap), .ts_prep_pulse(ts_prep),
        .ts_npu_pulse(ts_npu), .ts_dma_pulse(ts_dma),
        .ts_value0(ts0), .ts_value1(ts1), .ts_value2(ts2), .ts_value3(ts3)
    );

    //------------------------------------------------------------------
    // AXI-Lite BFM
    //------------------------------------------------------------------
    task axi_wr(input [31:0] a, input [31:0] d);
        begin
            @(posedge clk);
            awvalid = 1'b1; awaddr = a;
            wvalid  = 1'b1; wdata = d; wstrb = 4'hF;
            while (!(awready && wready)) @(posedge clk);
            awvalid = 1'b0; wvalid = 1'b0;   // ready 当拍即撤 (防 slave 重_arm)
            while (!bvalid) @(posedge clk);
            bready = 1'b1;
            @(posedge clk);
            bready = 1'b0;
        end
    endtask

    task axi_rd(input [31:0] a, output [31:0] d);
        begin
            @(posedge clk);
            arvalid = 1'b1; araddr = a;
            while (!arready) @(posedge clk);
            @(posedge clk);
            arvalid = 1'b0;
            while (!rvalid) @(posedge clk);
            d = rdata;
            rready = 1'b1;
            @(posedge clk);
            rready = 1'b0;
        end
    endtask

    integer err = 0;
    reg [31:0] rd;
    reg inj_start_seen = 1'b0, inj_start_now0 = 1'b0, inj_clr_seen = 1'b0;
    reg saw_start = 1'b0;
    always @(posedge clk) begin
        if (rst_n) begin
            if (inj_start) begin
                inj_start_seen <= 1'b1;
                saw_start      <= 1'b1;
            end else if (saw_start) begin
                inj_start_now0 <= 1'b1;
                saw_start      <= 1'b0;
            end
            if (inj_done_clr) inj_clr_seen <= 1'b1;
        end
    end

    task chk(input [31:0] got, input [31:0] exp, input [127:0] name);
        begin
            if (got !== exp) begin
                $display("[REGS][ERR] %0s: got=%08h exp=%08h", name, got, exp);
                err = err + 1;
            end
        end
    endtask

    //------------------------------------------------------------------
    // 激励
    //------------------------------------------------------------------
    localparam BASE = 32'h0000_0000;   // 偏移即全地址 (低8位译码)

    initial begin
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);

        // 1) 复位默认值
        axi_rd(BASE + 32'h100, rd);
        chk(rd, 32'h0000_0018, "CTRL默认");
        axi_rd(BASE + 32'h104, rd);
        chk(rd, {8'd160, 8'd64, 8'd96, 8'd128}, "THR默认");
        axi_rd(BASE + 32'h108, rd);
        chk(rd, {4'd0, 12'd720, 4'd0, 12'd1280}, "SIZE默认");
        chk(prep_img_width, 12'd1280, "img_width默认");

        // 2) CTRL 写读 + 模式折叠
        axi_wr(BASE + 32'h100, 32'h0000_001F);      // bypass1 mode3 edge1 color1
        chk(prep_bypass, 1'b1, "bypass");
        chk(prep_mode, 2'd3, "mode3");
        axi_rd(BASE + 32'h100, rd);
        chk(rd, 32'h0000_001F, "CTRL回读");
        axi_wr(BASE + 32'h100, 32'h0000_0007);      // bypass0 mode3 edge1 color0 -> 折叠2
        chk(prep_mode, 2'd2, "color_en=0折叠灰度");
        axi_wr(BASE + 32'h100, 32'h0000_0016);      // bypass0 mode3 edge0 color1 -> 折叠1
        chk(prep_mode, 2'd1, "edge_en=0折叠色化");

        // 3) 阈值组写读
        axi_wr(BASE + 32'h104, {8'd200, 8'd90, 8'd80, 8'd70});
        axi_rd(BASE + 32'h104, rd);
        chk(rd, {8'd200, 8'd90, 8'd80, 8'd70}, "THR回读");
        chk({prep_thr_val, prep_thr_hue, prep_thr_sat, prep_thr_edge[7:0]},
            {8'd200, 8'd90, 8'd80, 8'd70}, "阈值端口");

        // 4) LANE 参数
        axi_wr(BASE + 32'h10C, {8'd9, 8'd4, 8'd80, 8'd30});
        axi_rd(BASE + 32'h10C, rd);
        chk(rd, {8'd9, 8'd4, 8'd80, 8'd30}, "LANE回读");

        // 5) 注入地址/长度/帧号 + 单拍脉冲 (并发标志捕获)
        axi_wr(BASE + 32'h110, 32'h0600_1000);
        axi_wr(BASE + 32'h114, 32'd691200);
        axi_wr(BASE + 32'h118, 32'd77);
        axi_rd(BASE + 32'h110, rd);
        chk(rd, 32'h0600_1000, "INJ_ADDR");
        chk(inj_len, 32'd691200, "inj_len端口");
        chk(inj_fid, 32'd77, "inj_fid端口");
        axi_wr(BASE + 32'h11C, 32'h0000_0001);      // start
        repeat (3) @(posedge clk);                  // 等脉冲结束+标志置位
        chk(inj_start_seen, 1'b1, "inj_start脉冲");
        chk(inj_start_now0, 1'b1, "inj_start单拍");
        axi_wr(BASE + 32'h11C, 32'h0000_0010);      // 清done
        repeat (3) @(posedge clk);
        chk(inj_clr_seen, 1'b1, "inj_clr脉冲");

        // 6) 状态回读 (INJ_STATUS / PIPE_STATUS / LANE_RESULT)
        inj_busy = 1'b1; inj_done = 1'b1;
        axi_rd(BASE + 32'h120, rd);
        chk(rd[1:0], 2'b11, "INJ_STATUS忙完成");
        chk(rd[31:16], 16'h1234, "INJ_STATUS帧号");
        npu_busy = 1'b1; pipe_fifo_afull = 1'b1; out_frame_cnt = 8'd55;
        axi_rd(BASE + 32'h130, rd);
        chk(rd[15:8], 8'd55, "PIPE帧计数");
        chk(rd[2], 1'b1, "PIPE npu_busy");
        chk(rd[1], 1'b1, "PIPE fifo_afull");
        axi_rd(BASE + 32'h160, rd);
        chk(rd[1:0], 2'd1, "LANE左线型");
        chk(rd[3:2], 2'd2, "LANE右线型");

        // 7) 按键粘滞 + W1C
        btn_level_sync = 4'b0010;
        @(posedge clk);
        btn_toggle_evt = 4'b0010;
        @(posedge clk);
        btn_toggle_evt = 4'd0;
        repeat (2) @(posedge clk);
        axi_rd(BASE + 32'h140, rd);
        chk(rd[1], 1'b1, "按键粘滞置位");
        axi_wr(BASE + 32'h144, 32'b0010);           // W1C
        repeat (2) @(posedge clk);
        axi_rd(BASE + 32'h140, rd);
        chk(rd[1], 1'b0, "按键W1C清除");
        axi_rd(BASE + 32'h144, rd);
        chk(rd[3:0], 4'b0010, "按键实时电平");

        // 8) LED
        axi_wr(BASE + 32'h150, 32'h0000_0005);
        chk(led_ctrl, 4'b0101, "LED");

        // 9) 打点: 事件锁存 -> 主机清零
        repeat (10) @(posedge clk);
        ts_prep = 1'b1;
        @(posedge clk);
        ts_prep = 1'b0;
        repeat (2) @(posedge clk);
        axi_rd(BASE + 32'h174, rd);
        if (rd == 32'd0) begin
            $display("[REGS][ERR] TS1未锁存");
            err = err + 1;
        end
        axi_wr(BASE + 32'h17C, 32'h0);              // 清零
        repeat (2) @(posedge clk);
        axi_rd(BASE + 32'h170, rd);
        chk(rd, 32'd0, "TS0清零");
        axi_rd(BASE + 32'h174, rd);
        chk(rd, 32'd0, "TS1清零");

        // 10) 未映射地址
        axi_rd(BASE + 32'hF0, rd);
        chk(rd, 32'd0, "未映射读0");

        // 11) 背靠背写 (验证 seen 标志重挂)
        axi_wr(BASE + 32'h150, 32'h0000_0001);
        axi_wr(BASE + 32'h150, 32'h0000_0002);
        chk(led_ctrl, 4'b0010, "背靠背写第2笔生效");
        axi_rd(BASE + 32'h100, rd);
        chk(rd[3:0], 4'b0110, "读后状态");

        if (err == 0)
            $display("[REGS] TB_PASS");
        else
            $display("[REGS] TB_FAIL  err=%0d", err);
        $finish;
    end

    initial begin
        #5_000_000;
        $display("[REGS] TB_FAIL  超时 err=%0d", err);
        $finish;
    end

endmodule
