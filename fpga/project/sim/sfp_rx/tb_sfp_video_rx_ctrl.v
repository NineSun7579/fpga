`timescale 1ns/1ps
module tb_sfp_video_rx_ctrl;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,en=0;
    reg [31:0] rxd=32'hbc0028bc;
    reg [3:0] rxk=4'b1001;
    wire vs,hs,de,overflow;
    wire [15:0] pix;
    sfp_video_rx #(.FIFO_AW(5)) dut (.i_clk(clk),.i_rst_n(rst_n),.i_en(en),
        .i_rxd(rxd),.i_rxk(rxk),.o_vs(vs),.o_hs(hs),.o_de(de),.o_pix(pix),.o_overflow(overflow));
    reg [18:0] queue[0:4095];
    integer wr=0,rd=0,errors=0,pixels=0,controls=0,sof=0,disabled=0;
    reg shadow_vs=0,shadow_hs=0,evs=0,ehs=0,ede=0;
    reg [15:0] epix=0;
    reg [18:0] head;
    reg old_vs;
    // Reference protocol queue: data cannot change control shadow state.
    always @(posedge clk) begin
        old_vs=evs;
        ede=0;
        if(!rst_n || !en) begin
            wr=0; rd=0; shadow_vs=0; shadow_hs=0; evs=0; ehs=0;
            if(!rst_n) epix=0;
            if(rst_n) disabled=disabled+1;
        end else begin
            if(rd<wr) begin
                head=queue[rd]; rd=rd+1;
                if(head[18]) begin evs=head[17]; ehs=head[16]; controls=controls+1; end
                else begin ede=1; epix=head[15:0]; pixels=pixels+1; end
            end
            if(rxk==0) begin
                queue[wr]={3'b000,rxd[15:0]};
                queue[wr+1]={3'b000,rxd[31:16]}; wr=wr+2;
            end else if(rxk==9 && (rxd[21]!=shadow_vs || rxd[22]!=shadow_hs)) begin
                queue[wr]={1'b1,rxd[21],rxd[22],16'b0}; wr=wr+1;
                shadow_vs=rxd[21]; shadow_hs=rxd[22];
            end
            if(evs && !old_vs) sof=sof+1;
        end
        #2;
        if({vs,hs,de,pix} !== {evs,ehs,ede,epix} || overflow !== 0) begin
            errors=errors+1;
            if(errors<15) $display("FAIL %0t got=%b/%b/%b/%h exp=%b/%b/%b/%h overflow=%b",
                $time,vs,hs,de,pix,evs,ehs,ede,epix,overflow);
        end
    end
    task word(input [3:0] k,input [31:0] d);
        begin @(negedge clk); rxk=k; rxd=d; end
    endtask
    task ctrl(input v,input h);
        begin word(9,{8'hbc,1'b0,h,v,5'b0,8'h28,8'hbc}); end
    endtask
    integer n;
    initial begin
        #20; rst_n=1; en=1;
        ctrl(0,0);
        word(0,32'h00201234); // upper pixel bit 5 used to suppress VS=1
        repeat(8) ctrl(1,0);
        word(0,32'h00405678); // upper pixel bit 6 used to suppress HS=1
        repeat(8) ctrl(1,1);
        // Consecutive data and control changes exercise bank parity/backlog.
        for(n=0;n<4;n=n+1) begin
            word(0,32'h00600020+n); word(0,32'h00000040+n);
            ctrl(n%2,(n+1)%2); ctrl(n%2,(n+1)%2);
            word(4'hf,32'hffffffff); // unsupported K mask is ignored
        end
        repeat(20) ctrl(1,1);
        // Disable while syncs are high and pending pixels remain.
        word(0,32'h1234abcd);
        @(negedge clk); en=0;
        repeat(4) @(negedge clk);
        en=1; rxk=9; rxd=32'hbc6028bc;
        repeat(10) ctrl(1,1);
        word(0,32'h00200040);
        repeat(10) ctrl(1,1);
        ctrl(0,0); repeat(10) ctrl(0,0);
        @(negedge clk);
        if(wr!=rd || pixels<20 || controls<7 || sof<3 || disabled<4) begin
            errors=errors+1; $display("FAIL final coverage");
        end
        $display("decoder pixels=%0d controls=%0d SOF=%0d disable_cycles=%0d errors=%0d",pixels,controls,sof,disabled,errors);
        if(errors) $fatal(1,"TB_FAIL decoder");
        $display("TB_PASS decoder"); $finish;
    end
    initial begin #100000; $fatal(1,"TB_FAIL timeout"); end
endmodule
