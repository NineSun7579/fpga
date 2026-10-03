`timescale 1ns/1ps
module tb_power_startup;
    reg sys_clk=0;
    always #10 sys_clk=~sys_clk;
    reg rstn=0;
    wire c1,c2,pwnd,en,lc1,lc2,lpwnd,len;
    power_on_delay candidate(sys_clk,rstn,c1,c2,pwnd,en);
    power_on_delay legacy(sys_clk,1'b1,lc1,lc2,lpwnd,len);
    integer cycles=0;
    always @(posedge sys_clk) cycles=cycles+1;
    task check_reset;
        begin
            // power_on_delay resets synchronously through three dependent stages.
            repeat(3) @(posedge sys_clk); #1;
            if({c1,c2,pwnd,en}!==4'b0010 || candidate.cnt1!==0 ||
               candidate.cnt2!==0 || candidate.cnt3!==0)
                $fatal(1,"power reset undefined");
        end
    endtask
    task startup;
        integer start_cycle;
        begin
            @(negedge sys_clk); rstn=1; start_cycle=cycles;
            @(negedge pwnd);
            if(cycles-start_cycle!=262145) $fatal(1,"pwdn delay %d",cycles-start_cycle);
            @(posedge c1);
            if(cycles-start_cycle!=327681) $fatal(1,"camera delay %d",cycles-start_cycle);
            @(posedge en);
            if(cycles-start_cycle!=1376257) $fatal(1,"config-enable delay %d",cycles-start_cycle);
            if(c2!==1) $fatal(1,"camera resets differ");
            $display("POWER STARTUP PASS cycles=%0d",cycles-start_cycle);
        end
    endtask
    initial begin
        check_reset;
        #1000;
        if(legacy.cnt1!==19'bx || legacy.cnt2!==16'bx || legacy.cnt3!==20'bx)
            $fatal(1,"legacy counters unexpectedly initialized");
        $display("LEGACY STARTUP FAILURE REPRODUCED: reset tied high leaves counters X");
        startup;
        @(negedge sys_clk); rstn=0;
        check_reset;
        startup;
        $display("TEST PASS power startup and reset rerun, actual unreduced delay counters");
        $finish;
    end
    initial begin #60000000; $fatal(1,"timeout"); end
endmodule
