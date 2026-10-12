`timescale 1ns/1ps
module tb_sys_reset;
    reg cfg_clk=0, sys_clk=0, a_clk=0, b_clk=0, mrg_clk=0;
    reg sys_run=1, cfg_run=1, diag_run=1, clk_25M=0;
    always #20 if(diag_run) clk_25M=~clk_25M;
    always #50 if(cfg_run) cfg_clk=~cfg_clk;
    always #10 if(sys_run) sys_clk=~sys_clk;
    always #12 a_clk=~a_clk;
    always #11.9 b_clk=~b_clk;
    always #8 mrg_clk=~mrg_clk;
    reg locked=0;
    reg [1:0] done=0;
    wire rstn_int, req, ar, br, mr, sys_rst_n;
    merge_reset_top_candidate resets
        (cfg_clk,locked,done,a_clk,b_clk,mrg_clk,rstn_int,req,ar,br,mr);
    production_sys_reset sync_reset(sys_clk,rstn_int,sys_rst_n);
    wire diag_rst_n;
    production_diag_reset diag_reset(clk_25M,rstn_int,diag_rst_n);
    integer cfg_edges=0, diag_edges=0;
    always @(posedge cfg_clk) if(locked) cfg_edges=cfg_edges+1;
    always @(negedge locked) cfg_edges=0;
    always @(posedge clk_25M) begin
        if(!rstn_int) diag_edges=0;
        else begin
            diag_edges=diag_edges+1;
            #1;
            if(diag_rst_n !== (diag_edges>=2)) $fatal(1,"diagnostic release edge %d",diag_edges);
        end
    end
    always @(negedge rstn_int) diag_edges=0;
    always @(posedge rstn_int) begin
        if(cfg_edges!=10001) $fatal(1,"registered startup delay %d",cfg_edges);
        if(cfg_clk!==1 || !locked) $fatal(1,"startup release outside cfg edge");
    end
    wire c1,c2,pwnd,en;
    power_on_delay power(sys_clk,sys_rst_n,c1,c2,pwnd,en);
    integer cycles=0;
    always @(posedge sys_clk) cycles=cycles+1;
    task release_and_start;
        integer base;
        begin
            // Real 10,000-cycle cfg delay, not the short merge-test parameter.
            #7 locked=1;
            repeat(10000) @(posedge cfg_clk);
            #1;
            if(rstn_int!==0 || sys_rst_n!==0) $fatal(1,"startup released early");
            @(posedge rstn_int);
            @(posedge sys_clk); #1;
            if(sys_rst_n!==0) $fatal(1,"released on first sys edge");
            @(posedge sys_clk); #1;
            if(sys_rst_n!==1) $fatal(1,"missing second-edge release");
            base=cycles;
            @(negedge pwnd);
            if(cycles-base!=262145) $fatal(1,"pwdn delay %d",cycles-base);
            @(posedge c1);
            if(cycles-base!=327681 || c2!==1) $fatal(1,"camera delay/skew");
            @(posedge en);
            if(cycles-base!=1376257) $fatal(1,"config enable delay %d",cycles-base);
            done=3;
            wait(ar && br && mr);
            $display("REAL TOP+POWER STARTUP PASS full cfg and power counters");
        end
    endtask
    initial begin
        repeat(4) @(posedge sys_clk); #1;
        if({c1,c2,pwnd,en}!==4'b0010) $fatal(1,"initial power reset X");
        release_and_start;
        // Lock loss between edges with both relevant clocks stopped.
        @(negedge sys_clk); sys_run=0; cfg_run=0; diag_run=0;
        #3 locked=0; #1;
        if(diag_rst_n!==0 || sys_rst_n!==0 || rstn_int!==0 || req!==0 || {ar,br,mr}!==0)
            $fatal(1,"reset assertion depended on clock");
        #6 locked=1; #1;
        if(diag_rst_n!==0 || sys_rst_n!==0 || rstn_int!==0) $fatal(1,"short lock loss lost");
        #13 locked=0; done=0; sys_run=1; cfg_run=1; diag_run=1;
        repeat(4) @(posedge sys_clk); #1;
        if({c1,c2,pwnd,en}!==4'b0010 || power.cnt1!==0 ||
           power.cnt2!==0 || power.cnt3!==0) $fatal(1,"power rerun reset X");
        release_and_start;
        $display("TEST PASS production sys reset, stopped-clock assertion, full deterministic startup/rerun and coordinated merge");
        $finish;
    end
    initial begin #65000000; $fatal(1,"timeout"); end
endmodule
