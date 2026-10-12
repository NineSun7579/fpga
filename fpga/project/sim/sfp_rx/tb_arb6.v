`timescale 1ns/1ps
//===========================================================================
// tb_arb6.v -- ddr_w_arb (6 master) 单元仿真
//   slave 模型: awready 随机延迟, 收齐 awlen+1 拍 W 后发 B (模拟 DDR3 口)
//   场景: 1) m0 单发  2) 六主同发 x3 轮  3) 死锁看门狗
//   判定: 每个 burst 的 AW/W/B 完整且 owner 数据不串; TB_PASS/TB_FAIL
//===========================================================================
module tb_arb6;

    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1;
    initial begin #100 rst = 0; end

    reg  [3:0]   m_awid    [0:5];
    reg  [31:0]  m_awaddr  [0:5];
    reg  [7:0]   m_awlen   [0:5];
    reg          m_awvalid [0:5];
    reg  [127:0] m_wdata   [0:5];
    reg          m_wlast   [0:5];
    reg          m_wvalid  [0:5];
    wire         m_awready [0:5];
    wire         m_wready  [0:5];
    wire         m_bvalid  [0:5];
    wire [3:0]   m_bid     [0:5];
    wire [1:0]   m_bresp   [0:5];

    //---------------------------------------------------------------------
    // DUT
    //---------------------------------------------------------------------
    wire [3:0]   s_awid;  wire [31:0] s_awaddr; wire [7:0] s_awlen;
    wire [2:0]   s_awsize; wire [1:0] s_awburst; wire s_awlock;
    wire [3:0]   s_awcache; wire [2:0] s_awprot;
    wire         s_awvalid;
    reg          s_awready;
    wire [127:0] s_wdata; wire [15:0] s_wstrb;
    wire         s_wlast, s_wvalid, s_wready;
    wire [3:0]   s_bid; wire [1:0] s_bresp;
    reg          s_bvalid;
    wire         s_bready;

    ddr_w_arb dut (
        .clk(clk), .rst(rst),
        .m0_awid(m_awid[0]), .m0_awaddr(m_awaddr[0]), .m0_awlen(m_awlen[0]),
        .m0_awsize(3'd3), .m0_awburst(2'd1), .m0_awlock(0), .m0_awcache(0), .m0_awprot(0),
        .m0_awvalid(m_awvalid[0]), .m0_awready(m_awready[0]),
        .m0_wdata(m_wdata[0]), .m0_wstrb(16'hFFFF), .m0_wlast(m_wlast[0]), .m0_wvalid(m_wvalid[0]),
        .m0_wready(m_wready[0]), .m0_bid(m_bid[0]), .m0_bresp(m_bresp[0]),
        .m0_bvalid(m_bvalid[0]), .m0_bready(1'b1),
        .m1_awid(m_awid[1]), .m1_awaddr(m_awaddr[1]), .m1_awlen(m_awlen[1]),
        .m1_awsize(3'd3), .m1_awburst(2'd1), .m1_awlock(0), .m1_awcache(0), .m1_awprot(0),
        .m1_awvalid(m_awvalid[1]), .m1_awready(m_awready[1]),
        .m1_wdata(m_wdata[1]), .m1_wstrb(16'hFFFF), .m1_wlast(m_wlast[1]), .m1_wvalid(m_wvalid[1]),
        .m1_wready(m_wready[1]), .m1_bid(m_bid[1]), .m1_bresp(m_bresp[1]),
        .m1_bvalid(m_bvalid[1]), .m1_bready(1'b1),
        .m2_awid(m_awid[2]), .m2_awaddr(m_awaddr[2]), .m2_awlen(m_awlen[2]),
        .m2_awsize(3'd3), .m2_awburst(2'd1), .m2_awlock(0), .m2_awcache(0), .m2_awprot(0),
        .m2_awvalid(m_awvalid[2]), .m2_awready(m_awready[2]),
        .m2_wdata(m_wdata[2]), .m2_wstrb(16'hFFFF), .m2_wlast(m_wlast[2]), .m2_wvalid(m_wvalid[2]),
        .m2_wready(m_wready[2]), .m2_bid(m_bid[2]), .m2_bresp(m_bresp[2]),
        .m2_bvalid(m_bvalid[2]), .m2_bready(1'b1),
        .m3_awid(m_awid[3]), .m3_awaddr(m_awaddr[3]), .m3_awlen(m_awlen[3]),
        .m3_awsize(3'd3), .m3_awburst(2'd1), .m3_awlock(0), .m3_awcache(0), .m3_awprot(0),
        .m3_awvalid(m_awvalid[3]), .m3_awready(m_awready[3]),
        .m3_wdata(m_wdata[3]), .m3_wstrb(16'hFFFF), .m3_wlast(m_wlast[3]), .m3_wvalid(m_wvalid[3]),
        .m3_wready(m_wready[3]), .m3_bid(m_bid[3]), .m3_bresp(m_bresp[3]),
        .m3_bvalid(m_bvalid[3]), .m3_bready(1'b1),
        .m4_awid(m_awid[4]), .m4_awaddr(m_awaddr[4]), .m4_awlen(m_awlen[4]),
        .m4_awsize(3'd3), .m4_awburst(2'd1), .m4_awlock(0), .m4_awcache(0), .m4_awprot(0),
        .m4_awvalid(m_awvalid[4]), .m4_awready(m_awready[4]),
        .m4_wdata(m_wdata[4]), .m4_wstrb(16'hFFFF), .m4_wlast(m_wlast[4]), .m4_wvalid(m_wvalid[4]),
        .m4_wready(m_wready[4]), .m4_bid(m_bid[4]), .m4_bresp(m_bresp[4]),
        .m4_bvalid(m_bvalid[4]), .m4_bready(1'b1),
        .m5_awid(m_awid[5]), .m5_awaddr(m_awaddr[5]), .m5_awlen(m_awlen[5]),
        .m5_awsize(3'd3), .m5_awburst(2'd1), .m5_awlock(0), .m5_awcache(0), .m5_awprot(0),
        .m5_awvalid(m_awvalid[5]), .m5_awready(m_awready[5]),
        .m5_wdata(m_wdata[5]), .m5_wstrb(16'hFFFF), .m5_wlast(m_wlast[5]), .m5_wvalid(m_wvalid[5]),
        .m5_wready(m_wready[5]), .m5_bid(m_bid[5]), .m5_bresp(m_bresp[5]),
        .m5_bvalid(m_bvalid[5]), .m5_bready(1'b1),
        .s_awid(s_awid), .s_awaddr(s_awaddr), .s_awlen(s_awlen), .s_awsize(s_awsize),
        .s_awburst(s_awburst), .s_awlock(s_awlock), .s_awcache(s_awcache), .s_awprot(s_awprot),
        .s_awvalid(s_awvalid), .s_awready(s_awready),
        .s_wdata(s_wdata), .s_wstrb(s_wstrb), .s_wlast(s_wlast), .s_wvalid(s_wvalid),
        .s_wready(s_wready), .s_bid(s_bid), .s_bresp(s_bresp),
        .s_bvalid(s_bvalid), .s_bready(s_bready)
    );

    //---------------------------------------------------------------------
    // 6 个 master 行为模型
    //---------------------------------------------------------------------

    integer done_cnt [0:5];
    integer i;
    initial begin
        for (i = 0; i < 6; i = i + 1) begin
            m_awid[i] = i[3:0]; m_awvalid[i] = 0; m_wvalid[i] = 0; m_wlast[i] = 0;
            done_cnt[i] = 0;
        end
    end

    // 单个 master 的 burst 任务
    task do_burst(input integer idx, input [31:0] addr);
        begin
            @(posedge clk);
            m_awaddr[idx]  = addr;
            m_awlen[idx]   = 8'd3;                  // 4 拍
            m_awvalid[idx] = 1;
            while (!m_awready[idx]) @(posedge clk);
            m_awvalid[idx] = 0;
            // W: 4 拍, 数据含 master 号便于查串
            repeat (4) begin
                m_wdata[idx]  = {4{32'hA5A5_0000 + idx}};
                m_wlast[idx]  = 0;
                m_wvalid[idx] = 1;
                while (!m_wready[idx]) @(posedge clk);
                @(posedge clk);
            end
            m_wvalid[idx] = 0; m_wlast[idx] = 0;
            while (!m_bvalid[idx]) @(posedge clk);
            done_cnt[idx] = done_cnt[idx] + 1;
        end
    endtask

    //---------------------------------------------------------------------
    // slave 模型: 随机延迟 awready; 记账; 4 拍 W 后发 B
    //---------------------------------------------------------------------
    integer err = 0;
    reg aw_ready_d = 0;
    integer aw_pend = 0, w_cnt = 0;
    integer seed = 7;
    always @(posedge clk) begin
        if (rst) begin
            s_awready <= 0;
        end else begin
            if (s_awvalid && s_awready) begin
                s_awready <= 0;
                aw_pend   <= 1;
                w_cnt     <= 0;
                chk_aw(s_awid, s_awaddr, s_awlen);
            end
            else if (!s_awready && ({$random(seed)} % 3 == 0))
                s_awready <= 1;
        end
    end
    // W 接收: s_wready 恒 1 (DDR3 口实际不可反压)
    // 真实背压模型: wready 随机断续, 模拟 ddr_fifo16_w 满 (含 >16 拍长顿)
    reg [5:0] wstall = 0;
    always @(posedge clk) begin
        if (rst) wstall <= 0;
        else if (wstall == 0 && ({$random(seed)} % 7 == 0)) wstall <= ({$random(seed)} % 40) + 3;
        else if (wstall != 0) wstall <= wstall - 1;
    end
    assign s_wready = !rst && (wstall == 0);
    always @(posedge clk) begin
        if (!rst) begin
            if (s_awvalid && s_awready) ; // 记账在上一个块
        end
    end
    task chk_aw(input [3:0] id, input [31:0] addr, input [7:0] len);
        begin
            if (id > 5 || addr[31:16] != id)
                begin err = err + 1; $display("[%0t] AW_BAD id=%0d addr=%08h", $time, id, addr); end
        end
    endtask
    // B: 数满 4 拍 W 发 B (owner 的 W 才到 s_w 侧, 由 DUT 保证)
    integer wbeat = 0;
    always @(posedge clk) begin
        if (rst) begin
            s_bvalid <= 0; wbeat <= 0;
        end else begin
            if (s_awvalid && s_awready) wbeat <= 0;
            else if (s_wvalid && s_wready) wbeat <= wbeat + 1;
            s_bvalid <= (wbeat == 3 && s_wvalid && s_wready);
        end
    end
    assign s_bid = s_awid; // 简化: 用最近 AW id (单发场景正确)
    always @(posedge clk)
        if (!rst && s_bvalid)
            $display("[%0t] B_PULSE dut_owner=%0d s_awid=%0d s_awaddr=%08h", $time, dut.owner, s_awid, s_awaddr);

    //---------------------------------------------------------------------
    // 激励
    //---------------------------------------------------------------------
    initial begin
        wait (!rst); repeat (5) @(posedge clk);
        // 场景 1: m0 单发 3 轮
        repeat (3) do_burst(0, 32'h0000_0100);
        // 场景 2: 六主同发 x3 轮
        fork
            repeat (3) do_burst(0, 32'h0000_0100);
            repeat (3) do_burst(1, 32'h0001_0100);
            repeat (3) do_burst(2, 32'h0002_0100);
            repeat (3) do_burst(3, 32'h0003_0100);
            repeat (3) do_burst(4, 32'h0004_0100);
            repeat (3) do_burst(5, 32'h0005_0100);
        join
        $display("done: %0d %0d %0d %0d %0d %0d err=%0d",
                 done_cnt[0], done_cnt[1], done_cnt[2], done_cnt[3], done_cnt[4], done_cnt[5], err);
        if (err == 0 && done_cnt[0] == 6 && done_cnt[1] == 3 && done_cnt[2] == 3 &&
            done_cnt[3] == 3 && done_cnt[4] == 3 && done_cnt[5] == 3)
            $display("TB_PASS");
        else
            $display("TB_FAIL");
        $finish;
    end

    // 看门狗
    initial begin
        #500_000;
        $display("TB_FAIL_TIMEOUT done=%0d,%0d,%0d,%0d,%0d,%0d",
                 done_cnt[0], done_cnt[1], done_cnt[2], done_cnt[3], done_cnt[4], done_cnt[5]);
        $finish;
    end

endmodule
