`timescale 1ns/1ps
module tb_motion_stream_adapter;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, valid=0, vs=0;
    reg [15:0] pix=0;
    wire [319:0] record;
    motion_stream_adapter #(.WIDTH(8), .HEIGHT(8), .SAMPLE_STEP(1),
        .BLOCK_SAMPLES_X(2), .BLOCK_SAMPLES_Y(2), .BLOCK_THRESHOLD(2)) dut (
        .clk(clk), .rst_n(rst_n), .pixel_rgb565(pix),
        .pixel_valid(valid), .vsync(vs), .motion_record(record)
    );
    integer publications=0, accepted=0;
    reg expected_start=0, expected_end=0, expected_valid=0;
    reg [15:0] expected_rgb=0;
    always @(posedge clk) if (rst_n) begin
        if (dut.strobe) publications=publications+1;
        if (dut.fire) accepted=accepted+1;
        if ((dut.core_start || dut.core_end) && dut.core_valid)
            $fatal(1,"marker consumed pixel");
        if ({dut.core_start,dut.core_end,dut.core_valid,dut.core_rgb} !==
            {expected_start,expected_end,expected_valid,expected_rgb})
            $fatal(1,"registered event tuple changed alignment");
        if (dut.overflow || dut.overflow_reset) begin
            expected_start=0; expected_end=0; expected_valid=0; expected_rgb=0;
        end else begin
            expected_start=dut.start || dut.excess;
            expected_end=dut.end_pending;
            expected_valid=dut.fire;
            expected_rgb=dut.head[15:0];
        end
        if (dut.queued > 16) $fatal(1,"event queue overflow");
    end
    task beat(input bit v, input bit s, input [15:0] p);
        @(negedge clk); valid=v; vs=s; pix=p;
    endtask
    task idle(input integer n);
        repeat(n) beat(0,0,0);
    endtask
    task image(input [15:0] p, input bit gaps, input bit simultaneous);
        integer i;
        if (!simultaneous) beat(0,1,0);
        for(i=0;i<64;i=i+1) begin
            beat(1,(i==0 && simultaneous),p);
            if(gaps && i%7==3) idle(2);
        end
        idle(10);
    endtask
    task check(input [31:0] seq, input [31:0] flags,
               input [31:0] counts, input [31:0] bbox, input [191:0] bitmap);
        if(record !== {bitmap,bbox,counts,flags,seq}) begin
            $display("actual=%h expected=%h",record,{bitmap,bbox,counts,flags,seq});
            $fatal(1,"record ABI/content mismatch");
        end
        idle(4);
        if(record !== {bitmap,bbox,counts,flags,seq}) $fatal(1,"record not held");
    endtask
    reg small_done=0, full_done=0, overflow_done=0;
    reg [319:0] held;
    integer before_count;
    initial begin
        idle(3); rst_n=1;
        repeat(80) beat(1,0,16'hffff);
        idle(10);
        if(record!==0 || accepted!=0) $fatal(1,"reset acquisition did not wait for VSYNC");
        image(0,0,1); check(1,0,0,0,0);
        image(16'hffff,0,1);
        check(2,3,32'h00004010,32'h00003030,192'hffff);
        image(16'hffff,1,0); check(3,1,0,0,0);
        // Exactly one legacy dummy must be excluded and preserve comparison.
        beat(1,0,0); idle(5);
        image(16'hffff,0,1); check(4,1,0,0,0);
        // Aborted frame overwrites history, never publishes, and invalidates it.
        held=record; before_count=publications;
        beat(1,1,0); repeat(12) beat(1,0,0); idle(3);
        if(record!==held || publications!=before_count) $fatal(1,"short frame published");
        image(16'hffff,0,1); check(6,4,0,0,0);
        if(dut.short_frame_count!=1) $fatal(1,"short diagnostic counter");
        image(0,1,1); check(7,3,32'h00004010,32'h00003030,192'hffff);
        // Two tail beats: exclude both, invalidate reference at next start.
        beat(1,0,16'hffff); beat(1,0,16'hffff); idle(5);
        image(0,0,1); check(8,4,0,0,0);
        image(0,0,1); check(9,1,0,0,0);
        if(publications!=8) $fatal(1,"publication count %d",publications);
        if(accepted!=8*64+13) $fatal(1,"accepted pixels %d",accepted);
        // A level VSYNC is one start, even while pixels continue.
        for(integer j=0;j<64;j=j+1) beat(1,j<5,0);
        idle(10); check(10,1,0,0,0);
        // Distinct final RGB catches a tuple skew hidden by uniform frames.
        // Five blank clocks are the sustained boundary-throughput contract.
        beat(1,1,0); repeat(63) beat(1,0,0); idle(5);
        beat(1,1,0); repeat(62) beat(1,0,0); beat(1,0,16'hffff);
        idle(10); check(12,1,32'h00000100,0,0);
        image(16'hffff,0,1);
        check(13,3,32'h00003f10,32'h00003030,192'hffff);
        $display("PASS adapter ABI, reset, continuous/gapped frames, coincident pixel0, last sample, dummy, short restart, excess tail");
        small_done=1;
    end
    reg full_valid=0, full_vs=0;
    reg [15:0] full_pix=0;
    wire [319:0] full_record;
    // Match the packed dimension parameters passed by the OV5640 wrapper.
    motion_stream_adapter #(.WIDTH(11'd640), .HEIGHT(11'd480)) full_dut(.clk(clk),.rst_n(rst_n),
        .pixel_rgb565(full_pix),.pixel_valid(full_valid),.vsync(full_vs),
        .motion_record(full_record));
    integer f,i;
    initial begin
        if ($bits(full_dut.WIDTH)!=32 || $bits(full_dut.HEIGHT)!=32 ||
            full_dut.TOTAL!=307200 || $bits(full_dut.pixels)!=19 ||
            full_dut.u_detector.TOTAL_PIXELS!=307200 ||
            $bits(full_dut.u_detector.pixel_count)!=19 ||
            full_dut.u_detector.TOTAL_SAMPLES!=19200 ||
            full_dut.u_detector.TOTAL_BLOCKS!=192)
            $fatal(1,"packed 11-bit adapter/core geometry truncated");
        wait(rst_n);
        for(f=0;f<2;f=f+1) begin
            for(i=0;i<640*480;i=i+1) begin
                @(negedge clk); full_valid=1; full_vs=(i==0);
                full_pix=(f==0 ? 16'h0000 : 16'hffff);
            end
            @(negedge clk); full_valid=1; full_vs=0; full_pix=0;
            @(negedge clk); full_valid=0;
            repeat(10) @(negedge clk);
            if(full_record[31:0]!==f+1) $fatal(1,"full source sequence");
            if(f==0 && full_record[63:32]!==0) $fatal(1,"full acquisition flags");
            if(f==1 && full_record !== {192'hffffffffffffffffffffffffffffffffffffffffffffffff,
                 32'h0000b0f0,32'h004b00c0,32'd3,32'd2})
                $fatal(1,"full 640x480 bitmap/count/bbox %h",full_record);
        end
        $display("PASS adapter 640x480 continuous frames and dummy: 192 blocks, 19200 samples");
        full_done=1;
    end
    initial begin
        wait(small_done && full_done && overflow_done);
        $display("PASS tb_motion_stream_adapter");
        $finish;
    end
    initial begin #10000000; $fatal(1,"timeout"); end
    reg tiny_valid=0, tiny_vs=0, tiny_link_ready=1;
    reg [15:0] tiny_pix=0;
    wire [319:0] tiny_record;
    motion_stream_adapter #(.WIDTH(2), .HEIGHT(2), .SAMPLE_STEP(1),
        .BLOCK_SAMPLES_X(1), .BLOCK_SAMPLES_Y(1), .BLOCK_THRESHOLD(1)) tiny (
        .clk(clk), .rst_n(rst_n && tiny_link_ready), .pixel_rgb565(tiny_pix),
        .pixel_valid(tiny_valid), .vsync(tiny_vs), .motion_record(tiny_record)
    );
    integer tiny_starts=0, tiny_cycle=0;
    reg tiny_vs_q=0;
    reg [319:0] overflow_held;
    always @(posedge clk) if(rst_n) begin
        tiny_vs_q <= tiny_vs;
        if(tiny_vs && !tiny_vs_q) tiny_starts=tiny_starts+1;
        if(tiny.queued>16) $fatal(1,"tiny FIFO overflowed occupancy");
        if(tiny.overflow && tiny.fire) $fatal(1,"overflow issued pixel");
        if ((tiny.core_start || tiny.core_end) && tiny.core_valid)
            $fatal(1,"tiny marker consumed pixel");
    end
    task tiny_image(input [15:0] p);
        for(integer j=0;j<4;j=j+1) begin
            @(negedge clk); tiny_valid=1; tiny_vs=(j==0); tiny_pix=p;
        end
        @(negedge clk); tiny_valid=0; tiny_vs=0;
        repeat(10) @(negedge clk);
    endtask
    initial begin
        wait(rst_n);
        // No blanking: boundary drain makes the producer outrun the FIFO.
        while(tiny.overflow_count==0) begin
            @(negedge clk);
            if(tiny.overflow_count==0) begin
                tiny_valid=1; tiny_vs=(tiny_cycle%4==0); tiny_pix=0;
                tiny_cycle=tiny_cycle+1;
            end
            if(tiny_cycle>200) $fatal(1,"forced overflow not reached");
        end
        tiny_valid=0; tiny_vs=0; overflow_held=tiny_record;
        repeat(10) @(negedge clk);
        if(tiny.queued!=0 || tiny.acquired || tiny.u_detector.reference_valid)
            $fatal(1,"overflow did not abort/drain/invalidate reference");
        if(tiny_record!==overflow_held) $fatal(1,"overflow published aborted frame");
        // Mid-frame traffic after loss must be ignored until another source edge.
        repeat(20) begin @(negedge clk); tiny_valid=1; end
        @(negedge clk); tiny_valid=0;
        repeat(5) @(negedge clk);
        if(tiny_record!==overflow_held || tiny.queued!=0)
            $fatal(1,"overflow recovery acquired without VSYNC");
        tiny_image(0);
        if(tiny_record !== {192'b0,32'b0,32'b0,32'd4,32'(tiny_starts)})
            $fatal(1,"overflow recovery record %h source starts %d",tiny_record,tiny_starts);
        tiny_image(16'hffff);
        if(tiny_record !== {192'hf,32'h00001010,32'h00000404,32'd3,32'(tiny_starts)})
            $fatal(1,"overflow reference recovery/ABI %h",tiny_record);
        $display("PASS forced tiny-frame FIFO overflow: abort, held status, fresh VSYNC recovery, source sequence, comparison restored");
        // CAM5/6 link-status reset must remove the old reference and reacquire.
        tiny_link_ready=0;
        repeat(3) @(negedge clk);
        if(tiny_record!==0) $fatal(1,"link-loss reset retained stale record");
        tiny_link_ready=1;
        repeat(10) begin @(negedge clk); tiny_valid=1; end
        @(negedge clk); tiny_valid=0;
        repeat(5) @(negedge clk);
        if(tiny_record!==0 || tiny.queued!=0) $fatal(1,"link reset accepted midframe");
        tiny_image(0);
        if(tiny_record !== {192'b0,32'b0,32'b0,32'b0,32'd1})
            $fatal(1,"link recovery acquisition ABI");
        tiny_image(16'hffff);
        if(tiny_record !== {192'hf,32'h00001010,32'h00000404,32'd3,32'd2})
            $fatal(1,"link recovery comparison ABI");
        $display("PASS link-loss reset: clear record, ignore midframe, fresh acquisition and reference");
        // Sustain the minimum blanking contract over many queued boundaries.
        // Alternating frames expose publication/sequence mixing at each start.
        for(integer k=0;k<20;k=k+1) begin
            for(integer j=0;j<4;j=j+1) begin
                @(negedge clk); tiny_valid=1; tiny_vs=(j==0);
                tiny_pix=(k%2==0 ? 16'h0000 : 16'hffff);
            end
            repeat(5) begin @(negedge clk); tiny_valid=0; tiny_vs=0; end
        end
        repeat(10) @(negedge clk);
        if(tiny.overflow_count!=0 || tiny.queued!=0 ||
           tiny_record !== {192'hf,32'h00001010,32'h00000404,32'd3,32'd22})
            $fatal(1,"five-clock blanking throughput/record contract %h",tiny_record);
        $display("PASS five-clock blanking: 20 adjacent alternating frames, stable FIFO, aligned sequence/result");
        overflow_done=1;
    end
endmodule
