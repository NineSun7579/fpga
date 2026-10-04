`timescale 1ns/1ps
module tb_hdmi_modes;
    reg test_pass=0;
    reg sys=0, outclk=0, fab=0, pclk=0;
    always #10 sys=~sys;
    always #8 outclk=~outclk;
    always #4 fab=~fab;
    reg plugged=1;
    real pclk_half=6.734007;
    always begin #(pclk_half); if (plugged) pclk=~pclk; end
    reg rst=0, k1=1, k2=1;
    wire request, active, cam_reset, hdmi_reset, tx_reset;
    video_mode_keys #(.DEBOUNCE_CYCLES(8)) keys(sys,rst,k1,k2,request);
    reg [18:0] cam=0;
    wire [18:0] hdmi, video;
    wire fault, valid;
    reg vs=0, de=0;
    reg [7:0] r=0,g=0,b=0;
    hdmi_720p_capture capture(.pclk(pclk),.out_clk(outclk),.request_n(hdmi_reset),
        .capture_ready(1'b1),.vs_in(vs),.hs_in(1'b0),.de_in(de),.r_in(r),.g_in(g),.b_in(b),
        .video(hdmi),.fault(fault),.format_ok(valid));
    video_mode_switch #(.TIMEOUT_CYCLES(2000)) mode(
        .clk(outclk),.rst_n(rst),.hdmi_request(request),.cam_video(cam),
        .hdmi_video(hdmi),.hdmi_fault(fault),.hdmi_active(active),
        .source_cam_request_n(cam_reset),.source_hdmi_request_n(hdmi_reset),
        .tx_request_n(tx_reset),.video(video));
    wire vr,fr;
    video_reset_sync rv(outclk,tx_reset,vr), rf(fab,tx_reset,fr);
    wire [31:0] txd;
    wire [3:0] txk;
    sfp_video_tx tx(outclk,vr,video,fab,fr,1'b1,txd,txk);
    wire rxvs,rxhs,rxde,overflow;
    wire [15:0] rxpix;
    // Use the real downloaded receiver read-only in the simulation file list.
    sfp_video_rx rx(fab,rst,1'b1,txd,txk,rxvs,rxhs,rxde,rxpix,overflow);
    integer errors=0, hcount=0, ccount=0, rxcount=0, packets=0, complete_hdmi=0;
    integer expected_kind=0;
    integer hdmi_kind=720;
    reg rxvs_d=0;
    function [15:0] hpixel(input integer n);
        integer yy,xx,phase;
        reg [7:0] rr,gg,bb;
        begin
            if(hdmi_kind==1080)begin
                phase=n/1280%4;
                case(phase)
                    0:yy=(n/1280/4)*9;
                    1:yy=(n/1280/4)*9+2;
                    2:yy=(n/1280/4)*9+4;
                    3:yy=(n/1280/4)*9+7;
                endcase
                xx=(n%1280/2)*3+(n%2);
            end else begin
                yy=(n/1280/2)*3+(n/1280%2); xx=n%1280;
            end
            rr=xx%256; gg=yy%256; bb=(xx+yy)%256;
            hpixel={rr[7:3],gg[7:2],bb[7:3]};
        end
    endfunction
    task fail(input string reason);
        begin $display("FAIL @%0t %s",$time,reason); errors=errors+1; if(errors>15)$fatal(1,"too many failures"); end
    endtask
    always @(negedge outclk) if(rst) begin
        if(cam_reset && hdmi_reset) fail("both sources enabled");
        if(video[16]) begin
            if(active) begin
                if(expected_kind==1 && video[15:0] !== hpixel(hcount)) fail($sformatf("adapter pixel %0d got %h expected %h",hcount,video[15:0],hpixel(hcount)));
                hcount=hcount+1;
            end else begin
                if(video[15:0] !== 16'h1234) fail("stale HDMI pixel in camera mode");
                ccount=ccount+1;
            end
        end
    end
    always @(negedge fab) if(rst) begin
        if(overflow) fail("actual receiver FIFO overflow");
        if(txk==0) packets=packets+1;
        if(rxvs && !rxvs_d) begin
            if(expected_kind==1 && rxcount==614400) complete_hdmi=complete_hdmi+1;
            rxcount=0;
        end
        rxvs_d=rxvs;
        if(rxde) begin
            if(expected_kind==1 && rxpix !== hpixel(rxcount)) fail($sformatf("wire pixel %0d got %h expected %h",rxcount,rxpix,hpixel(rxcount)));
            if(expected_kind==2 && rxpix !== 16'h1234) fail("stale wire pixel in camera mode");
            rxcount=rxcount+1;
        end
    end
    task cycles(input integer n); repeat(n) @(negedge sys); endtask
    task press(input integer which);
        begin
            if(which==1)k1=0; else k2=0;
            cycles(14);
            if(which==1)k1=1; else k2=1;
            cycles(14);
        end
    endtask
    task camera_frame;
        integer i;
        begin
            @(negedge outclk);cam={1'b1,2'b0,16'b0};
            repeat(5)@(negedge outclk);
            cam=0;repeat(4)@(negedge outclk);
            for(i=0;i<614400;i=i+1)begin cam={3'b001,16'h1234};@(negedge outclk);end
            cam=0;repeat(100)@(negedge outclk);
        end
    endtask
    task hdmi_frame(input integer width);
        integer yy,xx;
        begin
            @(negedge pclk);vs=1;de=0;
            repeat(5)@(negedge pclk);
            vs=0;repeat(5)@(negedge pclk);
            for(yy=0;yy<(width==1920 ? 1080 : 720);yy=yy+1)begin
                for(xx=0;xx<width;xx=xx+1)begin
                    de=1;r=xx%256;g=yy%256;b=(xx+yy)%256;
                    @(negedge pclk);
                end
                de=0;repeat(width==1920 ? 280 : 370)@(negedge pclk);
            end
            repeat(200)@(negedge pclk);
        end
    endtask
    integer snapshot;
    initial begin
        cycles(5);rst=1;cycles(20);
        if(request || active || !cam_reset || hdmi_reset)fail("default camera mode");
        k2=0;cycles(3);k2=1;cycles(15);
        if(request)fail("short bounce accepted");
        expected_kind=2;
        fork
            camera_frame();
            begin cycles(100);press(2);cycles(20);if(active)fail("mode changed mid camera frame");end
        join
        cycles(100);
        if(!request || !active || cam_reset || !hdmi_reset)fail("latched HDMI selection");
        if(ccount!=614400)fail("old camera frame was truncated");
        expected_kind=1;rxcount=0;hcount=0;
        hdmi_frame(1280); // geometry qualification: no payload
        if(hcount!=0)fail("unqualified HDMI frame admitted");
        hdmi_frame(1280); // full 720p -> 480p payload
        cycles(100);
        if(hcount!=614400 || rxcount!=614400 || packets<614400)fail($sformatf("pixel/packet totals h=%0d rx=%0d packets=%0d",hcount,rxcount,packets));
        // Source changes while HDMI remains selected: fault flush, then a
        // complete measured frame, then all 614400 pixels through actual RX.
        expected_kind=0;pclk_half=3.367003;
        hdmi_frame(1920);hdmi_frame(1920);
        hcount=0;hdmi_kind=1080;expected_kind=1;
        hdmi_frame(1920);cycles(100);
        if(hcount!=614400 || rxcount!=614400 || !valid)
            fail($sformatf("1080p totals h=%0d rx=%0d valid=%b",hcount,rxcount,valid));
        expected_kind=0;pclk_half=6.734007;
        hdmi_frame(1280);hdmi_frame(1280);
        hdmi_kind=720;expected_kind=1;
        hcount=0;
        fork
            hdmi_frame(1280);
            begin cycles(100);press(1);cycles(20);if(!active)fail("mode changed mid HDMI frame");end
        join
        cycles(100);
        if(active || request)fail("KEY1 camera selection");
        if(hcount!=614400)fail("HDMI frame truncated by key");
        expected_kind=2;rxcount=0;
        camera_frame();cycles(100);
        if(rxcount!=614400)fail("camera restart packet total");
        // Simultaneous keys select HDMI; release is stable, held KEY2 dominates.
        k1=0;k2=0;cycles(20);k1=1;cycles(12);
        if(!request)fail("both-key priority");
        k1=0;cycles(14);k1=1;cycles(14);
        if(!request)fail("held KEY2 lost priority");
        k2=1;cycles(20);
        expected_kind=0;
        if(!active)fail("HDMI request not committed while idle");
        // Unplugged pixel clock must not deadlock a return to cameras.
        plugged=0;snapshot=packets;cycles(100);press(1);cycles(100);
        if(active || !cam_reset || hdmi_reset)fail("unplug return to cameras");
        if(packets!=snapshot)fail("unplug generated pixels");
        // Repeated asynchronous switches while no source produces pixels.
        repeat(5)begin press(2);cycles(100);if(!active)fail("idle HDMI switch");
                        press(1);cycles(100);if(active)fail("idle camera switch");end
        // Wrong geometry never becomes valid or produces payload.
        plugged=1;press(2);cycles(100);snapshot=packets;
        hdmi_frame(1278);hdmi_frame(1278);cycles(100);
        if(valid || packets!=snapshot)fail("unsupported width admitted");
        // Qualify, start a valid frame then remove the clock mid-frame.
        hdmi_frame(1280);hcount=0;hdmi_frame(1280);hcount=0;
        @(negedge pclk);vs=1;repeat(5)@(negedge pclk);vs=0;
        repeat(5)@(negedge pclk);de=1;r=0;g=0;b=0;
        for(snapshot=0;snapshot<20;snapshot=snapshot+1)begin
            r=snapshot;b=snapshot;@(negedge pclk);
        end
        de=0;plugged=0;
        expected_kind=0;cycles(2500);press(1);cycles(100);
        if(active || !cam_reset)fail("stalled frame timeout/flush failed");
        if(errors==0)$display("TEST PASS: default/debounce/latch/priority, full 720p/1080p decimation and transitions, RGB565 actual RX, frame-boundary switches, isolation, unsupported width, unplug/timeout; packets=%0d",packets);
        else $fatal(1,"TEST FAIL errors=%0d",errors);
        test_pass=1;
        $finish;
    end
    initial begin #250000000;$fatal(1,"test watchdog");end
endmodule
