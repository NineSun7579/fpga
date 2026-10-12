`timescale 1ns/1ps
module tb;
reg clk=0, rst=1;
always #5 clk=~clk;
@@DECL@@
ddr_w_arb dut (
@@CONNECT@@
);
integer mode=0, cycle=0, i, j, selected, active=-1, total=0, delay_b=-1;
integer ac[0:2], wc[0:2], bc[0:2], beat[0:2];
integer wstalls=0, bstalls=0, maxgap[0:2], lastgrant[0:2];
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
    for(i=0;i<3;i=i+1) begin
        ac[i]=0;wc[i]=0;bc[i]=0;beat[i]=0;maxgap[i]=0;lastgrant[i]=i-3;
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
    for(i=0;i<3;i=i+1) drive_master(i);
    forever begin
        @(posedge clk);
        cycle=cycle+1;
        if(cycle>20000) fail("timeout");
        if(held_w && (!s_wvalid || held_payload !== {s_wdata,s_wstrb,s_wlast})) fail("W changed while stalled");
        held_w=s_wvalid && !s_wready;
        held_payload={s_wdata,s_wstrb,s_wlast};
        selected=-1;
        if(s_wvalid !== ((active>=0) ? wvalid[active] : 1'b0)) fail("WVALID route");
        for(j=0;j<3;j=j+1) begin
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
            if(selected!=total%3) fail("round robin fairness/order");
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
        if(bc[0]==24 && bc[1]==24 && bc[2]==24) begin
            if(wstalls==0 || bstalls==0) fail("missing backpressure coverage");
            for(j=0;j<3;j=j+1) begin
                if(ac[j]!=24 || wc[j]!=108 || maxgap[j]!=3) fail("final counts/fairness");
                $display("MASTER %0d AW=%0d W=%0d B=%0d max_grant_gap=%0d",j,ac[j],wc[j],bc[j],maxgap[j]);
            end
            $display("PASS THROUGHPUT mode=%0d cycles=%0d AW=72 W=324 B=72 W_stall_cycles=%0d B_stall_cycles=%0d",mode,cycle,wstalls,bstalls);
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
        for(i=0;i<3;i=i+1) drive_master(i);
    end
end
endmodule
