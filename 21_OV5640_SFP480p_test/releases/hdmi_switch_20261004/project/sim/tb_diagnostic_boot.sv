`timescale 1ns/1ps
module tb_diagnostic_boot;
    reg sys=0;
    always #10 sys=~sys;
    reg key1=1,key2=1;
    wire drst,crst1,crst2,prst;
    // Unspecified top parameters use their production defaults, including
    // the real 500000-clock debounce in both instances.
    hdmi_ddr_ov5640_top #(.DIAGNOSTIC_HDMI_BOOT(1)) diagnostic(
        .sys_clk(sys),.key1(key1),.key2(key2),.rstn_in(drst),
        .cmos1_reset(crst1),.cmos2_reset(crst2),
        .cmos1_pclk(sys),.cmos2_pclk(sys),.cmos1_href(1'b0),.cmos2_href(1'b0),
        .cmos1_vsync(1'b0),.cmos2_vsync(1'b0),.cmos1_data(8'b0),.cmos2_data(8'b0),
        .pixclk_in(sys),.vs_in(1'b0),.hs_in(1'b0),.de_in(1'b0),
        .r_in(8'b0),.g_in(8'b0),.b_in(8'b0),.sfp0_los(1'b1));
    hdmi_ddr_ov5640_top production(
        .sys_clk(sys),.key1(1'b1),.key2(1'b1),.rstn_in(prst),
        .cmos1_pclk(sys),.cmos2_pclk(sys),.cmos1_href(1'b0),.cmos2_href(1'b0),
        .cmos1_vsync(1'b0),.cmos2_vsync(1'b0),.cmos1_data(8'b0),.cmos2_data(8'b0),
        .pixclk_in(sys),.vs_in(1'b0),.hs_in(1'b0),.de_in(1'b0),
        .r_in(8'b0),.g_in(8'b0),.b_in(8'b0),.sfp0_los(1'b1));
    task clocks(input integer n);repeat(n)@(negedge sys);endtask
    integer start_count;
    always @(negedge sys) if(production.sys_rst_n) begin
        if(production.diag_press !== 0 || production.hdmi_request !== 0 || prst !== 0)
            $fatal(1,"default production boot generated an HDMI request/reset release");
    end
    initial begin
        wait(diagnostic.sys_rst_n);clocks(20);
        if(diagnostic.hdmi_request || diagnostic.hdmi_active || drst || diagnostic.diag_press)
            $fatal(1,"diagnostic selected HDMI before the delay");
        start_count=diagnostic.g_diagnostic_boot.counter;
        clocks(20);
        if(diagnostic.g_diagnostic_boot.counter != start_count+20)
            $fatal(1,"diagnostic delay counter rate");
        // Skip quiescent waiting without changing the production RTL timing
        // constants; exercise both exact thresholds and the REAL debounce.
        diagnostic.g_diagnostic_boot.counter=9999999;
        clocks(1);
        if(diagnostic.diag_press)$fatal(1,"virtual press started before 200 ms threshold");
        clocks(1);
        if(!diagnostic.diag_press)$fatal(1,"200 ms virtual press threshold");
        clocks(499990);
        if(diagnostic.hdmi_request)$fatal(1,"virtual press bypassed production debounce");
        clocks(150);
        if(!diagnostic.hdmi_request || !diagnostic.hdmi_active || !drst || crst1 || crst2)
            $fatal(1,"debounced diagnostic press did not disable both cameras/select MS7200");
        diagnostic.g_diagnostic_boot.counter=14999999;
        clocks(1);
        if(!diagnostic.diag_press)$fatal(1,"virtual press ended before 100 ms duration");
        clocks(1);
        if(diagnostic.diag_press)$fatal(1,"virtual press failed to end");
        clocks(500010);
        if(!diagnostic.hdmi_request)$fatal(1,"virtual release changed the latched mode");
        if(diagnostic.g_diagnostic_boot.counter!=15000000)$fatal(1,"pulse counter not saturated");
        // Real keys remain usable after the automatic press has ended.
        key1=0;clocks(500150);key1=1;clocks(500010);
        if(diagnostic.hdmi_request || diagnostic.hdmi_active || drst)
            $fatal(1,"physical KEY1 cannot return diagnostic build to cameras");
        key2=0;clocks(500150);key2=1;clocks(500010);
        if(!diagnostic.hdmi_request || !diagnostic.hdmi_active || !drst || crst1 || crst2)
            $fatal(1,"physical KEY2 cannot reselect HDMI");
        if(diagnostic.diag_press)$fatal(1,"diagnostic pulse repeated");
        $display("TEST PASS: production defaults cameras/no auto press; diagnostic 200/100 ms thresholds, real 10 ms debounce, latched release, physical keys, both camera resets and RX reset");
        $finish;
    end
    initial begin #80000000;$fatal(1,"diagnostic boot watchdog");end
endmodule
