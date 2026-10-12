`timescale 1ns/1ps
module boundary_pair #(parameter BURST=8, WIDTH=128, KEEP=WIDTH/8, ID=0, EXPECT=1, EXHAUST=0)(output reg done=0); localparam WAIT=1;
reg  clk=0;
reg  rst=0;
reg  cmd_valid=0;
reg [31:0] cmd_addr=0;
reg [31:0] cmd_len=0;
reg [4 - 1:0] cmd_id=0;
wire  old_cmd_ready, new_cmd_ready;
reg [15:0] data_in_available=0;
reg  abort_req=0;
wire  old_data_in_abort, new_data_in_abort;
reg [WIDTH - 1:0] data_in=0;
reg [KEEP - 1:0] data_in_keep=0;
reg  data_in_valid=0;
wire  old_data_in_last, new_data_in_last;
wire  old_data_in_ready, new_data_in_ready;
wire [4 - 1:0] old_m_axi_awid, new_m_axi_awid;
wire [31:0] old_m_axi_awaddr, new_m_axi_awaddr;
wire [7:0] old_m_axi_awlen, new_m_axi_awlen;
wire [2:0] old_m_axi_awsize, new_m_axi_awsize;
wire [1:0] old_m_axi_awburst, new_m_axi_awburst;
wire  old_m_axi_awlock, new_m_axi_awlock;
wire [3:0] old_m_axi_awcache, new_m_axi_awcache;
wire [2:0] old_m_axi_awprot, new_m_axi_awprot;
wire  old_m_axi_awvalid, new_m_axi_awvalid;
reg  m_axi_awready=0;
wire [WIDTH - 1:0] old_m_axi_wdata, new_m_axi_wdata;
wire [KEEP - 1:0] old_m_axi_wstrb, new_m_axi_wstrb;
wire  old_m_axi_wlast, new_m_axi_wlast;
wire  old_m_axi_wvalid, new_m_axi_wvalid;
reg  m_axi_wready=0;
reg [4 - 1:0] m_axi_bid=0;
reg [1:0] m_axi_bresp=0;
reg  m_axi_bvalid=0;
wire  old_m_axi_bready, new_m_axi_bready;
axi_dma_write_dma_sc_v2_reference #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(BURST),.DATA_WIDTH(WIDTH),.KEEP_WIDTH(KEEP)) old_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(old_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(old_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(old_data_in_last),.data_in_ready(old_data_in_ready),.m_axi_awid(old_m_axi_awid),.m_axi_awaddr(old_m_axi_awaddr),.m_axi_awlen(old_m_axi_awlen),.m_axi_awsize(old_m_axi_awsize),.m_axi_awburst(old_m_axi_awburst),.m_axi_awlock(old_m_axi_awlock),.m_axi_awcache(old_m_axi_awcache),.m_axi_awprot(old_m_axi_awprot),.m_axi_awvalid(old_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(old_m_axi_wdata),.m_axi_wstrb(old_m_axi_wstrb),.m_axi_wlast(old_m_axi_wlast),.m_axi_wvalid(old_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(old_m_axi_bready));
axi_dma_write_dma_sc_v2 #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(BURST),.DATA_WIDTH(WIDTH),.KEEP_WIDTH(KEEP)) new_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(new_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(new_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(new_data_in_last),.data_in_ready(new_data_in_ready),.m_axi_awid(new_m_axi_awid),.m_axi_awaddr(new_m_axi_awaddr),.m_axi_awlen(new_m_axi_awlen),.m_axi_awsize(new_m_axi_awsize),.m_axi_awburst(new_m_axi_awburst),.m_axi_awlock(new_m_axi_awlock),.m_axi_awcache(new_m_axi_awcache),.m_axi_awprot(new_m_axi_awprot),.m_axi_awvalid(new_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(new_m_axi_wdata),.m_axi_wstrb(new_m_axi_wstrb),.m_axi_wlast(new_m_axi_wlast),.m_axi_wvalid(new_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(new_m_axi_bready));

reg [7:0] test_burst=0;
integer off, bl, n, bitn, digit, h, lo, th, binary_count=0, four_count=0, credit_count=0;
reg [31:0] test_addr;
reg [15:0] test_credit;
reg [31:0] rng=32'h26ab93d1 ^ ID;
function automatic reg state4(input integer x);
    case(x) 0:state4=0;1:state4=1;2:state4=1'bx;3:state4=1'bz;endcase
endfunction
function automatic [31:0] next_rng(input [31:0] x);
    reg [31:0] y;
    begin y=x^(x<<13);y=y^(y>>17);next_rng=y^(y<<5);end
endfunction
task check;
reg [7:0] expected_known;
integer page_known;
begin
    #1;
    if(old_dut.burst_len !== test_burst || new_dut.burst_len !== test_burst ||
       old_dut.addr !== test_addr || new_dut.addr !== test_addr)
        $fatal(1,"actual cone stimulus failed to track force/deposit id=%0d",ID);
    if(old_dut.max_burst_len !== new_dut.max_burst_len ||
       old_dut.source_burst_ready !== new_dut.source_burst_ready ||
       old_dut.waiting_source !== new_dut.waiting_source ||
       old_dut.wd_clear !== new_dut.wd_clear || old_dut.wd_step !== new_dut.wd_step) begin
        $display("COUNTEREXAMPLE id=%0d addr=%h burst=%b credit=%b valid=%b refmax=%b dutmax=%b refready=%b dutready=%b",ID,test_addr,test_burst,data_in_available,data_in_valid,old_dut.max_burst_len,new_dut.max_burst_len,old_dut.source_burst_ready,new_dut.source_burst_ready);
        $fatal(1,"boundary mismatch");
    end
    // Independent known-value integer oracle supplements the actual RTL golden.
    // Includes offset=0 (remaining=256 truncated) and all unaligned offsets.
    if(WIDTH==128 && KEEP==16 && (^test_addr[11:0] !== 1'bx) && (^test_burst !== 1'bx)) begin
        page_known=test_addr[11:0];
        expected_known=(page_known+16*test_burst >= 4096) ? (4096-page_known)/16 : test_burst;
        if(old_dut.max_burst_len !== expected_known || new_dut.max_burst_len !== expected_known)
            $fatal(1,"known boundary oracle id=%0d offset=%0d burst=%0d expected=%0d ref=%0d dut=%0d",ID,page_known,test_burst,expected_known,old_dut.max_burst_len,new_dut.max_burst_len);
    end
end
endtask
task apply_addr;
begin old_dut.addr=test_addr;new_dut.addr=test_addr;end
endtask
initial begin
    // Frozen clock: these are actual instantiated combinational RTL cones.
    force old_dut.burst_len=test_burst;
    force new_dut.burst_len=test_burst;
    rst=0; data_in_valid=1; data_in_available=16'hffff; m_axi_wready=1;
    old_dut.trans=1; new_dut.trans=1;
    old_dut.burst_trans=0;new_dut.burst_trans=0;
    old_dut.m_axi_awvalid=0;new_dut.m_axi_awvalid=0;
    old_dut.abort_r=0;new_dut.abort_r=0;
    old_dut.len=8;new_dut.len=8;
    old_dut.available_q=0;new_dut.available_q=0;
    old_dut.wd_cnt=1;new_dut.wd_cnt=1;
    #1;
    if(new_dut.PAGE_ARITH_13_SUPPORTED !== EXPECT) $fatal(1,"static guard id=%0d actual=%b expected=%0d",ID,new_dut.PAGE_ARITH_13_SUPPORTED,EXPECT);
    if(EXHAUST) begin
        for(off=0;off<4096;off=off+1) for(bl=0;bl<256;bl=bl+1) begin
            test_addr=32'ha57cb000|off;test_burst=bl;apply_addr;
            data_in_available=(bl+off)%65536;
            check;binary_count=binary_count+1;
        end
        // credit classes: all 256 thresholds, all low bytes, upper=0,1,255.
        // Every other nonzero known upper byte has the same >= result (true).
        test_addr=32'h1000;apply_addr;
        for(th=0;th<256;th=th+1) for(h=0;h<3;h=h+1) for(lo=0;lo<256;lo=lo+1) begin
            test_burst=th;data_in_available={8'(h==0?0:h==1?1:255),8'(lo)};
            check;
            if(old_dut.source_burst_ready !== (data_in_available >= th)) $fatal(1,"credit class error");
            credit_count=credit_count+1;
        end
    end else begin
        for(n=0;n<2048;n=n+1) begin
            rng=next_rng(rng);test_addr=rng; rng=next_rng(rng);test_burst=rng;
            data_in_available=rng>>8;apply_addr;check;binary_count=binary_count+1;
        end
    end
    // Per-bit X/Z in lower and masked upper addr, burst, credit and valid.
    for(n=0;n<4;n=n+1) for(bitn=0;bitn<32;bitn=bitn+1) for(digit=2;digit<4;digit=digit+1) begin
        test_addr=n==0?0:n==1?4095:n==2?4080:32'hffffffff;
        test_addr[bitn]=state4(digit);test_burst=n==0?0:n==1?1:n==2?255:128;
        data_in_available=256;data_in_valid=1;apply_addr;check;four_count=four_count+1;
    end
    for(n=0;n<4;n=n+1) for(bitn=0;bitn<8;bitn=bitn+1) for(digit=2;digit<4;digit=digit+1) begin
        test_addr=n==0?0:n==1?4095:n==2?4080:1;
        test_burst=n==0?0:n==1?1:n==2?255:128;test_burst[bitn]=state4(digit);
        data_in_available=256;apply_addr;check;four_count=four_count+1;
    end
    for(bitn=0;bitn<16;bitn=bitn+1) for(digit=2;digit<4;digit=digit+1) begin
        test_addr=0;test_burst=127;data_in_available=256;data_in_available[bitn]=state4(digit);
        apply_addr;check;four_count=four_count+1;
    end
    for(digit=0;digit<4;digit=digit+1) begin
        test_addr=4095;test_burst=1;data_in_available=1;data_in_valid=state4(digit);
        apply_addr;check;four_count=four_count+1;
    end
    for(n=0;n<4096;n=n+1) begin
        for(bitn=0;bitn<32;bitn=bitn+1) begin rng=next_rng(rng);test_addr[bitn]=state4(rng%4);end
        for(bitn=0;bitn<8;bitn=bitn+1) begin rng=next_rng(rng);test_burst[bitn]=state4(rng%4);end
        for(bitn=0;bitn<16;bitn=bitn+1) begin rng=next_rng(rng);data_in_available[bitn]=state4(rng%4);end
        rng=next_rng(rng);data_in_valid=state4(rng%4);apply_addr;check;four_count=four_count+1;
    end
    $display("BOUNDARY_PAIR_PASS id=%0d specialized=%0d binary=%0d fourstate=%0d credit=%0d",ID,new_dut.PAGE_ARITH_13_SUPPORTED,binary_count,four_count,credit_count);
    done=1;
end
endmodule

module tb_boundary;
wire [11:0] done;
boundary_pair #(.ID(0),.BURST(8),.EXHAUST(1)) p0(done[0]);
boundary_pair #(.ID(1),.BURST(0)) p1(done[1]);
boundary_pair #(.ID(2),.BURST(1)) p2(done[2]);
boundary_pair #(.ID(3),.BURST(255)) p3(done[3]);
boundary_pair #(.ID(4),.BURST(-1),.EXPECT(0)) p4(done[4]);
boundary_pair #(.ID(5),.BURST(256),.EXPECT(0)) p5(done[5]);
boundary_pair #(.ID(6),.BURST(32'd8),.EXPECT(0)) p6(done[6]);
boundary_pair #(.ID(7),.BURST(8'd8),.EXPECT(0)) p7(done[7]);
boundary_pair #(.ID(8),.BURST(64'd8),.EXPECT(0)) p8(done[8]);
boundary_pair #(.ID(9),.WIDTH(64),.EXPECT(0)) p9(done[9]);
boundary_pair #(.ID(10),.WIDTH(256),.EXPECT(0)) p10(done[10]);
boundary_pair #(.ID(11),.WIDTH(128),.KEEP(8),.EXPECT(0)) p11(done[11]);
initial begin wait(&done);$display("BOUNDARY_ALL_PASS pairs=12");$finish;end
initial begin #2000000;$fatal(1,"boundary timeout");end
endmodule
