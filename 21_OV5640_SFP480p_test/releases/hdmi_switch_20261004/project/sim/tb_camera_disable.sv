`timescale 1ns/1ps
module tb_camera_disable;
    reg clk=0, reset_n=0;
    always #10 clk=~clk;
    wire reset1,reset2,pwdn,initial_en;
    power_on_delay dut(clk,reset_n,reset1,reset2,pwdn,initial_en);
    initial begin
        #35;reset_n=1;
        #100;
        if(reset1 || reset2 || initial_en || !pwdn)$fatal(1,"unsafe startup");
        wait(initial_en);
        if(!reset1 || !reset2 || pwdn)$fatal(1,"incorrect camera startup");
        #3;reset_n=0;#1;
        if(reset1 || reset2 || initial_en || !pwdn)$fatal(1,"camera disable is not asynchronous");
        #97;reset_n=1;#100;
        if(reset1 || reset2 || initial_en)$fatal(1,"camera re-enable skipped startup delay");
        wait(initial_en);
        $display("TEST PASS: both camera resets assert without clock edge and repeat full startup delay");
        $finish;
    end
    initial begin #60000000;$fatal(1,"camera test watchdog");end
endmodule
