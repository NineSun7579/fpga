`timescale 1ns/1ps
module tb;
    reg clk=0, rst=0, raw=0, href=0;
    reg [7:0] data=0;
    always #5.952 clk=~clk;
    wire filtered, bypass, one, three;
    filter_under_test #(64) dut(clk,rst,raw,filtered);
    filter_under_test #(0) bp(clk,rst,raw,bypass);
    filter_under_test #(1) n1(clk,rst,raw,one);
    filter_under_test #(3) n3(clk,rst,raw,three);
    wire fs, hs, valid;
    wire [15:0] pixel;
    cmos_capture capture(.rst_n(rst), .cam_pclk(clk), .cam_vsync(filtered),
        .cam_href(href), .cam_data(data), .cmos_frame_vsync(fs),
        .cmos_frame_href(hs), .cmos_frame_valid(valid), .cmos_frame_data(pixel));
    wire ref_fs, ref_hs, ref_valid;
    wire [15:0] ref_pixel;
    cmos_capture reference_capture(.rst_n(rst), .cam_pclk(clk), .cam_vsync(raw),
        .cam_href(href), .cam_data(data), .cmos_frame_vsync(ref_fs),
        .cmos_frame_href(ref_hs), .cmos_frame_valid(ref_valid), .cmos_frame_data(ref_pixel));
    integer rises=0, falls=0, frames=0, words=0, raw_rises=0;
    reg last=0, last_fs=0, last_raw=0, compare_pixels=0;
    always @(posedge clk) begin
        #1;
        if (rst) begin
            if(filtered && !last) rises=rises+1;
            if(!filtered && last) falls=falls+1;
            if(fs && !last_fs) frames=frames+1;
            if(raw && !last_raw) raw_rises=raw_rises+1;
            if(compare_pixels) begin
                if ({hs,valid,pixel} !== {ref_hs,ref_valid,ref_pixel})
                    $fatal(1,"HREF/data timing changed");
                if(valid) words=words+1;
            end
        end
        last=filtered; last_fs=fs; last_raw=raw;
    end
    task drive(input bit level, input integer cycles);
        begin
            @(negedge clk); raw=level;
            #1; if(bypass !== raw) $fatal(1,"bypass not combinational");
            repeat(cycles) begin @(posedge clk); #2; end
        end
    endtask
    task expect_level(input bit level);
        if(filtered !== level) $fatal(1,"filter level expected %b",level);
    endtask
    integer i,j,before_rises,before_frames;
    initial begin
        #1; rst=1; #1; rst=0; #1;
        expect_level(0);
        drive(1,10); expect_level(0);
        if(bypass !== 1) $fatal(1,"bypass reset behavior");
        @(negedge clk); raw=0; rst=1;
        drive(0,4);
        for(i=1;i<64;i=i+1) begin
            drive(1,i); expect_level(0);
            drive(0,2); expect_level(0);
        end
        if(rises!=0 || capture.cmos_ps_cnt!=0) $fatal(1,"positive glitch frame");
        drive(1,63); expect_level(0);
        drive(1,1); expect_level(1);
        if(one !== 1 || three !== 1) $fatal(1,"small parameter acceptance");
        for(i=1;i<64;i=i+1) begin
            drive(0,i); expect_level(1);
            drive(1,2); expect_level(1);
        end
        drive(1,10000);
        if(rises!=1 || falls!=0) $fatal(1,"negative glitch/repeated frame");
        drive(0,63); expect_level(1);
        drive(0,1); expect_level(0);
        drive(0,10000);
        if(rises!=1 || falls!=1) $fatal(1,"idle fabricated frame");
        // Reset discards a partially qualified transition.
        drive(1,40); rst=0; #1; expect_level(0);
        @(negedge clk); rst=1;
        repeat(63) begin @(posedge clk); #2; end
        expect_level(0);
        @(posedge clk); #2; expect_level(1);
        rst=0; #1; expect_level(0);
        drive(0,4); @(negedge clk); rst=1;
        // Real capture WAIT_FRAME=10: eleven clean pulses open capture.
        for(i=0;i<11;i=i+1) begin drive(1,128); drive(0,128); end
        if(!capture.frame_val_flag) $fatal(1,"capture never enabled");
        before_rises=rises; before_frames=frames;
        compare_pixels=1;
        // Full 640x480 payload; 1896 PCLK line spacing, glitches in active lines.
        for(i=0;i<480;i=i+1) begin
            for(j=0;j<1896;j=j+1) begin
                @(negedge clk);
                href=(j<1280); data=(i+j);
                raw=(j>=200 && j<231);
            end
        end
        @(negedge clk); href=0; raw=0;
        repeat(10) @(negedge clk);
        compare_pixels=0;
        if(words!=640*480) $fatal(1,"full-frame words %0d",words);
        if(rises!=before_rises || frames!=before_frames) $fatal(1,"active glitch split frame");
        drive(1,128); drive(0,128);
        if(rises!=before_rises+1 || frames!=before_frames+1) $fatal(1,"legal frame missing/duplicated");
        // Thresholds 1 and 3, including consecutive-run restart.
        drive(1,1); if(one!==1 || three!==0) $fatal(1,"N=1/3 early");
        drive(0,1); if(one!==0 || three!==0) $fatal(1,"N=3 restart");
        drive(1,2); if(three!==0) $fatal(1,"N=3 early after restart");
        drive(1,1); if(three!==1) $fatal(1,"N=3 late");
        $display("PASS cam3 VSYNC: widths 1..63 both polarities, exact 64, reset, bypass, N=1/3, idle 10000 cycles, capture words=%0d raw_rises=%0d",words,raw_rises);
        $finish;
    end
    initial begin #20000000; $fatal(1,"timeout"); end
endmodule
