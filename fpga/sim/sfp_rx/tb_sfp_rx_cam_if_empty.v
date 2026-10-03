`timescale 1ns/1ps
module tb_sfp_rx_cam_if_empty;
    localparam W=8, SW=4, H=3, NF=4, D=16;
    reg rx_clk=0, axi_clk=0, run_writer=0;
    always #4 if (run_writer) rx_clk=~rx_clk;
    always #3.809524 axi_clk=~axi_clk; // 131.25 MHz
    reg rst_n=0, vs=0, hs=0, de=0;
    reg [15:0] pix=0;
    wire vs5,hs5,de5,vs6,hs6,de6;
    wire [15:0] pix5,pix6;
    sfp_rx_cam_if #(.IMG_W(W),.SPLIT_W(SW),.FIFO_D(D)) dut (
        .i_rx_clk(rx_clk),.i_rx_rst_n(rst_n),.i_vs(vs),.i_hs(hs),
        .i_de(de),.i_pix(pix),.i_axi_clk(axi_clk),.i_axi_rst_n(rst_n),
        .o_vs5(vs5),.o_hs5(hs5),.o_de5(de5),.o_pix5(pix5),
        .o_vs6(vs6),.o_hs6(hs6),.o_de6(de6),.o_pix6(pix6));
    reg [18:0] expected5[0:4095],expected6[0:4095];
    integer wr=0,rd5=0,rd6=0,errors=0,empty_cycles=0;
    integer col=0,frame5=-1,frame6=-1,count5=0,count6=0,sof5=0,sof6=0;
    reg in_vs_q=0,last_vs5=0,last_hs5=0,last_vs6=0,last_hs6=0;
    reg seen_vs5=0,seen_vs6=0;
    function [15:0] pattern(input integer f,input integer y,input integer x);
        pattern=16'h1000+f*256+y*16+x;
    endfunction
    task fail(input [255:0] msg);
        begin errors=errors+1; if(errors<15) $display("FAIL %0t %0s",$time,msg); end
    endtask
    // Independent input model, including every blank symbol written by DUT.
    always @(posedge rx_clk) if(rst_n) begin
        if(dut.fif5_full || dut.fif6_full) fail("unexpected full");
        expected5[wr]={vs,hs,de && col<SW,pix};
        expected6[wr]={vs,hs,de && col>=SW,pix};
        wr=wr+1;
        if(vs && !in_vs_q) col=0;
        else if(de) col=(col==W-1)?0:col+1;
        in_vs_q=vs;
    end
    // Sample the same pre-edge head as a synchronous downstream consumer.
    always @(posedge axi_clk) if(rst_n) begin
        if(!dut.fif5_empty) begin
            if(rd5>=wr) fail("channel5 extra symbol");
            if({vs5,hs5,de5,pix5} !== expected5[rd5]) fail("channel5 head mismatch");
            rd5=rd5+1; last_vs5=vs5; last_hs5=hs5;
        end else begin
            empty_cycles=empty_cycles+1;
            if(de5 !== 0 || vs5 !== last_vs5 || hs5 !== last_hs5) fail("channel5 empty stale head");
        end
        if(!dut.fif6_empty) begin
            if(rd6>=wr) fail("channel6 extra symbol");
            if({vs6,hs6,de6,pix6} !== expected6[rd6]) fail("channel6 head mismatch");
            rd6=rd6+1; last_vs6=vs6; last_hs6=hs6;
        end else if(de6 !== 0 || vs6 !== last_vs6 || hs6 !== last_hs6)
            fail("channel6 empty stale head");
        if(vs5 && !seen_vs5) begin
            if(frame5>=0 && count5!=SW*H) fail("channel5 frame length");
            frame5=frame5+1; count5=0; sof5=sof5+1;
        end
        if(vs6 && !seen_vs6) begin
            if(frame6>=0 && count6!=SW*H) fail("channel6 frame length");
            frame6=frame6+1; count6=0; sof6=sof6+1;
        end
        seen_vs5=vs5; seen_vs6=vs6;
        if(de5) begin
            if(frame5<0 || count5>=SW*H || pix5 !== pattern(frame5,count5/SW,count5%SW)) fail("channel5 pixel/frame");
            count5=count5+1;
        end
        if(de6) begin
            if(frame6<0 || count6>=SW*H || pix6 !== pattern(frame6,count6/SW,SW+count6%SW)) fail("channel6 pixel/frame");
            count6=count6+1;
        end
    end
    task symbol(input v,input h,input d,input [15:0] p);
        begin @(negedge rx_clk); vs=v; hs=h; de=d; pix=p; end
    endtask
    task drain_and_poison;
        begin
            @(negedge rx_clk); run_writer=0;
            repeat(12) @(negedge axi_clk);
            if(!dut.fif5_empty || !dut.fif6_empty || rd5!=wr || rd6!=wr) fail("drain incomplete");
            // Empty head: deliberately opposite syncs and asserted DE.
            dut.u_fifo5.mem[dut.u_fifo5.raddr]={~last_vs5,~last_hs5,1'b1,16'hdead};
            dut.u_fifo6.mem[dut.u_fifo6.raddr]={~last_vs6,~last_hs6,1'b1,16'hbeef};
            repeat(8) @(negedge axi_clk);
            run_writer=1;
        end
    endtask
    integer f,y,x;
    initial begin
        #20; rst_n=1;
        // Poison empty memory before any valid write: no phantom SOF/pixel.
        dut.u_fifo5.mem[0]={3'b111,16'hdead};
        dut.u_fifo6.mem[0]={3'b111,16'hbeef};
        repeat(8) @(negedge axi_clk);
        run_writer=1;
        for(f=0;f<NF;f=f+1) begin
            symbol(1,0,0,0); symbol(1,0,0,0);
            // Preserve high VS through an empty interval, then use new head.
            drain_and_poison();
            symbol(0,0,0,0);
            for(y=0;y<H;y=y+1) begin
                for(x=0;x<W;x=x+1) begin
                    symbol(0,1,1,pattern(f,y,x));
                    if(x==2 || x==5) symbol(0,1,0,0); // intra-line DE gaps
                end
                symbol(0,0,0,0);
            end
            drain_and_poison();
        end
        symbol(0,0,0,0);
        @(negedge rx_clk); run_writer=0;
        repeat(30) @(negedge axi_clk);
        if(sof5!=NF || sof6!=NF || count5!=SW*H || count6!=SW*H ||
           rd5!=wr || rd6!=wr || empty_cycles<30) fail("final counts/coverage");
        $display("splitter symbols=%0d/%0d/%0d SOF=%0d/%0d pixels_per_frame=%0d/%0d empty_cycles=%0d errors=%0d",
                 wr,rd5,rd6,sof5,sof6,count5,count6,empty_cycles,errors);
        if(errors) $fatal(1,"TB_FAIL splitter");
        $display("TB_PASS splitter"); $finish;
    end
    initial begin #100000; $fatal(1,"TB_FAIL timeout"); end
endmodule
