`timescale 1ns/1ps
// Directed checks for registered grants, all AW fields, ownership and reset.
module tb_arb6_registered;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1;
    reg [5:0] av = 0, bv_ready = 0, wv = 0;
    wire [5:0] ar, bv, wr;
    reg [3:0] id [0:5];
    reg [31:0] addr [0:5];
    reg [7:0] len [0:5];
    reg [2:0] size [0:5], prot [0:5];
    reg [1:0] burst [0:5];
    reg lock [0:5];
    reg [3:0] cache [0:5];
    wire [3:0] aid;
    wire [31:0] aaddr;
    wire [7:0] alen;
    wire [2:0] asize, aprot;
    wire [1:0] aburst;
    wire alock;
    wire [3:0] acache;
    wire aval, wval, wlast, bready;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    reg aready = 1, wready = 1, bvalid = 0;
    reg [3:0] bid = 0;
    wire [3:0] mbid [0:5];
    wire [1:0] mbresp [0:5];
`define MASTER(N) \
    .m``N``_awid(id[N]), .m``N``_awaddr(addr[N]), .m``N``_awlen(len[N]), \
    .m``N``_awsize(size[N]), .m``N``_awburst(burst[N]), .m``N``_awlock(lock[N]), \
    .m``N``_awcache(cache[N]), .m``N``_awprot(prot[N]), \
    .m``N``_awvalid(av[N]), .m``N``_awready(ar[N]), \
    .m``N``_wdata(128'h100 + N), .m``N``_wstrb(16'hffff), .m``N``_wlast(1'b1), \
    .m``N``_wvalid(wv[N]), .m``N``_wready(wr[N]), \
    .m``N``_bid(mbid[N]), .m``N``_bresp(mbresp[N]), \
    .m``N``_bvalid(bv[N]), .m``N``_bready(bv_ready[N]),
    ddr_w_arb dut (
        .clk(clk), .rst(rst),
        `MASTER(0) `MASTER(1) `MASTER(2) `MASTER(3) `MASTER(4) `MASTER(5)
        .s_awid(aid), .s_awaddr(aaddr), .s_awlen(alen), .s_awsize(asize),
        .s_awburst(aburst), .s_awlock(alock), .s_awcache(acache), .s_awprot(aprot),
        .s_awvalid(aval), .s_awready(aready),
        .s_wdata(wdata), .s_wstrb(wstrb), .s_wlast(wlast),
        .s_wvalid(wval), .s_wready(wready),
        .s_bid(bid), .s_bresp(2'b10), .s_bvalid(bvalid), .s_bready(bready)
    );
`undef MASTER
    wire [56:0] payload = {aid, aaddr, alen, asize, aburst, alock, acache, aprot};
    reg [56:0] held;
    integer i, n;
    reg passed = 0;
    task tick;
        begin @(posedge clk); #1; @(negedge clk); end
    endtask
    task check(input bit ok, input string msg);
        if (!ok) $fatal(1, "TB_FAIL: %s at %0t", msg, $time);
    endtask
    task reset_check;
        begin
            rst = 1;
            tick;
            check(!aval && ar == 0 && !wval && wr == 0 && bv == 0 && !bready,
                  "reset clears grants, owner and response routing");
            av = 0; wv = 0; bvalid = 0; bv_ready = 0;
            rst = 0;
        end
    endtask
    task complete_owner(input integer owner);
        begin
            check(!aval && ar == 0, "busy blocks all AW");
            wv = 6'b111111;
            #1;
            check(wval && wr == (6'b1 << owner) && wdata == 128'h100 + owner &&
                  wstrb == 16'hffff && wlast, "only owner's W is routed");
            wready = 0;
            tick;
            check(wval && wr == 0 && wdata == 128'h100 + owner, "W stall routing");
            wready = 1;
            tick;
            wv = 0;
            bid = owner; bvalid = 1;
            repeat (4) begin
                #1;
                check(!aval && ar == 0 && bv == (6'b1 << owner) && !bready &&
                      mbid[owner] == owner && mbresp[owner] == 2'b10,
                      "stalled B retains owner and blocks re-arbitration");
                tick;
            end
            bv_ready = 6'b1 << owner;
            #1;
            check(bready, "owner accepts B");
            tick;
            bvalid = 0; bv_ready = 0;
            check(!aval && ar == 0, "B completion cannot bypass grant register");
        end
    endtask
    initial begin
        for (i = 0; i < 6; i = i + 1) begin
            id[i] = i; addr[i] = 32'h12340000 + i * 256;
            len[i] = i * 13; size[i] = i; burst[i] = i % 3;
            lock[i] = i % 2; cache[i] = i + 8; prot[i] = 5 - i;
        end
        @(negedge clk);
        reset_check;
        // Ready is already high: no source can accept before the grant edge.
        av = 6'b100000;
        #1;
        check(!aval && ar == 0, "no fresh combinational grant when ready high");
        aready = 0;
        tick;
        check(aval && aid == 5 && ar == 0, "registered master 5 is presented");
        held = payload;
        // A higher priority contender arrives after AWVALID; change every
        // non-selected payload too, while the selected source obeys AXI.
        av = 6'b111111;
        repeat (5) begin
            for (i = 0; i < 5; i = i + 1) begin
                addr[i] = addr[i] + 1; len[i] = len[i] + 1;
                id[i] = id[i] + 1; size[i] = size[i] + 1;
                burst[i] = burst[i] + 1; lock[i] = ~lock[i];
                cache[i] = cache[i] + 1; prot[i] = prot[i] + 1;
            end
            #1;
            check(aval && payload === held && ar == 0, "all AW fields stable under stall");
            tick;
        end
        aready = 1;
        #1;
        check(ar == 6'b100000, "only registered source receives AWREADY");
        tick;
        av[5] = 0;
        complete_owner(5);
        // Reset round-robin; keep all six requests asserted for three rounds.
        reset_check;
        av = 6'b111111;
        for (n = 0; n < 18; n = n + 1) begin
            #1;
            check(!aval && ar == 0, "idle must first register selection");
            tick;
            check(aval && ar == (6'b1 << (n % 6)), "six-master round-robin order");
            check(payload === {id[n%6], addr[n%6], len[n%6], size[n%6],
                  burst[n%6], lock[n%6], cache[n%6], prot[n%6]}, "selected AW payload");
            tick;
            complete_owner(n % 6);
        end
        // Reset with a pending stalled AW, then reset during a stalled B.
        aready = 0;
        tick;
        check(aval, "pending AW before reset");
        reset_check;
        aready = 1; av = 6'b000100;
        tick; tick;
        av = 0; bvalid = 1;
        #1;
        check(bv == 6'b000100 && !bready, "pending B before reset");
        reset_check;
        av = 6'b111111;
        tick;
        check(ar == 6'b000001, "reset restarts round-robin at master zero");
        passed = 1;
        $display("TB_PASS_REGISTERED: AW registration/stability, 18 fair grants, W/B stalls, reset");
        $finish;
    end
    initial begin #100000; $fatal(1, "TB_FAIL_TIMEOUT"); end
endmodule
