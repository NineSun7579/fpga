`timescale 1ns/1ps
// Full-size digital capture -> production TX -> unmodified 100H RX test.
module tb_capture_formats;
    reg test_pass=0;
    reg sys=0, outclk=0, fab=0, pclk=0;
    always #10 sys=~sys;
    always #8 outclk=~outclk;
    always #4 fab=~fab;
    real half_period=6.734007; // 74.25 MHz; 1080p changes to 3.367003 ns.
    reg plugged=1;
    always begin #(half_period); if(plugged) pclk=~pclk; end
    reg rst=0, request=1, vs=0, de=0;
    reg [7:0] r=0,g=0,b=0;
    wire hdmi_reset, cam_reset, tx_reset, active, fault, valid;
    wire [18:0] hdmi, video;
    hdmi_720p_capture capture(.pclk(pclk),.out_clk(outclk),
        .request_n(hdmi_reset),.capture_ready(1'b1),
        .vs_in(vs),.hs_in(1'b0),.de_in(de),.r_in(r),.g_in(g),.b_in(b),
        .video(hdmi),.fault(fault),.format_ok(valid));
    video_mode_switch #(.TIMEOUT_CYCLES(2000)) mode(
        .clk(outclk),.rst_n(rst),.hdmi_request(request),.cam_video(19'b0),
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
    sfp_video_rx rx(fab,rst,1'b1,txd,txk,rxvs,rxhs,rxde,rxpix,overflow);
    integer errors=0, hcount=0, rxcount=0, packets=0, full_frames=0;
    integer expected=0, peak_used=0, used_now, fault_count=0, flush_count=0;
    integer full720=0, full1080=0, i, snapshot;
    reg video_vs_d=0, rxvs_d=0, fault_d=0, reset_d=0;
    function [15:0] pixel(input integer n,input integer kind);
        integer yy,xx,phase;
        reg [7:0] rr,gg,bb;
        begin
            if(kind==1080) begin
                phase=(n/1280)%4;
                case(phase)
                    0: yy=(n/1280/4)*9;
                    1: yy=(n/1280/4)*9+2;
                    2: yy=(n/1280/4)*9+4;
                    3: yy=(n/1280/4)*9+7;
                endcase
                xx=((n%1280)/2)*3+(n%2);
            end else begin
                yy=(n/1280/2)*3+(n/1280%2); xx=n%1280;
            end
            rr=xx%256; gg=yy%256; bb=(xx+yy)%256;
            pixel={rr[7:3],gg[7:2],bb[7:3]};
        end
    endfunction
    task fail(input string reason);
        begin
            $display("FAIL @%0t %s",$time,reason); errors=errors+1;
            if(errors>10) $fatal(1,"too many failures");
        end
    endtask
    always @(negedge outclk) if(rst) begin
        if(video[18] && !video_vs_d) hcount=0;
        video_vs_d=video[18];
        if(video[16]) begin
            if(expected && (hcount>=614400 || video[15:0] !== pixel(hcount,expected)))
                fail($sformatf("adapter %0dp pixel %0d got %h expected %h",
                    expected,hcount,video[15:0],pixel(hcount,expected)));
            hcount=hcount+1;
        end
        if(fault && !fault_d) fault_count=fault_count+1;
        fault_d=fault;
        if(!hdmi_reset && reset_d) flush_count=flush_count+1;
        reset_d=hdmi_reset;
    end
    always @(negedge pclk) if(hdmi_reset && capture.wr_rst_n) begin
        // Diagnostic only: pointers observed together, no synthesizable CDC.
        used_now=(capture.u_fifo.wbin-capture.u_fifo.rbin)&4095;
        if(used_now>peak_used) peak_used=used_now;
        if(expected && capture.full) fail("capture FIFO full");
    end
    always @(negedge fab) if(rst) begin
        if(overflow) fail("actual receiver FIFO overflow");
        if(txk==0) packets=packets+1;
        if(rxvs && !rxvs_d) rxcount=0;
        rxvs_d=rxvs;
        if(rxde) begin
            if(expected && (rxcount>=614400 || rxpix !== pixel(rxcount,expected)))
                fail($sformatf("actual RX %0dp pixel %0d got %h expected %h",
                    expected,rxcount,rxpix,pixel(rxcount,expected)));
            rxcount=rxcount+1;
        end
    end
    task settle; repeat(200) @(negedge outclk); endtask
    task reacquire;
        begin
            // Lock loss invokes common flush; wait through that interval
            // before presenting the first complete geometry-measurement VS.
            repeat(200) tick(); settle();
            if(!capture.input_locked || !capture.wr_rst_n || !capture.rd_rst_n)
                fail("PLL did not reacquire/reset-release");
        end
    endtask
    // Change only after the input falling sample has completed, with the
    // entire RGB/DE bus stable before its next falling sample.
    task tick; @(negedge pclk); #0.01; endtask
    task sof;
        begin
            tick(); vs=1; de=0;
            repeat(5) tick();
            vs=0; repeat(5) tick();
        end
    endtask
    task line(input integer width,input integer yy,input integer blank);
        integer xx;
        begin
            for(xx=0;xx<width;xx=xx+1) begin
                de=1; r=xx%256; g=yy%256; b=(xx+yy)%256; tick();
            end
            de=0; repeat(blank) tick();
        end
    endtask
    task frame(input integer width,input integer height,input integer blank);
        integer yy;
        begin
            sof();
            for(yy=0;yy<height;yy=yy+1) line(width,yy,blank);
            repeat(200) tick(); settle();
        end
    endtask
    task check_full(input integer kind);
        begin
            if(hcount!=614400 || rxcount!=614400 || fault || !valid)
                fail($sformatf("%0dp totals capture=%0d actualRX=%0d valid=%b fault=%b",
                    kind,hcount,rxcount,valid,fault));
            full_frames=full_frames+1;
            if(kind==720)full720=full720+1; else full1080=full1080+1;
            $display("FULL FRAME %0dp: capture=%0d actualRX=%0d peakFIFO=%0d",
                kind,hcount,rxcount,peak_used);
        end
    endtask
    initial begin
        repeat(10) @(negedge sys); rst=1; settle();
        if(!active || !hdmi_reset) fail("HDMI selection did not start");
        frame(1280,720,370);
        if(hcount || rxcount || valid) fail("unqualified 720p payload");
        expected=720; frame(1280,720,370); check_full(720);
        // Same selected source, new 148.5 MHz input: previous admitted format
        // must fault and flush when the first line becomes wider than 1280.
        expected=0; half_period=3.367003; snapshot=fault_count;
        reacquire();
        if(fault_count!=snapshot+1 || flush_count==0)
            fail("720->1080 change did not fault/flush");
        snapshot=packets; frame(1920,1080,280);
        if(packets!=snapshot || valid) fail("1080 qualification emitted payload");
        expected=1080; frame(1920,1080,280); check_full(1080);
        frame(1920,1080,280); check_full(1080); // independent repeated SOF/order
        // Wrong width in an admitted frame must abort; neither repeated
        // wrong width nor correct width with wrong height may qualify.
        expected=0; snapshot=fault_count; frame(1918,1080,280);
        if(fault_count!=snapshot+1) fail("short width did not abort");
        snapshot=packets; frame(1918,1080,280); frame(1918,1080,280);
        if(valid || packets!=snapshot) fail("unsupported 1918 width admitted");
        frame(1920,1079,280); frame(1920,1079,280);
        if(valid || packets!=snapshot) fail("unsupported 1079 height admitted");
        // Recover automatically to 720p without a key selection change.
        half_period=6.734007; reacquire(); frame(1280,720,370);
        if(valid || packets!=snapshot) fail("720 reacquisition emitted payload");
        expected=720; frame(1280,720,370); check_full(720);
        // Short admitted height is recognized at the following VS, before
        // another frame can be admitted. Both FIFO domains are flushed.
        expected=0; frame(1280,719,370); snapshot=fault_count;
        sof(); settle();
        if(fault_count!=snapshot+1) fail("short admitted height did not abort at VS");
        // A mixed-width measurement must never qualify even if its final
        // height is supported. Use short malformed DE pulses for speed.
        sof();
        for(i=0;i<720;i=i+1) line(i==360 ? 1278 : 1280,i,370);
        de=0; settle(); snapshot=packets; frame(1280,720,370);
        if(valid || packets!=snapshot) fail("mixed-width frame qualified");
        expected=720; frame(1280,720,370); check_full(720);
        // Unplug in a retained row, at a supported line length so geometry
        // cannot detect it. Mode switch must timeout, then switch to cameras.
        expected=0; sof(); line(1280,0,370); plugged=0;
        repeat(2500) @(negedge sys); request=0; settle();
        if(active || hdmi_reset || !cam_reset) fail("unplug timeout/switch failed");
        snapshot=packets; settle();
        if(packets!=snapshot) fail("stale unplug payload after flush");
        if(errors) $fatal(1,"TEST FAIL errors=%0d",errors);
        $display("TEST PASS: full720=%0d full1080=%0d exact614400 RGB565 actual100H_RX; transition/unsupported/mixedwidth/shortheight/unplug; peakFIFO=%0d faultFlushes=%0d packets=%0d",
            full720,full1080,peak_used,fault_count,packets);
        test_pass=1;
        $finish;
    end
    initial begin #400000000; $fatal(1,"format test watchdog"); end
endmodule

// Reduced legacy override and coincident final line-end/SOF regression.
module tb_capture_preset;
    reg test_pass=0;
    reg pclk=0,outclk=0,reset_n=0,vs=0,de=0;
    always #6.734 pclk=~pclk;
    always #8 outclk=~outclk;
    reg [7:0] r=0,g=0,b=0;
    wire [18:0] video;
    wire fault,valid;
    hdmi_720p_capture #(.INPUT_WIDTH(6),.INPUT_HEIGHT(6),.OUTPUT_HEIGHT(4),.FIFO_DEPTH(32)) dut(
        .pclk(pclk),.out_clk(outclk),.request_n(reset_n),.capture_ready(1'b1),
        .vs_in(vs),.hs_in(1'b0),.de_in(de),.r_in(r),.g_in(g),.b_in(b),
        .video(video),.fault(fault),.format_ok(valid));
    integer count=0,full=0;
    reg expect_payload=0,vs_d=0;
    function [15:0] pixel(input integer n);
        integer yy,xx;
        reg [7:0] rr,gg,bb;
        begin
            yy=(n/6/2)*3+(n/6%2);xx=n%6;
            rr=xx*32;gg=yy*32;bb=(xx+yy)*16;
            pixel={rr[7:3],gg[7:2],bb[7:3]};
        end
    endfunction
    always @(negedge outclk) if(reset_n)begin
        if(video[18] && !vs_d)begin
            if(expect_payload)begin
                if(count!=24)$fatal(1,"preset/coincident VS count=%0d",count);
                full=full+1;
            end else if(count)$fatal(1,"preset qualification emitted pixels");
            count=0;
        end
        vs_d=video[18];
        if(video[16])begin
            if(!expect_payload || video[15:0]!==pixel(count))
                $fatal(1,"preset RGB/order pixel %0d",count);
            count=count+1;
        end
    end
    task tick; @(negedge pclk); #0.01; endtask
    task body;
        integer yy,xx;
        begin
            vs=0;repeat(5)tick();
            for(yy=0;yy<6;yy=yy+1)begin
                for(xx=0;xx<6;xx=xx+1)begin
                    de=1;r=xx*32;g=yy*32;b=(xx+yy)*16;tick();
                end
                de=0;
                if(yy==5)vs=1; // simultaneous DE fall and VS rise
                repeat(12)tick();
            end
            repeat(20)tick();
        end
    endtask
    initial begin
        repeat(10)tick();reset_n=1;repeat(32)tick();
        vs=1;repeat(10)tick();body();
        if(!valid || fault)$fatal(1,"preset/coincident last line failed qualification");
        expect_payload=1;body();
        if(full!=1 || !valid || fault)$fatal(1,"preset full frame failed");
        $display("TEST PASS: legacy 6x6->6x4 RGB565 override, coincident final DE fall/VS rise, exact24 pixels");
        test_pass=1;
        $finish;
    end
    initial begin #100000;$fatal(1,"preset watchdog");end
endmodule
