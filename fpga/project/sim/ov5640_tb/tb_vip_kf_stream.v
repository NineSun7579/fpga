`timescale 1ns/1ps
//============================================================================
// tb_vip_kf_stream.v -- vip_kf_stream (vip_kf + DDR line prefetcher) 单元测试
//
// 结构:
//   * 行为 AXI 读从机: 响应 axi_dma_read 的 AR, 以 128-bit beat 从"帧存"回放.
//   * 行为帧存: 2 个 bank (模拟 DDR 乒乓); 本帧读上一帧 bank, 本帧输出写本帧 bank.
//   * 与 tb_vip_kf 相同的确定性 RGB565 激励 + 相同的落盘格式, 复用
//     vip_kf_compare.py 做位精确黄金比对.
//
// 目的: 验证"行预取 + 128b 拆 16b lane" 对外部帧存的读回与直接同步 RAM
//       等价 (即 prev_rdata 与黄金模型的 state 逐位一致).
//============================================================================
module tb_vip_kf_stream;
    parameter integer W    = 16;
    parameter integer H    = 8;
    localparam integer NPIX = W*H;       // 128
    localparam integer AW   = $clog2(NPIX)+1;
    parameter integer NF   = 7;         // 帧数

    localparam [31:0] B0 = 32'h0080_0000;
    localparam [31:0] B1 = 32'h00A0_0000;

    reg          clk, rst;
    reg          en;
    reg  [5:0]   thr0, thr1, thr2;
    reg          in_valid;
    reg  [15:0]  in_pixel;
    reg          in_vsync;
    reg  [31:0]  prev_base;

    wire         out_valid;
    wire [15:0]  out_pixel;
    wire         out_vsync;

    wire [3:0]   m_arid;
    wire [31:0]  m_araddr;
    wire [7:0]   m_arlen;
    wire [2:0]   m_arsize;
    wire [1:0]   m_arburst;
    wire         m_arlock;
    wire [3:0]   m_arcache;
    wire [2:0]   m_arprot;
    wire         m_arvalid;
    wire         m_arready;
    wire [3:0]   m_rid;
    wire [127:0] m_rdata;
    wire [1:0]   m_rresp;
    wire         m_rlast;
    wire         m_rvalid;
    wire         m_rready;

    vip_kf_stream #(
        .W(W), .H(H), .AW(AW), .AXI_ID_WIDTH(4), .AXI_DATA_W(128), .BURST_LEN(8)
    ) dut (
        .clk(clk), .rst(rst),
        .en(en), .thr0(thr0), .thr1(thr1), .thr2(thr2),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .prev_base(prev_base),
        .m_axi_arid(m_arid), .m_axi_araddr(m_araddr), .m_axi_arlen(m_arlen),
        .m_axi_arsize(m_arsize), .m_axi_arburst(m_arburst), .m_axi_arlock(m_arlock),
        .m_axi_arcache(m_arcache), .m_axi_arprot(m_arprot),
        .m_axi_arvalid(m_arvalid), .m_axi_arready(m_arready),
        .m_axi_rid(m_rid), .m_axi_rdata(m_rdata), .m_axi_rresp(m_rresp),
        .m_axi_rlast(m_rlast), .m_axi_rvalid(m_rvalid), .m_axi_rready(m_rready),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync)
    );

    // 行为帧存 (2 bank)
    reg [15:0] bank0 [0:NPIX-1];
    reg [15:0] bank1 [0:NPIX-1];

    initial clk = 1'b0;
    always #5 clk = ~clk;

    //--------------------------------------------------------------
    // 行为 AXI 读从机
    //--------------------------------------------------------------
    reg        s_rv;
    reg [31:0] s_addr;
    reg [8:0]  s_left;
    reg        ar_pend;

    assign m_arready = ~s_rv & ~ar_pend;

    wire ar_hs = m_arvalid & m_arready;
    wire r_hs  = s_rv & m_rready;

    always @(posedge clk) begin
        if (rst) begin
            ar_pend <= 1'b0; s_rv <= 1'b0; s_addr <= 32'd0; s_left <= 9'd0;
        end else begin
            if (ar_hs) begin
                s_addr  <= m_araddr;
                s_left  <= {1'b0, m_arlen} + 9'd1;
                ar_pend <= 1'b1;
            end
            if (ar_pend) begin
                s_rv    <= 1'b1;
                ar_pend <= 1'b0;
            end
            if (r_hs) begin
                if (s_left == 9'd1) begin
                    s_rv <= 1'b0;
                end else begin
                    s_addr <= s_addr + 32'd16;
                    s_left <= s_left - 9'd1;
                end
            end
        end
    end

    assign m_rid    = 4'd0;
    assign m_rresp  = 2'b00;
    assign m_rvalid = s_rv;
    assign m_rlast  = s_rv & (s_left == 9'd1);

    function [127:0] beat_data;
        input [31:0] a;
        integer i, base, idx;
        reg [15:0] px;
        begin
            beat_data = 128'd0;
            base = (a >= B1) ? B1 : B0;
            for (i = 0; i < 8; i = i + 1) begin
                idx = ((a - base) >> 1) + i;
                if (idx < NPIX) begin
                    if (a >= B1) px = bank1[idx]; else px = bank0[idx];
                    beat_data[16*i +: 16] = px;
                end
            end
        end
    endfunction

    assign m_rdata = beat_data(s_addr);

    //--------------------------------------------------------------
    // 输出捕获 + 写回本帧 bank
    //--------------------------------------------------------------
    reg [15:0] inf  [0:NF*NPIX-1];
    reg [15:0] outf [0:NF*NPIX-1];
    integer    of, oc, fopen_f; 
    integer    nframes_out;
    integer    dbg_f;

    always @(posedge clk) begin
        if (!rst) begin
            if (out_vsync) begin
                of = of + 1;
                oc = 0;
                fopen_f = 1;
            end else if (out_valid && fopen_f) begin
                if (of >= 0 && of < NF && oc < NPIX) begin
                    outf[of*NPIX + oc] = out_pixel;
                    if ((of & 1) == 0) bank0[oc] <= out_pixel;
                    else               bank1[oc] <= out_pixel;
                end
                oc = oc + 1;
            end
        end
    end

    //--------------------------------------------------------------
    // 激励
    //--------------------------------------------------------------
    function [15:0] gen_px;
        input integer ff;
        input integer pp;
        integer r, g, b, n;
        begin
            r = (pp*3) & 31;
            g = (pp*5) & 63;
            b = (pp*7) & 31;
            n = ((ff*37) + (pp*11)) % 4;
            r = (r + n) & 31;
            g = (g + n) & 63;
            b = (b + n) & 31;
            if (pp >= 8 && pp < 12) begin
                r = (r + ff*3) & 31;
                g = (g + ff*5) & 63;
                b = (b + ff*7) & 31;
            end
            gen_px = {r[4:0], g[5:0], b[4:0]};
            if (pp == ((ff*5) % NPIX))   gen_px = 16'hFFFF;
            if (pp == ((ff*5+1) % NPIX)) gen_px = 16'h0000;
        end
    endfunction

    task send_frame;
        input integer ff;
        integer r, q;
        begin
            dbg_f = ff;
            @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
            repeat (3) @(negedge clk);
            in_vsync = 1'b0;
            repeat (30) @(negedge clk);          // 场消隐
            for (r = 0; r < H; r = r + 1) begin
                for (q = 0; q < W; q = q + 1) begin
                    @(negedge clk);
                    in_valid = 1'b1;
                    in_pixel = gen_px(ff, r*W + q);
                    inf[ff*NPIX + r*W + q] = gen_px(ff, r*W + q);
                end
                @(negedge clk); in_valid = 1'b0;
                repeat (24) @(negedge clk);      // 行消隐 (给预取留时间)
            end
            repeat (10) @(negedge clk);
        end
    endtask

    integer fin, fout, i, f, p;
    integer dbg_en = 0;
    always @(posedge clk) begin
        if (!rst && dbg_en && in_valid)
            $display("DBG in: row=%0d col=%0d pix=%04X prev=%04X (ra=%0d lane=%0d)",
                     dut.row, dut.col, in_pixel, dut.kf_prev_rdata, dut.lb_ra, dut.rd_lane);
        if (!rst && dbg_en && dut.fill_wr)
            $display("DBG wr: base=%0d idx=%0d data_lo=%04X", dut.fill_base, dut.fill_idx, dut.m_r_data[15:0]);
    end
    initial begin
        rst = 1'b1; en = 1'b1;
        thr0 = 6'd3; thr1 = 6'd8; thr2 = 6'd20;
        in_valid = 1'b0; in_pixel = 16'd0; in_vsync = 1'b0;
        prev_base = B1;
        of = -1; oc = 0; fopen_f = 0; nframes_out = 0; dbg_f = -1;
        for (i = 0; i < NPIX; i = i + 1) begin bank0[i] = 16'd0; bank1[i] = 16'd0; end
        for (i = 0; i < NF*NPIX; i = i + 1) begin inf[i] = 16'd0; outf[i] = 16'd0; end

        repeat (5) @(negedge clk);
        rst = 1'b0;

        for (f = 0; f < NF; f = f + 1) begin
            // prev bank = (f-1)&1 = (f+1)&1
            prev_base = (((f + 1) & 1) == 0) ? B0 : B1;
            send_frame(f);
        end

        @(negedge clk); in_valid = 1'b0;
        repeat (120) @(negedge clk);

        nframes_out = of + (fopen_f ? 1 : 0);

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

        $display("VIPKFSTREAM frames_out=%0d (expect %0d)", nframes_out, NF);
        if (nframes_out >= NF)
            $display("VIPKFSTREAM_DUMP_OK");
        else
            $display("VIPKFSTREAM_DUMP_FAIL");
        $finish;
    end
endmodule
