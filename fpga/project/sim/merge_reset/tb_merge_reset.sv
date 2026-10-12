`timescale 1ns/1ps
module tb_merge_reset;
    localparam LP=16, NL=4, HT=80, VT=8;
    reg cfg_clk=0, a_clk=0, b_clk=0, o_clk=0;
    reg cfg_run=1, a_run=1, b_run=1, o_run=1;
    always #50 if(cfg_run) cfg_clk=~cfg_clk;
    always #12 if(a_run) a_clk=~a_clk;
    always #11.9 if(b_run) b_clk=~b_clk;
    always #8 if(o_run) o_clk=~o_clk;
    reg locked=0;
    reg [1:0] done=0;
    wire rstn, req, ar, br, orun;
    merge_reset_top_candidate #(.DELAY(10)) resets
        (cfg_clk,locked,done,a_clk,b_clk,o_clk,rstn,req,ar,br,orun);

    // Actual legacy reset topology, for a negative control on the same traffic.
    reg [1:0] fab_sync=0;
    always @(posedge o_clk) fab_sync <= {fab_sync[0],rstn};
    wire legacy_or=fab_sync[1];
    reg [15:0] ad=0,bd=0;
    reg ade=0,bde=0,avs=1,bvs=1;
    reg source_reset=1;
    reg [2:0] epoch=1;
    integer ah=0,av=0,bh=0,bv=0;
    always @(negedge a_clk) begin
        if(source_reset) begin ah=0; av=0; ade=0; avs=1; end
        else begin
            avs=(av<1); ade=(av>=1 && av<=NL && ah<LP);
            ad={1'b0,epoch,4'(av-1),8'(ah)};
            if(ah==HT-1) begin ah=0; av=(av==VT-1)?0:av+1; end
            else ah=ah+1;
        end
    end
    always @(negedge b_clk) begin
        if(source_reset) begin bh=0; bv=1; bde=0; bvs=1; end
        else begin
            bvs=(bv<1); bde=(bv>=1 && bv<=NL && bh<LP);
            bd={1'b1,epoch,4'(bv-1),8'(bh)};
            if(bh==HT-1) begin bh=0; bv=(bv==VT-1)?0:bv+1; end
            else bh=bh+1;
        end
    end
    wire [15:0] cd,ld;
    wire de,vs,lde,lvs;
    cam2_merge #(.LINE_PIX(LP),.LINES(NL)) dut (
        .a_clk(a_clk),.a_rst_n(ar),.a_data(ad),.a_de(ade),.a_vs(avs),
        .b_clk(b_clk),.b_rst_n(br),.b_data(bd),.b_de(bde),.b_vs(bvs),
        .o_clk(o_clk),.o_rst_n(orun),.corr_mode(4'd0),.c_data(cd),.c_de(de),.c_vs(vs));
    cam2_merge #(.LINE_PIX(LP),.LINES(NL)) legacy (
        .a_clk(a_clk),.a_rst_n(done[0]),.a_data(ad),.a_de(ade),.a_vs(avs),
        .b_clk(b_clk),.b_rst_n(done[1]),.b_data(bd),.b_de(bde),.b_vs(bvs),
        .o_clk(o_clk),.o_rst_n(legacy_or),.corr_mode(4'd0),.c_data(ld),.c_de(lde),.c_vs(lvs));

    integer pixels=0, rows=0, frames=0, epoch_rows=0;
    reg vprev=0;
    reg [3:0] rowtag;
    reg [15:0] raw;
    always @(posedge o_clk) begin
        #2; // actual RTL has #1 delayed nonblocking assignments
        if(!orun) begin pixels=0; rows=0; vprev=0; end
        else begin
            if(de) begin
                raw={cd[4:0],cd[10:5],cd[15:11]};
                if(pixels<LP) begin
                    if(pixels==0) rowtag=raw[11:8];
                    if(raw[15]!==0 || raw[14:12]!==epoch || raw[7:0]!==8'(pixels) || raw[11:8]!==rowtag)
                        $fatal(1,"A stale/corrupt pixel epoch=%d pixel=%d raw=%h",epoch,pixels,raw);
                end else if(raw!=0) begin
                    // B is allowed to repeat its last line or fill black.
                    if(raw[15]!==1 || raw[14:12]!==epoch || raw[7:0]!==8'(pixels-LP))
                        $fatal(1,"B stale/corrupt pixel epoch=%d pixel=%d raw=%h",epoch,pixels,raw);
                end
                pixels=pixels+1;
            end else if(pixels!=0) begin
                if(pixels!=2*LP) $fatal(1,"short row %d",pixels);
                pixels=0; rows=rows+1; epoch_rows=epoch_rows+1;
            end
            if(vs && !vprev) begin
                if(rows!=NL) $fatal(1,"frame rows %d",rows);
                rows=0; frames=frames+1;
            end
            vprev=vs;
        end
    end

    task check_clear;
        begin
            #3;
            if({ar,br,orun}!==3'b000) $fatal(1,"not all resets asserted");
            if(dut.u_afifo.wbin!==0 || dut.u_afifo.rbin!==0 ||
               dut.u_bfifo.wbin!==0 || dut.u_bfifo.rbin!==0 ||
               dut.u_afifo.wptr_rd2!==0 || dut.u_afifo.rptr_wr2!==0 ||
               dut.u_bfifo.wptr_rd2!==0 || dut.u_bfifo.rptr_wr2!==0 ||
               dut.u_afifo.empty!==1 || dut.u_bfifo.empty!==1 ||
               dut.u_afifo.full!==0 || dut.u_bfifo.full!==0 ||
               dut.a_ready[0]!==0 || dut.a_ready[1]!==0 ||
               dut.b_ready[0]!==0 || dut.b_ready[1]!==0 ||
               dut.snap_valid!==0 || dut.pair_cnt!==0 ||
               dut.a_line_cnt!==0 || dut.b_line_cnt!==0 || de!==0 || vs!==0)
                $fatal(1,"FIFO/logical state not cleared without clocks");
        end
    endtask
    task recover(input [2:0] new_epoch);
        integer before_frames;
        begin
            epoch=new_epoch; source_reset=1; a_run=1; b_run=1; o_run=1; cfg_run=1;
            done=3; locked=1;
            wait(ar && br && orun); #100;
            epoch_rows=0; before_frames=frames; source_reset=0;
            wait(frames>=before_frames+2);
            $display("RECOVERY PASS epoch=%0d rows=%0d frames=%0d",epoch,epoch_rows,frames-before_frames);
        end
    endtask
    initial begin
        #300;
        if(rstn!==0 || req!==0) $fatal(1,"undefined delayed startup");
        locked=1; done=1; #2000;
        if(ar || br || orun) $fatal(1,"released before both config flags");
        recover(1);
        // Unlock in a live row; all clocks stop, config-done remains high.
        wait(de && dut.a_rcnt>4);
        #1; a_run=0; b_run=0; o_run=0; cfg_run=0; locked=0;
        check_clear;
        if(legacy.u_afifo.wbin===0 && legacy.u_bfifo.wbin===0)
            $fatal(1,"negative control did not retain writers");
        $display("LEGACY FAILURE REPRODUCED: stopped-clock PLL unlock retains writer pointers A=%0d B=%0d",legacy.u_afifo.wbin,legacy.u_bfifo.wbin);
        #100; locked=1; #200;
        if(rstn!==0 || ar || br || orun) $fatal(1,"release without cfg clock");
        recover(2);
        // One camera reruns config while the other camera remains configured.
        wait(de && dut.a_rcnt>4); #1;
        a_run=0; b_run=0; o_run=0; done[0]=0;
        check_clear;
        #100; done[0]=1; #100;
        if(ar || br || orun) $fatal(1,"release without destination clock");
        recover(3);
        wait(de && dut.a_rcnt>4); #1;
        a_run=0; b_run=0; o_run=0; done[1]=0;
        check_clear;
        recover(4);
        $display("TEST PASS merge reset: startup, stopped-clock PLL reset, A/B config rerun, 8 complete frames");
        $finish;
    end
    initial begin #1000000; $fatal(1,"timeout"); end
endmodule
