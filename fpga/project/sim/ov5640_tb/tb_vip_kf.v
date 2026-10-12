`timescale 1ns/1ps
//============================================================================
// tb_vip_kf.v -- vip_kf 时域卡尔曼/IIR 滤波单元测试
//
// 结构:
//   * 双 bank 行为帧存 (模拟 DDR 乒乓): 本帧读上一帧 bank, 写本帧 bank.
//   * 逐帧灌入确定性 RGB565 激励 (静态底图 + 小幅噪声 + 运动亮块),
//     覆盖 K=1/4,1/2,3/4,1 四档.
//   * 输入帧与硬件输出帧落盘, 供 Python 黄金模型逐位比对:
//       kf_in.mem     : 每帧 NPIX 行 "%04X", 帧头 "# frame <f>"
//       kf_hw_out.mem : 同上, 硬件滤波输出
//
// PASS 条件: 由 vip_kf_compare.py 判定 (位精确).
// 本 TB 自身打印激励覆盖统计, 并检查输出帧数.
//============================================================================
module tb_vip_kf;
    localparam integer W    = 8;
    localparam integer H    = 4;
    localparam integer NPIX = W*H;    // 32
    localparam integer AW   = 5;
    localparam integer LAT  = 1;
    localparam integer NF   = 7;      // 帧数

    reg          clk, rst;
    reg          en;
    reg  [5:0]   thr0, thr1, thr2;
    reg          in_valid;
    reg  [15:0]  in_pixel;
    reg          in_vsync;
    wire         out_valid;
    wire [15:0]  out_pixel;
    wire         out_vsync;
    wire         prev_ren;
    wire [AW-1:0] prev_raddr;
    reg  [15:0]  prev_rdata;
    wire         wr_en;
    wire [AW-1:0] wr_addr;
    wire [15:0]  wr_data;

    // 行为帧存: 2 个 bank, 每个 NPIX x 16bit ; 同步读(1拍), 同步写
    reg [15:0] bank0 [0:NPIX-1];
    reg [15:0] bank1 [0:NPIX-1];

    // 记录
    reg [15:0] inf  [0:NF*NPIX-1];
    reg [15:0] outf [0:NF*NPIX-1];
    integer    o_frame, o_cnt, frame_open;
    integer    f, p, i;
    integer    nframes_out;

    vip_kf #(
        .W(W), .H(H), .AW(AW), .LAT(LAT)
    ) dut (
        .clk(clk), .rst(rst),
        .en(en), .thr0(thr0), .thr1(thr1), .thr2(thr2),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .prev_ren(prev_ren), .prev_raddr(prev_raddr), .prev_rdata(prev_rdata),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // 当前帧的读/写 bank
    integer cur_f;
    wire [AW-1:0] rd_addr = prev_raddr;
    always @(posedge clk) begin
        if (prev_ren)
            prev_rdata <= (cur_f % 2 == 0) ? bank1[rd_addr] : bank0[rd_addr];
    end
    always @(posedge clk) begin
        if (wr_en) begin
            if (cur_f % 2 == 0) bank0[wr_addr] <= wr_data;
            else                bank1[wr_addr] <= wr_data;
        end
    end

    // 输出捕获 (按 out_vsync 分帧)
    always @(posedge clk) begin
        if (!rst) begin
            if (out_vsync) begin
                o_frame = o_frame + 1;
                o_cnt   = 0;
                frame_open = 1;
            end else if (out_valid && frame_open) begin
                if (o_frame >= 0 && o_frame < NF && o_cnt < NPIX)
                    outf[o_frame*NPIX + o_cnt] = out_pixel;
                o_cnt = o_cnt + 1;
            end
        end
    end

    // 激励生成 (与 golden 无关: golden 从落盘的 kf_in.mem 读)
    function [15:0] gen_px;
        input integer ff;
        input integer pp;
        integer r, g, b, n;
        begin
            r = (pp*3)       & 31;
            g = (pp*5)       & 63;
            b = (pp*7)       & 31;
            // 小幅噪声 0..3 (帧相关, 触发低档平滑)
            n = ((ff*37) + (pp*11)) % 4;
            r = (r + n) & 31;
            g = (g + n) & 63;
            b = (b + n) & 31;
            // 中等变化区 (像素 8..11): 触发中间档
            if (pp >= 8 && pp < 12) begin
                r = (r + ff*3) & 31;
                g = (g + ff*5) & 63;
                b = (b + ff*7) & 31;
            end
            gen_px = {r[4:0], g[5:0], b[4:0]};
            // 运动亮块 (强变化 -> K=1 档)
            if (pp == ((ff*5) % NPIX)) gen_px = 16'hFFFF;
            if (pp == ((ff*5+1) % NPIX)) gen_px = 16'h0000;
        end
    endfunction

    task send_frame;
        input integer ff;
        integer q;
        begin
            // 帧首: vsync 脉冲 (无数据)
            @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
            repeat (3) @(negedge clk);
            in_vsync = 1'b0;
            cur_f = ff;
            // 有效像素
            for (q = 0; q < NPIX; q = q + 1) begin
                @(negedge clk);
                in_valid = 1'b1;
                in_pixel = gen_px(ff, q);
                inf[ff*NPIX + q] = gen_px(ff, q);
            end
            @(negedge clk); in_valid = 1'b0;
            repeat (4) @(negedge clk);
        end
    endtask

    integer fin, fout;
    initial begin
        rst = 1'b1; en = 1'b1;
        thr0 = 6'd3; thr1 = 6'd8; thr2 = 6'd20;
        in_valid = 1'b0; in_pixel = 16'd0; in_vsync = 1'b0;
        prev_rdata = 16'd0;
        o_frame = -1; o_cnt = 0; frame_open = 0; nframes_out = 0;
        cur_f = 0;
        for (i = 0; i < NPIX; i = i + 1) begin bank0[i] = 16'd0; bank1[i] = 16'd0; end
        for (i = 0; i < NF*NPIX; i = i + 1) begin inf[i] = 16'd0; outf[i] = 16'd0; end

        repeat (5) @(negedge clk);
        rst = 1'b0;

        for (f = 0; f < NF; f = f + 1) send_frame(f);

        // 收尾: 等待最后流水输出
        @(negedge clk); in_valid = 1'b0;
        repeat (60) @(negedge clk);

        nframes_out = o_frame + (frame_open ? 1 : 0);

        // 落盘 (相对工程根目录)
        fin = $fopen("sim/ov5640_tb/kf_in.mem", "w");
        for (f = 0; f < NF; f = f + 1) begin
            $fwrite(fin, "# frame %0d\n", f);
            for (p = 0; p < NPIX; p = p + 1)
                $fwrite(fin, "%04X\n", inf[f*NPIX + p]);
        end
        $fclose(fin);

        fout = $fopen("sim/ov5640_tb/kf_hw_out.mem", "w");
        for (f = 0; f < NF; f = f + 1) begin
            $fwrite(fout, "# frame %0d\n", f);
            for (p = 0; p < NPIX; p = p + 1)
                $fwrite(fout, "%04X\n", outf[f*NPIX + p]);
        end
        $fclose(fout);

        $display("VIPKF frames_out=%0d (expect %0d)", nframes_out, NF);
        if (nframes_out >= NF)
            $display("VIPKF_DUMP_OK");
        else
            $display("VIPKF_DUMP_FAIL");
        $finish;
    end
endmodule
