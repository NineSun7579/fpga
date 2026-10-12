`timescale 1ns/1ps
module tb_tx_recovery;
    // Actual merged-row shape: two contiguous 64-pixel cameras, then blank.
    // Reduced geometry, real FIFO depth and 62.5/125 MHz clock ratio.
    localparam W=128, H=6, N=W*H, VS=4, PRE=8, BLANK=16;
    localparam FRAME=VS+PRE+H*(W+BLANK), NF=8;
    reg fab_clk=0, vid_clk=0, rx_clk=0;
    always #4 fab_clk=~fab_clk;
    always @(negedge fab_clk) vid_clk<=~vid_clk;
    initial begin #2; forever #4 rx_clk=~rx_clk; end
    reg rst_n=0, ready=0;
    reg [18:0] video=0;
    wire [31:0] txd;
    wire [3:0] txk;
    sfp_video_tx tx(.vid_clk(vid_clk),.vid_rst_n(rst_n),.vid_data(video),
        .fab_clk(fab_clk),.fab_rst_n(rst_n),.link_ready(ready),.txd(txd),.txk(txk));
    // Ideal parallel transport: readiness faults affect TX only. Keeping RX
    // enabled exposes unwanted partial payload instead of masking it in reset.
    reg [31:0] rxd=32'hBC0028BC;
    reg [3:0] rxk=9;
    always @(negedge rx_clk) begin rxd=txd; rxk=txk; end
    wire vs,hs,de,overflow;
    wire [15:0] pix;
    sfp_video_rx rx(.i_clk(rx_clk),.i_rst_n(rst_n),.i_en(rst_n),
        .i_rxd(rxd),.i_rxk(rxk),.o_vs(vs),.o_hs(hs),.o_de(de),.o_pix(pix),.o_overflow(overflow));

    integer errors=0, case_errors=0, cases=0, current_case=0;
    integer counts[0:NF-1];
    integer last_index[0:NF-1];
    integer recovered=-1, recover_count=0, down_pops=0, max_tx_used=0;
    integer forbidden_words=0, postfault_words=0, startup_words=0, max_rx_used=0;
    bit blocked=1, ever_down=0, previous_go=0;
    task automatic fail(input string msg);
        errors++; case_errors++;
        if(case_errors<=5) $display("FAIL case=%0d t=%0t %s",current_case,$time,msg);
    endtask

    // Contract monitor observes consumed input and emitted output, not the
    // candidate's recovery register. A sampled low readiness invalidates the
    // current frame. A ready-high, consumed de=0 VS pulse permits the next one.
    bit must_block, have_pop;
    reg [1:0] consumed_ctrl;
    integer fid;
    always @(posedge fab_clk) begin
        if(!rst_n) begin blocked=1; previous_go=0; end
        else begin
            if(!tx.tx_go) begin
                blocked=1;
                if(previous_go) ever_down=1;
                if(tx.fifo_pop) down_pops++;
            end
            must_block=blocked;
            have_pop=tx.fifo_pop;
            consumed_ctrl={tx.head_hs,tx.head_vs};
            if(tx.tx_go && tx.fifo_pop && !tx.head_de && tx.head_vs) begin
                if(blocked && ever_down) begin
                    recovered=tx.fifo_rdata[15:12]; recover_count++;
                end
                blocked=0;
            end
            previous_go=tx.tx_go;
            #2;
            if(must_block && txk==0) begin
                forbidden_words++;
                if(ever_down) postfault_words++;
                fail("payload before ready-high consumed VS boundary");
            end
            if(must_block && have_pop && (txk!==9 || txd[22:21]!==consumed_ctrl))
                fail("discarded input controls not propagated");
        end
    end
    integer used_tx;
    always @(posedge vid_clk) if(rst_n) begin
        if(tx.u_fifo.full) fail("TX FIFO full / dropped write");
        used_tx=(tx.u_fifo.wbin-tx.u_fifo.rbin)&1023;
        if(used_tx>max_tx_used) max_tx_used=used_tx;
    end
    integer pf,pi;
    always @(posedge rx_clk) if(rst_n) begin
        if(overflow) fail("100H decoder FIFO overflow");
        if(rx.used>max_rx_used) max_rx_used=rx.used;
        if(de) begin
            pf=pix[15:12]; pi=pix[11:0];
            if(pf<0 || pf>=NF || pi>=N) fail("unexpected RX pixel identity");
            else begin
                if(pf==0) begin startup_words++; fail("startup partial frame leaked"); end
                if(last_index[pf]<0 && pi!=0) fail($sformatf("frame %0d starts at pixel %0d",pf,pi));
                if(last_index[pf]>=0 && pi!=last_index[pf]+1)
                    fail($sformatf("frame %0d pixel order: prev=%0d got=%0d",pf,last_index[pf],pi));
                last_index[pf]=pi;
                counts[pf]++;
            end
        end
    end

    task automatic symbol(input bit v,h,d,input integer f,p);
        @(negedge vid_clk); video={v,h,d,4'(f),12'(p)};
    endtask
    // Fault times are source-symbol positions, including VS/blanking. Changes
    // reach tx_go through its real two-stage synchronizer and FIFO CDC latency.
    task automatic run_case(input integer point,length,start_delay,reset_phase,input bit bounce=0);
        integer f,s,y,x,k,absolute,drop_at,rise_at;
        begin
            rst_n=0; ready=0; video=0;
            #80;
            for(k=0;k<NF;k++) begin counts[k]=0; last_index[k]=-1; end
            case_errors=0; down_pops=0; recovered=-1; recover_count=0;
            ever_down=0; max_tx_used=0; max_rx_used=0;
            #(reset_phase); rst_n=1;
            // Start with active data and no VS: reset release must wait for
            // frame1. ready can rise immediately or halfway through startup.
            for(s=0;s<64;s++) begin
                if(s==start_delay) ready=1;
                symbol(0,0,1,0,s);
            end
            repeat(24) symbol(0,0,0,0,0);
            drop_at=FRAME+point; rise_at=drop_at+length;
            for(f=1;f<NF;f++) begin
                for(s=0;s<FRAME;s++) begin
                    absolute=(f-1)*FRAME+s;
                    if(length>0 && absolute==drop_at) ready=0;
                    if(length>0 && absolute==rise_at) ready=1;
                    // Readiness falls again after accepting frame3's VS but
                    // before its first pixel, then rises in that active row.
                    if(bounce && absolute==2*FRAME+5) ready=0;
                    if(bounce && absolute==2*FRAME+45) ready=1;
                    if(s<VS) symbol(1,0,0,f,0);
                    else if(s<VS+PRE) symbol(0,0,0,f,0);
                    else begin
                        y=(s-VS-PRE)/(W+BLANK);
                        x=(s-VS-PRE)%(W+BLANK);
                        symbol(0,x>=W,x<W,f,y*W+(x<W?x:0));
                    end
                end
            end
            repeat(128) symbol(0,0,0,NF-1,0);
            // Both untouched baseline and several steady frames must preserve
            // every pixel, including first/last and the contiguous camera join.
            if(counts[1]!=N || last_index[1]!=N-1) fail("continuous first frame incomplete");
            for(k=5;k<NF;k++)
                if(counts[k]!=N || last_index[k]!=N-1) fail($sformatf("steady frame %0d incomplete (%0d)",k,counts[k]));
            if(length>0) begin
                if(down_pops==0 || recover_count==0 || recovered<2) fail("fault/recovery coverage missing");
                if(bounce && (recover_count!=2 || recovered!=4)) fail("readiness did not remain high across boundary / bounce coverage");
                if(recovered>=NF || counts[recovered]!=N || last_index[recovered]!=N-1)
                    fail($sformatf("first recovered frame %0d incomplete",recovered));
            end else begin
                for(k=2;k<NF;k++) if(counts[k]!=N) fail("continuous frame incomplete");
            end
            $display("CASE %0d point=%0d low_symbols=%0d startup=%0d phase=%0d recovered=%0d pixels=%0d down_pops=%0d max_tx=%0d max_rx=%0d errors=%0d",
                current_case,point,length,start_delay,reset_phase,recovered,(recovered>=0&&recovered<NF)?counts[recovered]:0,down_pops,max_tx_used,max_rx_used,case_errors);
            cases++; current_case++;
        end
    endtask
    integer points[0:7], lengths[0:4];
    integer a,b;
    initial begin
        points[0]=VS+PRE+33; // odd midrow, pending pair interrupted
        points[1]=VS+PRE+34; // even midrow
        points[2]=VS+PRE+W+8; // middle of horizontal blank
        points[3]=-1; // immediately before frame VS
        points[4]=0; // VS rising
        points[5]=2; // within VS pulse
        points[6]=3; // immediately before VS falling
        points[7]=4; // VS falling
        lengths[0]=1; lengths[1]=3; lengths[2]=17;
        lengths[3]=600; // exceeds FIFO depth if incorrectly stopped
        lengths[4]=2200; // spans multiple frame boundaries
        run_case(0,0,0,21);
        run_case(0,0,31,29);
        for(a=0;a<8;a++) for(b=0;b<5;b++)
            run_case(points[a],lengths[b],(a%2)?31:0,21+(b%3)*3);
        run_case(points[0],17,0,21,1);
        $display("RESULT cases=%0d forbidden_words=%0d startup_pixels=%0d errors=%0d",cases,forbidden_words,startup_words,errors);
        $display("RECOVERY postfault_payload_words=%0d",postfault_words);
        if(errors) $fatal(1,"TB_FAIL recovery");
        $display("TB_PASS recovery"); $finish;
    end
    initial begin #10000000; $fatal(1,"TB_FAIL recovery timeout"); end
endmodule
