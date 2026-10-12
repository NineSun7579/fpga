`timescale 1ns/1ps
//============================================================================
// tb.sv : four-master DDR write arbiter scoreboard (cam1..cam4)
//
// Adapted from sim/cam3_arb_test/tb.sv. Four behavioral masters present
// independent AW/W bursts and a behavioral slave provides AW/W/B
// backpressure. The scoreboard checks AW field routing, W data/strb/last,
// ready/valid routing, B ID/response routing, transaction counts, single
// outstanding ownership, W payload stability during stalls, and strict
// round-robin grant order/fairness.
//
// MODE=0 : deterministic W backpressure
// MODE=1 : pseudorandom (LFSR) W backpressure
// MODE=2 : AW-stability under AWREADY stall (expected to PASS with the
//          latched-winner arbitration; the pre-2026-09-26 combinational
//          design is documented to FAIL here)
//============================================================================
module tb;
reg clk=0, rst=1;
always #5 clk=~clk;
reg [3:0] awid [0:3];
reg [31:0] awaddr [0:3];
reg [7:0] awlen [0:3];
reg [2:0] awsize [0:3];
reg [1:0] awburst [0:3];
reg  awlock [0:3];
reg [3:0] awcache [0:3];
reg [2:0] awprot [0:3];
reg  awvalid [0:3];
wire  awready [0:3];
reg [127:0] wdata [0:3];
reg [15:0] wstrb [0:3];
reg  wlast [0:3];
reg  wvalid [0:3];
wire  wready [0:3];
wire [3:0] bid [0:3];
wire [1:0] bresp [0:3];
wire  bvalid [0:3];
reg  bready [0:3];
wire [3:0] s_awid;
wire [31:0] s_awaddr;
wire [7:0] s_awlen;
wire [2:0] s_awsize;
wire [1:0] s_awburst;
wire  s_awlock;
wire [3:0] s_awcache;
wire [2:0] s_awprot;
wire  s_awvalid;
reg  s_awready;
wire [127:0] s_wdata;
wire [15:0] s_wstrb;
wire  s_wlast;
wire  s_wvalid;
reg  s_wready;
reg [3:0] s_bid;
reg [1:0] s_bresp;
reg  s_bvalid;
wire  s_bready;
ddr_w_arb dut (
.clk(clk),
.rst(rst),
.m0_awid(awid[0]),
.m0_awaddr(awaddr[0]),
.m0_awlen(awlen[0]),
.m0_awsize(awsize[0]),
.m0_awburst(awburst[0]),
.m0_awlock(awlock[0]),
.m0_awcache(awcache[0]),
.m0_awprot(awprot[0]),
.m0_awvalid(awvalid[0]),
.m0_awready(awready[0]),
.m0_wdata(wdata[0]),
.m0_wstrb(wstrb[0]),
.m0_wlast(wlast[0]),
.m0_wvalid(wvalid[0]),
.m0_wready(wready[0]),
.m0_bid(bid[0]),
.m0_bresp(bresp[0]),
.m0_bvalid(bvalid[0]),
.m0_bready(bready[0]),
.m1_awid(awid[1]),
.m1_awaddr(awaddr[1]),
.m1_awlen(awlen[1]),
.m1_awsize(awsize[1]),
.m1_awburst(awburst[1]),
.m1_awlock(awlock[1]),
.m1_awcache(awcache[1]),
.m1_awprot(awprot[1]),
.m1_awvalid(awvalid[1]),
.m1_awready(awready[1]),
.m1_wdata(wdata[1]),
.m1_wstrb(wstrb[1]),
.m1_wlast(wlast[1]),
.m1_wvalid(wvalid[1]),
.m1_wready(wready[1]),
.m1_bid(bid[1]),
.m1_bresp(bresp[1]),
.m1_bvalid(bvalid[1]),
.m1_bready(bready[1]),
.m2_awid(awid[2]),
.m2_awaddr(awaddr[2]),
.m2_awlen(awlen[2]),
.m2_awsize(awsize[2]),
.m2_awburst(awburst[2]),
.m2_awlock(awlock[2]),
.m2_awcache(awcache[2]),
.m2_awprot(awprot[2]),
.m2_awvalid(awvalid[2]),
.m2_awready(awready[2]),
.m2_wdata(wdata[2]),
.m2_wstrb(wstrb[2]),
.m2_wlast(wlast[2]),
.m2_wvalid(wvalid[2]),
.m2_wready(wready[2]),
.m2_bid(bid[2]),
.m2_bresp(bresp[2]),
.m2_bvalid(bvalid[2]),
.m2_bready(bready[2]),
.m3_awid(awid[3]),
.m3_awaddr(awaddr[3]),
.m3_awlen(awlen[3]),
.m3_awsize(awsize[3]),
.m3_awburst(awburst[3]),
.m3_awlock(awlock[3]),
.m3_awcache(awcache[3]),
.m3_awprot(awprot[3]),
.m3_awvalid(awvalid[3]),
.m3_awready(awready[3]),
.m3_wdata(wdata[3]),
.m3_wstrb(wstrb[3]),
.m3_wlast(wlast[3]),
.m3_wvalid(wvalid[3]),
.m3_wready(wready[3]),
.m3_bid(bid[3]),
.m3_bresp(bresp[3]),
.m3_bvalid(bvalid[3]),
.m3_bready(bready[3]),
.s_awid(s_awid),
.s_awaddr(s_awaddr),
.s_awlen(s_awlen),
.s_awsize(s_awsize),
.s_awburst(s_awburst),
.s_awlock(s_awlock),
.s_awcache(s_awcache),
.s_awprot(s_awprot),
.s_awvalid(s_awvalid),
.s_awready(s_awready),
.s_wdata(s_wdata),
.s_wstrb(s_wstrb),
.s_wlast(s_wlast),
.s_wvalid(s_wvalid),
.s_wready(s_wready),
.s_bid(s_bid),
.s_bresp(s_bresp),
.s_bvalid(s_bvalid),
.s_bready(s_bready)
);
integer mode=0, cycle=0, i, j, selected, active=-1, total=0, delay_b=-1;
integer ac[0:3], wc[0:3], bc[0:3], beat[0:3];
integer wstalls=0, bstalls=0, maxgap[0:3], lastgrant[0:3];
reg [31:0] rng=32'h13579bdf;
reg [63:0] held_aw;
reg held_w=0;
reg [144:0] held_payload;
function automatic [127:0] data_for(input integer m,t,b);
    data_for={32'hca030000 | m, 32'h12000000 | t, 32'h34000000 | b, 32'h56000000 | (m<<16) | (t<<8) | b};
endfunction
function automatic integer length_for(input integer m,t);
    length_for=1+((m*3+t)%8);
endfunction
task automatic fail(input string reason);
    $display("FAIL mode=%0d cycle=%0d active=%0d: %s",mode,cycle,active,reason);
    $fatal(1,"scoreboard failure");
endtask
task automatic drive_master(input integer m);
    awid[m]=(m*5+ac[m])%16;
    awaddr[m]=32'h10000000+(m<<20)+(ac[m]<<8);
    awlen[m]=length_for(m,ac[m])-1;
    awsize[m]=4; awburst[m]=1; awlock[m]=ac[m]%2;
    awcache[m]=(m+ac[m])%16; awprot[m]=(m+ac[m])%8;
    awvalid[m]=(ac[m]<24);
    wvalid[m]=(bc[m]<ac[m]) && (beat[m]<length_for(m,bc[m]));
    wdata[m]=data_for(m,bc[m],beat[m]);
    wstrb[m]=16'hffff ^ (16'h1<<((m+beat[m])%16));
    wlast[m]=(beat[m]==length_for(m,bc[m])-1);
    bready[m]=(cycle%7>=3);
endtask
initial begin
    if ($value$plusargs("MODE=%d",mode)) begin end
    s_awready=1; s_wready=0; s_bvalid=0; s_bid=0; s_bresp=0;
    for(i=0;i<4;i=i+1) begin
        ac[i]=0;wc[i]=0;bc[i]=0;beat[i]=0;maxgap[i]=0;lastgrant[i]=i-4;
        drive_master(i); awvalid[i]=0;
    end
    repeat(4) @(negedge clk);
    rst=0;
    if(mode==2) begin
        s_awready=0;
        awvalid[2]=1;
        @(posedge clk); #1;
        held_aw={s_awid,s_awaddr,s_awlen,s_awsize,s_awburst,s_awlock,s_awcache,s_awprot};
        $display("AW_STALL initial id=%h addr=%h (m2)",s_awid,s_awaddr);
        @(negedge clk); awvalid[0]=1;
        @(posedge clk); #1;
        if(!s_awvalid || held_aw !== {s_awid,s_awaddr,s_awlen,s_awsize,s_awburst,s_awlock,s_awcache,s_awprot})
            $display("AW_STABILITY_FAIL: no handshake, m2 still valid and stable, newly arriving m0 changes slave payload to id=%h addr=%h",s_awid,s_awaddr);
        else $display("AW_STABILITY_PASS");
        $finish;
    end
    for(i=0;i<4;i=i+1) drive_master(i);
    forever begin
        @(posedge clk);
        cycle=cycle+1;
        if(cycle>40000) fail("timeout");
        if(held_w && (!s_wvalid || held_payload !== {s_wdata,s_wstrb,s_wlast})) fail("W changed while stalled");
        held_w=s_wvalid && !s_wready;
        held_payload={s_wdata,s_wstrb,s_wlast};
        selected=-1;
        if(s_wvalid !== ((active>=0) ? wvalid[active] : 1'b0)) fail("WVALID route");
        for(j=0;j<4;j=j+1) begin
            if(awready[j] && (!awvalid[j] || active>=0)) fail("unexpected AWREADY");
            if(awready[j] && awvalid[j]) begin
                if(selected!=-1) fail("multiple AW accepts");
                selected=j;
            end
            if(wready[j] !== ((active==j) && s_wready)) fail("WREADY route");
            if(bvalid[j] !== ((active==j) && s_bvalid)) fail("BVALID route");
            if(bvalid[j] && (bid[j] !== s_bid || bresp[j] !== s_bresp)) fail("B payload route");
        end
        if(s_bready !== ((active>=0) ? bready[active] : 1'b0)) fail("BREADY route");
        if((selected>=0) !== (s_awvalid && s_awready)) fail("AW handshake mismatch");
        if(selected>=0) begin
            if(active!=-1) fail("multiple outstanding transactions");
            if(selected!=total%4) fail("round robin fairness/order");
            if({s_awid,s_awaddr,s_awlen,s_awsize,s_awburst,s_awlock,s_awcache,s_awprot} !==
               {awid[selected],awaddr[selected],awlen[selected],awsize[selected],awburst[selected],awlock[selected],awcache[selected],awprot[selected]}) fail("AW payload route");
            if(total-lastgrant[selected]>maxgap[selected]) maxgap[selected]=total-lastgrant[selected];
            lastgrant[selected]=total;
            active=selected; ac[selected]=ac[selected]+1; total=total+1;
        end
        if(s_wvalid && !s_wready) wstalls=wstalls+1;
        if(s_wvalid && s_wready) begin
            if(active<0) fail("W without AW");
            if(s_wdata !== data_for(active,bc[active],beat[active])) fail("W data/order");
            if(s_wstrb !== (16'hffff ^ (16'h1<<((active+beat[active])%16)))) fail("WSTRB");
            if(s_wlast !== (beat[active]==length_for(active,bc[active])-1)) fail("WLAST/length");
            wc[active]=wc[active]+1; beat[active]=beat[active]+1;
            if(s_wlast) delay_b=3+(total%6);
        end
        if(s_bvalid && !s_bready) bstalls=bstalls+1;
        if(s_bvalid && s_bready) begin
            if(active<0) fail("B without owner");
            if(beat[active]!=length_for(active,bc[active])) fail("early B");
            bc[active]=bc[active]+1; beat[active]=0;active=-1;
        end
        if(bc[0]==24 && bc[1]==24 && bc[2]==24 && bc[3]==24) begin
            if(wstalls==0 || bstalls==0) fail("missing backpressure coverage");
            for(j=0;j<4;j=j+1) begin
                if(ac[j]!=24 || wc[j]!=108 || maxgap[j]!=4) fail("final counts/fairness");
                $display("MASTER %0d AW=%0d W=%0d B=%0d max_grant_gap=%0d",j,ac[j],wc[j],bc[j],maxgap[j]);
            end
            $display("PASS THROUGHPUT mode=%0d cycles=%0d AW=96 W=432 B=96 W_stall_cycles=%0d B_stall_cycles=%0d",mode,cycle,wstalls,bstalls);
            $finish;
        end
        @(negedge clk);
        rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
        s_wready=(mode==0) ? (cycle%5>=2) : (rng[0] && rng[3]);
        if(active<0) s_bvalid=0;
        if(delay_b>=0) begin
            if(delay_b==0) begin
                s_bvalid=1; s_bid=(active*5+bc[active])%16; s_bresp=bc[active]%4;
                delay_b=-1;
            end else delay_b=delay_b-1;
        end
        for(i=0;i<4;i=i+1) drive_master(i);
    end
end
endmodule
