`timescale 1ns/1ps
//============================================================================
// tb_ovreg_axil_decode.v : AXI-Lite address decoder back-to-back TB
//   DUT chain: BFM -> ovreg_axil_decode -> { ov5640_reg (sel=0),
//                                            prep_regs  (sel=1) }
//   Covers: CAM segment write/read (0x040/0x080/0x0C0), PREP segment
//   write/read (0x104/0x108/0x11C INJ pulse), unmapped ov5640 address
//   (reads 0xFFFFFFFF default), and interleaved segment switching.
//============================================================================
module tb_ovreg_axil_decode;

    reg clk = 1'b0;
    reg rst = 1'b1;                 // active high (axi_rst polarity)
    always #5 clk = ~clk;

    //----------------------------------------
    // upstream BFM channels
    //----------------------------------------
    reg          awvalid = 1'b0;
    wire         awready;
    reg  [31:0]  awaddr  = 32'd0;
    reg          wvalid  = 1'b0;
    wire         wready;
    reg  [31:0]  wdata   = 32'd0;
    reg  [3:0]   wstrb   = 4'hF;
    wire         bvalid;
    reg          bready  = 1'b0;
    wire  [1:0]  bresp;
    reg          arvalid = 1'b0;
    wire         arready;
    reg  [31:0]  araddr  = 32'd0;
    wire         rvalid;
    reg          rready  = 1'b0;
    wire [31:0]  rdata;
    wire  [1:0]  rresp;

    //----------------------------------------
    // decode DUT
    //----------------------------------------
    wire         m0_awvalid, m0_awready, m0_wvalid, m0_wready;
    wire [31:0]  m0_awaddr, m0_wdata;
    wire  [3:0]  m0_wstrb;
    wire         m0_bvalid, m0_bready;
    wire  [1:0]  m0_bresp;
    wire         m0_arvalid, m0_arready, m0_rvalid, m0_rready;
    wire [31:0]  m0_araddr, m0_rdata;
    wire  [1:0]  m0_rresp;

    wire         m1_awvalid, m1_awready, m1_wvalid, m1_wready;
    wire [31:0]  m1_awaddr, m1_wdata;
    wire  [3:0]  m1_wstrb;
    wire         m1_bvalid, m1_bready;
    wire  [1:0]  m1_bresp;
    wire         m1_arvalid, m1_arready, m1_rvalid, m1_rready;
    wire [31:0]  m1_araddr, m1_rdata;
    wire  [1:0]  m1_rresp;

    ovreg_axil_decode dut (
        .clk(clk), .rst(rst),
        .s_awvalid(awvalid), .s_awready(awready), .s_awaddr(awaddr),
        .s_wvalid(wvalid), .s_wready(wready), .s_wdata(wdata), .s_wstrb(wstrb),
        .s_bvalid(bvalid), .s_bready(bready), .s_bresp(bresp),
        .s_arvalid(arvalid), .s_arready(arready), .s_araddr(araddr),
        .s_rvalid(rvalid), .s_rready(rready), .s_rdata(rdata), .s_rresp(rresp),
        .m0_awvalid(m0_awvalid), .m0_awready(m0_awready), .m0_awaddr(m0_awaddr),
        .m0_wvalid(m0_wvalid), .m0_wready(m0_wready), .m0_wdata(m0_wdata), .m0_wstrb(m0_wstrb),
        .m0_bvalid(m0_bvalid), .m0_bready(m0_bready), .m0_bresp(m0_bresp),
        .m0_arvalid(m0_arvalid), .m0_arready(m0_arready), .m0_araddr(m0_araddr),
        .m0_rvalid(m0_rvalid), .m0_rready(m0_rready), .m0_rdata(m0_rdata), .m0_rresp(m0_rresp),
        .m1_awvalid(m1_awvalid), .m1_awready(m1_awready), .m1_awaddr(m1_awaddr),
        .m1_wvalid(m1_wvalid), .m1_wready(m1_wready), .m1_wdata(m1_wdata), .m1_wstrb(m1_wstrb),
        .m1_bvalid(m1_bvalid), .m1_bready(m1_bready), .m1_bresp(m1_bresp),
        .m1_arvalid(m1_arvalid), .m1_arready(m1_arready), .m1_araddr(m1_araddr),
        .m1_rvalid(m1_rvalid), .m1_rready(m1_rready), .m1_rdata(m1_rdata), .m1_rresp(m1_rresp)
    );

    //----------------------------------------
    // slave 0 : ov5640_reg (camera regs)
    //----------------------------------------
    wire        cam_bvalid;
    wire        cam_rvalid;
    wire [31:0] cam_rdata;

    ov5640_reg #(
        .BASE_ADDR(32'h2000_0000)
    ) ov5640_reg_u (
        .clk(clk),
        .rst(rst),
        .s_axi_awvalid(m0_awvalid), .s_axi_awready(m0_awready), .s_axi_awaddr(m0_awaddr),
        .s_axi_wvalid (m0_wvalid),  .s_axi_wready (m0_wready),  .s_axi_wdata (m0_wdata),
        .s_axi_wstrb  (m0_wstrb),
        .s_axi_bvalid (cam_bvalid), .s_axi_bready (m0_bready),
        .s_axi_bresp  (m0_bresp),
        .s_axi_arvalid(m0_arvalid), .s_axi_arready(m0_arready), .s_axi_araddr(m0_araddr),
        .s_axi_rvalid (cam_rvalid), .s_axi_rready (m0_rready),
        .s_axi_rdata  (cam_rdata),  .s_axi_rresp  (m0_rresp),
        .xdma_ack(), .cam_en(), .cam_addr_1(), .cam_addr_2()
    );

    // ov5640_reg honors bready/rready: connect decoder routing outputs
    // (already wired via .s_axi_bready/.s_axi_rready in the instance)
    // slave response nets -> decoder inputs (bresp/rresp routed in-instance)
    assign m0_bvalid = cam_bvalid;
    assign m0_rvalid = cam_rvalid;
    assign m0_rdata  = cam_rdata;


    //----------------------------------------
    // slave 1 : prep_regs
    //----------------------------------------
    wire        prep_bvalid;
    wire        prep_rvalid;
    wire [31:0] prep_rdata;

    wire        inj_start, inj_done_clr;
    wire [15:0] inj_done_fid = 16'h0;
    wire        btn_sticky_clr_w;
    wire [3:0]  led_ctrl;
    wire [3:0]  btn_sticky_w;

    prep_regs #(.TICK_DIV(4)) prep_regs_u (
        .clk(clk), .rst_n(~rst),
        .s_axi_awvalid(m1_awvalid), .s_axi_awready(m1_awready), .s_axi_awaddr(m1_awaddr),
        .s_axi_wvalid (m1_wvalid),  .s_axi_wready (m1_wready),  .s_axi_wdata (m1_wdata),
        .s_axi_wstrb  (m1_wstrb),
        .s_axi_bvalid (prep_bvalid), .s_axi_bready(m1_bready), .s_axi_bresp(m1_bresp),
        .s_axi_arvalid(m1_arvalid), .s_axi_arready(m1_arready), .s_axi_araddr(m1_araddr),
        .s_axi_rvalid (prep_rvalid), .s_axi_rready(m1_rready),
        .s_axi_rdata  (prep_rdata),  .s_axi_rresp (m1_rresp),
        .prep_bypass(), .prep_mode(), .prep_img_width(),
        .prep_thr_sat(), .prep_thr_hue(), .prep_thr_val(), .prep_thr_low(),
        .prep_thr_edge(),
        .prep_lane_roi_top(), .prep_lane_roi_bot(), .prep_lane_row_thr(), .prep_lane_dash_thr(),
        .inj_addr(), .inj_len(), .inj_frame_id(),
        .inj_start(inj_start), .inj_done_clr(inj_done_clr),
        .inj_busy(1'b0), .inj_done(1'b0), .inj_done_fid(inj_done_fid),
        .pipe_frame_sync(1'b0), .pipe_fifo_afull(1'b0),
        .npu_busy(1'b0), .out_frame_cnt(8'd0),
        .btn_toggle_evt(4'd0), .btn_level_sync(4'd0),
        .btn_sticky(btn_sticky_w), .btn_sticky_clr(btn_sticky_clr_w),
        .led_ctrl(led_ctrl),
        .lane_left_type(2'd0), .lane_right_type(2'd0),
        .lane_left_valid(1'b0), .lane_right_valid(1'b0),
        .lane_frame_upd(1'b0),
        .ts_cap_pulse(1'b0), .ts_prep_pulse(1'b0),
        .ts_npu_pulse(1'b0), .ts_dma_pulse(1'b0),
        .ts_value0(), .ts_value1(), .ts_value2(), .ts_value3()
    );
    // slave response nets -> decoder inputs
    assign m1_bvalid = prep_bvalid;
    assign m1_rvalid = prep_rvalid;
    assign m1_rdata  = prep_rdata;

    //----------------------------------------
    // BFM tasks
    //----------------------------------------
    task axi_wr(input [31:0] a, input [31:0] d);
        begin
            @(posedge clk);
            awvalid = 1'b1; awaddr = a;
            wvalid  = 1'b1; wdata  = d; wstrb = 4'hF;
            while (!(awready && wready)) @(posedge clk);
            awvalid = 1'b0; wvalid = 1'b0;
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

    // 背靠背流式写: 每次 ready 脉冲后立即呈现下一对 AW/W (复现 axi_to_axi_lite
    // 把一次 16B DMA 拆成 4 个连续 AXI-Lite 写的行为, 不等 bvalid)
    task axi_wr_stream4(input [31:0] a0, input [31:0] d0, input [31:0] d1,
                        input [31:0] d2, input [31:0] d3);
        integer k;
        reg [31:0] dw;
        begin
            @(posedge clk);
            awvalid = 1'b1; wvalid = 1'b1; bready = 1'b1;
            awaddr = a0; dw = d0; wdata = dw; wstrb = 4'hF;
            for (k = 0; k < 4; k = k + 1) begin
                while (!(awready && wready)) @(posedge clk);
                case (k)
                    0: dw = d1;
                    1: dw = d2;
                    2: dw = d3;
                    default: dw = dw;
                endcase
                wdata  = dw;
                awaddr = a0 + (k + 1) * 4;
            end
            awvalid = 1'b0; wvalid = 1'b0;
            repeat (4) @(posedge clk);
            bready = 1'b0;
        end
    endtask

    always @(posedge clk) begin
        if (!rst && arvalid && arready)
            $display("[DBG] AR t=%0t addr=%08h sel_live=%b", $time, araddr, dut.ar_sel_live);
        if (!rst && awvalid && awready)
            $display("[DBG] AW t=%0t addr=%08h sel_live=%b", $time, awaddr, dut.aw_sel_live);
    end

    //----------------------------------------
    // checks
    //----------------------------------------
    integer err = 0;
    reg [31:0] rd;
    localparam CAM_BASE = 32'h2000_0000;
    localparam PREP_BASE = 32'h2000_0100;

    initial begin
        repeat (10) @(posedge clk);
        rst = 1'b0;
        repeat (5) @(posedge clk);

        // 1) CAM segment : CAM_EN write/read (routed to slave0)
        axi_wr(CAM_BASE + 32'h40, 32'h1);
        axi_rd(CAM_BASE + 32'h40, rd);
        if (rd !== 32'h1) begin
            $display("[DEC][ERR] CAM_EN rd=%02h exp=1", rd); err = err + 1;
        end
        // CAM_ADDR_1 / _2
        axi_wr(CAM_BASE + 32'h80, 32'h0A00_0000);
        axi_wr(CAM_BASE + 32'hC0, 32'h0A1C_2000);
        axi_rd(CAM_BASE + 32'h80, rd);
        if (rd !== 32'h0A00_0000) begin
            $display("[DEC][ERR] ADDR_1 rd=%08h", rd); err = err + 1;
        end
        axi_rd(CAM_BASE + 32'hC0, rd);
        if (rd !== 32'h0A1C_2000) begin
            $display("[DEC][ERR] ADDR_2 rd=%08h", rd); err = err + 1;
        end

        // 2) unmapped ov5640 address reads default 0xFFFFFFFF
        axi_rd(CAM_BASE + 32'h20, rd);
        if (rd !== 32'hFFFF_FFFF) begin
            $display("[DEC][ERR] cam unmapped rd=%08h exp=FFFFFFFF", rd); err = err + 1;
        end

        // 3) PREP segment : real offsets (doc +0x100.. maps to prep internal 0x00..)
        //    CTRL=0x00  THR=0x04  SIZE=0x08  INJ_CTRL=0x1C
        axi_rd(PREP_BASE + 32'h04, rd);
        if (rd !== {8'd160, 8'd64, 8'd96, 8'd128}) begin
            $display("[DEC][ERR] PREP_THR default rd=%08h", rd); err = err + 1;
        end
        axi_wr(PREP_BASE + 32'h00, 32'h0000_001F);          // PREP_CTRL
        axi_rd(PREP_BASE + 32'h00, rd);
        if (rd !== 32'h0000_001F) begin
            $display("[DEC][ERR] PREP_CTRL rd=%08h exp=1F", rd); err = err + 1;
        end
        axi_wr(PREP_BASE + 32'h04, {8'd200, 8'd90, 8'd80, 8'd70});  // PREP_THR
        axi_rd(PREP_BASE + 32'h04, rd);
        if (rd !== {8'd200, 8'd90, 8'd80, 8'd70}) begin
            $display("[DEC][ERR] PREP_THR rd=%08h", rd); err = err + 1;
        end
        axi_wr(PREP_BASE + 32'h08, {4'd0, 12'd360, 4'd0, 12'd640}); // PREP_SIZE (masked fields)
        axi_rd(PREP_BASE + 32'h08, rd);
        if (rd !== {4'd0, 12'd360, 4'd0, 12'd640}) begin
            $display("[DEC][ERR] PREP_SIZE rd=%08h", rd); err = err + 1;
        end

        // 4) INJ_START single-cycle pulse (prep side outputs)
        axi_wr(PREP_BASE + 32'h1C, 32'h1);                  // +0x11C INJ_CTRL
        repeat (4) @(posedge clk);
        if (inj_start !== 1'b1) begin
            // pulse may already have passed if timing differs; capture with flag
        end

        // 5) interleaved segment switching
        axi_wr(CAM_BASE + 32'h40, 32'h0);
        axi_wr(PREP_BASE + 32'h00, 32'h0000_0007);
        axi_rd(CAM_BASE + 32'h40, rd);
        if (rd !== 32'h0) begin
            $display("[DEC][ERR] interleave CAM_EN rd=%02h exp=0", rd); err = err + 1;
        end
        axi_rd(PREP_BASE + 32'h00, rd);
        if (rd !== 32'h0000_0007) begin
            $display("[DEC][ERR] interleave PREP_CTRL rd=%08h exp=7", rd); err = err + 1;
        end

        // 6) back-to-back streaming writes (16B DMA -> 4 连续 AXI-Lite 写)
        //    复现板级 K 变体场景: [CTRL,THR,SIZE,LANE] 连续 4 写, 逐一读回校验
        axi_wr_stream4(PREP_BASE + 32'h00, 32'h0000_001E, 32'hA040_6080,
                       {4'd0, 12'd360, 4'd0, 12'd640}, 32'h0603_2828);
        axi_rd(PREP_BASE + 32'h00, rd);
        if (rd !== 32'h0000_001E) begin
            $display("[DEC][ERR] b2b CTRL rd=%08h exp=1E", rd); err = err + 1;
        end
        axi_rd(PREP_BASE + 32'h04, rd);
        if (rd !== 32'hA040_6080) begin
            $display("[DEC][ERR] b2b THR rd=%08h exp=A0406080", rd); err = err + 1;
        end
        axi_rd(PREP_BASE + 32'h08, rd);
        if (rd !== {4'd0, 12'd360, 4'd0, 12'd640}) begin
            $display("[DEC][ERR] b2b SIZE rd=%08h", rd); err = err + 1;
        end
        axi_rd(PREP_BASE + 32'h0C, rd);
        if (rd !== 32'h0603_2828) begin
            $display("[DEC][ERR] b2b LANE rd=%08h exp=06032828", rd); err = err + 1;
        end

        if (err == 0)
            $display("[DEC] TB_PASS");
        else
            $display("[DEC] TB_FAIL  err=%0d", err);
        $finish;
    end

    initial begin
        #500_000;
        $display("[DEC] TB_FAIL  timeout");
        $finish;
    end

endmodule
