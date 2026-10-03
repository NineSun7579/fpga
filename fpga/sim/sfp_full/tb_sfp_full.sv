`timescale 1ns/1ps
module tb_sfp_full;
    localparam W=640, H=480, N=W*H, NF=2;
    reg fab_clk=0, vid_clk=0, rx_clk=0, axi_clk=0;
    always #4 fab_clk=~fab_clk;
    // Match TX top: merge clock toggles on fabric falling edges.
    always @(negedge fab_clk) vid_clk<=~vid_clk;
    initial begin #2; forever #4 rx_clk=~rx_clk; end
    always #3.809524 axi_clk=~axi_clk;
    reg rst_n=0;
    reg [18:0] video=0;
    wire [31:0] txd;
    wire [3:0] txk;
    sfp_video_tx tx(.vid_clk(vid_clk),.vid_rst_n(rst_n),.vid_data(video),
        .fab_clk(fab_clk),.fab_rst_n(rst_n),.link_ready(rst_n),.txd(txd),.txk(txk));

    // Ideal parallel word transport, not an HSST/PCS implementation.
    // GE mode substitutes redundant controls only; changed state and data
    // are never removed. This tests decoder ignore semantics, not GE LSM.
    reg [31:0] rxd=32'hBC0028BC;
    reg [3:0] rxk=9;
    reg [1:0] wire_state=0;
    integer beat=0, data_words=0, ctrl_words=0, skip_words=0, idle_words=0;
    reg ge_mode=0;
    integer skip_pops=0,skip_active_pops=0;
`ifdef CTC_SOURCE
    always @(posedge fab_clk) if(rst_n && tx.ctc_phase==6 && tx.u_fifo.rd_en && !tx.fifo_empty) begin
        skip_pops=skip_pops+1;
        if(tx.head_de) skip_active_pops=skip_active_pops+1;
    end
`endif
    always @(negedge rx_clk) begin
        rxd=txd; rxk=txk;
        if(rst_n) begin
            beat=beat+1;
            if(ge_mode && txk==9 && txd[22:21]===wire_state) begin
                if(beat%8==6) begin rxd=32'h28BC28BC; rxk=5; end
                else if(beat%8==0) begin rxd=32'hC5BCC5BC; rxk=5; end
            end
            if(txk==9) wire_state=txd[22:21];
            if(rxk==0) data_words=data_words+1;
            else if(rxk==9) ctrl_words=ctrl_words+1;
            else if(rxk==5 && rxd==32'h28BC28BC) skip_words=skip_words+1;
            else if(rxk==5 && rxd==32'hC5BCC5BC) idle_words=idle_words+1;
        end
    end
    wire vs,hs,de,overflow;
    wire [15:0] pix;
    sfp_video_rx rx(.i_clk(rx_clk),.i_rst_n(rst_n),.i_en(rst_n),
        .i_rxd(rxd),.i_rxk(rxk),.o_vs(vs),.o_hs(hs),.o_de(de),.o_pix(pix),.o_overflow(overflow));
    wire vs5,hs5,de5,vs6,hs6,de6;
    wire [15:0] pix5,pix6;
    sfp_rx_cam_if split(.i_rx_clk(rx_clk),.i_rx_rst_n(rst_n),.i_vs(vs),
        .i_hs(hs),.i_de(de),.i_pix(pix),.i_axi_clk(axi_clk),.i_axi_rst_n(rst_n),
        .o_vs5(vs5),.o_hs5(hs5),.o_de5(de5),.o_pix5(pix5),
        .o_vs6(vs6),.o_hs6(hs6),.o_de6(de6),.o_pix6(pix6));
    function automatic [15:0] pattern(input integer f,y,x,cam);
        // Camera/frame identity plus column/row variation, modulo 16 bits.
        pattern=(cam==5 ? 16'h1357 : 16'h8ace) ^ (f*16'h3141) ^ (y*641+x);
    endfunction
    integer errors=0,sof_rx=0,sof5=0,sof6=0;
    integer fr=-1,f5=-1,f6=-1,nr=0,n5=0,n6=0,total_rx=0,total5=0,total6=0;
    integer max_used=0,empty5=0,empty6=0,source_pixels=0,source_sof=0;
    reg prev_rx=0,prev5=0,prev6=0,prev_src=0;
    task automatic fail(input string msg);
        begin errors=errors+1; if(errors<=12) $display("FAIL %0t %s",$time,msg); end
    endtask
    always @(posedge vid_clk) if(rst_n) begin
        if(tx.u_fifo.full) fail("TX FIFO full");
        if(video[16]) source_pixels=source_pixels+1;
        if(video[18] && !prev_src) source_sof=source_sof+1;
        prev_src=video[18];
    end
    always @(posedge rx_clk) if(rst_n) begin
        if(overflow) fail("decoder overflow");
        if(rx.used>max_used) max_used=rx.used;
        if(split.fif5_full || split.fif6_full) fail("split FIFO full");
        if(vs && !prev_rx) begin
            if(fr>=0 && nr!=2*N) fail($sformatf("RX frame %0d length %0d",fr,nr));
            fr=fr+1; nr=0; sof_rx=sof_rx+1;
        end
        prev_rx=vs;
        if(de) begin
            if(fr<0 || nr>=2*N || pix!==pattern(fr,nr/(2*W),nr%W,(nr%(2*W)<W)?5:6))
                fail($sformatf("RX pixel f=%0d n=%0d got=%h",fr,nr,pix));
            nr=nr+1; total_rx=total_rx+1;
        end
    end
    // Pre-edge sampling matches the downstream synchronous consumer.
    always @(posedge axi_clk) if(rst_n) begin
        if(split.fif5_empty) empty5=empty5+1;
        if(split.fif6_empty) empty6=empty6+1;
        if(vs5 && !prev5) begin
            if(f5>=0 && n5!=N) fail($sformatf("cam5 frame %0d length %0d",f5,n5));
            f5=f5+1; n5=0; sof5=sof5+1;
        end
        if(vs6 && !prev6) begin
            if(f6>=0 && n6!=N) fail($sformatf("cam6 frame %0d length %0d",f6,n6));
            f6=f6+1; n6=0; sof6=sof6+1;
        end
        prev5=vs5; prev6=vs6;
        if(de5) begin
            if(f5<0 || n5>=N || pix5!==pattern(f5,n5/W,n5%W,5))
                fail($sformatf("cam5 pixel f=%0d n=%0d got=%h",f5,n5,pix5));
            n5=n5+1; total5=total5+1;
        end
        if(de6) begin
            if(f6<0 || n6>=N || pix6!==pattern(f6,n6/W,n6%W,6))
                fail($sformatf("cam6 pixel f=%0d n=%0d got=%h",f6,n6,pix6));
            n6=n6+1; total6=total6+1;
        end
    end
    task automatic symbol(input bit v,h,d,input [15:0] p);
        begin @(negedge vid_clk); video={v,h,d,p}; end
    endtask
    integer f,y,x,reset_ns=101;
    initial begin
        ge_mode=$test$plusargs("GE");
`ifdef CTC_SOURCE
        // ModelSim collapses this input onto fifo_pop; use its primitive
        // sources to avoid a self-referential force through fifo_pop_gated.
        if($test$plusargs("FIX_POP")) force tx.u_fifo.rd_en=(!tx.fifo_empty && tx.ctc_phase!=6);
`endif
        if($value$plusargs("RESET_NS=%d",reset_ns)) begin end
        #(reset_ns); rst_n=1;
        repeat(32) symbol(0,0,0,0);
        for(f=0;f<NF;f=f+1) begin
            repeat(4) symbol(1,0,0,0);
            repeat(8) symbol(0,0,0,0);
            for(y=0;y<H;y=y+1) begin
                // Actual merge shape: 640 A + 640 B, continuous DE, HS=0.
                for(x=0;x<2*W;x=x+1)
                    symbol(0,0,1,pattern(f,y,x%W,x<W?5:6));
                // Actual merge copies the 640-pixel B snapshot between lines.
                repeat(648) symbol(0,0,0,0);
            end
        end
        repeat(128) symbol(0,0,0,0);
        if(source_pixels!=NF*2*N || source_sof!=NF) fail("source count");
        if(sof_rx!=NF || sof5!=NF || sof6!=NF || nr!=2*N || n5!=N || n6!=N ||
           total_rx!=NF*2*N || total5!=NF*N || total6!=NF*N) fail("final frame/SOF/pixel counts");
        if(data_words!=NF*N || empty5==0 || empty6==0) fail("word count/empty coverage");
        if(ge_mode && (skip_words==0 || idle_words==0)) fail("GE coverage");
        $display("SOURCE pixels=%0d SOF=%0d",source_pixels,source_sof);
        $display("RX pixels=%0d SOF=%0d last_frame=%0d max_used=%0d",total_rx,sof_rx,nr,max_used);
        $display("CAM5 pixels=%0d SOF=%0d last_frame=%0d empty=%0d",total5,sof5,n5,empty5);
        $display("CAM6 pixels=%0d SOF=%0d last_frame=%0d empty=%0d",total6,sof6,n6,empty6);
        $display("WIRE data=%0d ctrl=%0d skip=%0d idle=%0d errors=%0d",data_words,ctrl_words,skip_words,idle_words,errors);
        $display("PHASE reset_ns=%0d skip_FIFO_pops=%0d skip_active_pops=%0d",reset_ns,skip_pops,skip_active_pops);
        if(errors) $fatal(1,"TB_FAIL full");
        $display("TB_PASS full"); $finish;
    end
    initial begin #40000000; $fatal(1,"TB_FAIL timeout"); end
endmodule
