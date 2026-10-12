`timescale 1ns/1ps
module tb_motion_tc05;
    parameter W=640, H=480, SEED=1;
    reg clk=0, rst_n=0, valid=0, vs=0;
    reg [15:0] rgb=0;
    always #5 clk=~clk;
    wire [319:0] ref_record, new_record;
    motion_stream_adapter_tc04 #(.WIDTH(W),.HEIGHT(H)) ref_dut(
        .clk(clk),.rst_n(rst_n),.pixel_rgb565(rgb),.pixel_valid(valid),.vsync(vs),.motion_record(ref_record));
    motion_stream_adapter_tc05_test #(.WIDTH(W),.HEIGHT(H)) dut(
        .clk(clk),.rst_n(rst_n),.pixel_rgb565(rgb),.pixel_valid(valid),.vsync(vs),.motion_record(new_record));
    localparam NS=((W+3)/4)*((H+3)/4);

    integer history_checks=0, history_writes=0, history_resets=0;
    integer history_index, written_address;
    reg did_write;
    always @(posedge clk) begin
        did_write=dut.u_detector.rst_n && dut.u_detector.accept_sample;
        written_address=dut.u_detector.sample_address;

        if ({dut.u_detector.rst_n && dut.u_detector.accept_sample,dut.u_detector.sample_address,dut.u_detector.luma} !==
            {ref_dut.u_detector.rst_n && ref_dut.u_detector.accept_sample,ref_dut.u_detector.sample_address,ref_dut.u_detector.luma})
            $fatal(1,"TC05 history transaction differs from ref_dut.u_detector");

        #2;
        history_checks=history_checks+1;
        if (!dut.u_detector.rst_n) history_resets=history_resets+1;
        if (dut.u_detector.history_eligible !== (dut.u_detector.active &&
            dut.u_detector.pixel_count<dut.u_detector.TOTAL_PIXELS &&
            (dut.u_detector.x%dut.u_detector.SAMPLE_STEP)==0 && (dut.u_detector.y%dut.u_detector.SAMPLE_STEP)==0))
            $fatal(1,"TC05 lookahead invariant");
        if (did_write) history_writes=history_writes+1;

        if ({dut.u_detector.result_strobe,dut.u_detector.result_valid,dut.u_detector.bbox_valid,dut.u_detector.block_bitmap,dut.u_detector.changed_blocks,dut.u_detector.changed_samples,dut.u_detector.bbox_min_x,dut.u_detector.bbox_max_x,dut.u_detector.bbox_min_y,dut.u_detector.bbox_max_y,dut.u_detector.frame_sequence} !== {ref_dut.u_detector.result_strobe,ref_dut.u_detector.result_valid,ref_dut.u_detector.bbox_valid,ref_dut.u_detector.block_bitmap,ref_dut.u_detector.changed_blocks,ref_dut.u_detector.changed_samples,ref_dut.u_detector.bbox_min_x,ref_dut.u_detector.bbox_max_x,ref_dut.u_detector.bbox_min_y,ref_dut.u_detector.bbox_max_y,ref_dut.u_detector.frame_sequence})
            $fatal(1,"TC05 public output mismatch vs ref_dut.u_detector");
        if (dut.u_detector.history_q !== ref_dut.u_detector.history_q)
            $fatal(1,"TC05 read-first history_q mismatch vs ref_dut.u_detector");
        if (did_write && dut.u_detector.history[written_address] !== ref_dut.u_detector.history[written_address])
            $fatal(1,"TC05 written history byte mismatch vs ref_dut.u_detector");
        if (dut.u_detector.frame_start || dut.u_detector.frame_end || !dut.u_detector.rst_n) begin
            for (history_index=0;history_index<NS;history_index=history_index+1)
                if (dut.u_detector.history[history_index] !== ref_dut.u_detector.history[history_index])
                    $fatal(1,"TC05 retained history mismatch vs ref_dut.u_detector");
        end
    end
    integer comparisons=0, records=0, fires=0, overflows=0, shorts=0, boundaries=0;
    reg [31:0] rng=SEED;
    function [31:0] random_word;
        begin rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5); random_word=rng; end
    endfunction
    always @(posedge clk) begin
        if(rst_n) begin
            if(ref_dut.fire) fires=fires+1;
            if(ref_dut.overflow) overflows=overflows+1;
            if(ref_dut.start && ref_dut.active) shorts=shorts+1;
            if(ref_dut.strobe) records=records+1;
        end
        #1;
        if(ref_record !== new_record || ref_dut.pixels !== dut.pixels ||
           {ref_dut.core_start,ref_dut.core_end,ref_dut.core_valid,ref_dut.core_rgb,
            ref_dut.source_sequence,ref_dut.active_sequence,ref_dut.publish_sequence,
            ref_dut.overflow_count,ref_dut.short_frame_count,ref_dut.queued,
            ref_dut.error_pending,ref_dut.publish_error,ref_dut.active} !==
           {dut.core_start,dut.core_end,dut.core_valid,dut.core_rgb,
            dut.source_sequence,dut.active_sequence,dut.publish_sequence,
            dut.overflow_count,dut.short_frame_count,dut.queued,
            dut.error_pending,dut.publish_error,dut.active})
            $fatal(1,"motion mismatch cycle=%0d ref_pixels=%h new_pixels=%h",comparisons,ref_dut.pixels,dut.pixels);
        comparisons=comparisons+1;
    end
    task tick(input bit v,input bit s,input [15:0] p);
        begin @(negedge clk); valid=v; vs=s; rgb=p; @(posedge clk); #2; end
    endtask
    task idle(input integer n);
        integer i; begin for(i=0;i<n;i=i+1) tick(0,0,0); end
    endtask
    task reset_all;
        begin @(negedge clk); rst_n=0; valid=0; vs=0; idle(6); @(negedge clk); rst_n=1; idle(6); end
    endtask
    task frame(input integer n,input bit stalls,input integer tails);
        integer i; reg [31:0] r;
        begin
            tick(1,1,16'h1234);
            for(i=1;i<n;i=i+1) begin
                r=random_word(); if(stalls && r[2:0]==0) idle(1+(r[5:3]%5));
                tick(1,0,r[15:0]);
            end
            for(i=0;i<tails;i=i+1) tick(1,0,16'hffff);
            idle(40);
        end
    endtask
    integer i,k; reg [31:0] r;
    initial begin
        reset_all();
        frame(W*H,0,1); frame(W*H,1,0); frame(W*H,1,3);
        frame(W*H/2,1,0); frame(W*H,1,0);
        // Repeated coincident SOF+pixel0 fills the event FIFO naturally.
        for(i=0;i<200;i=i+1) tick(1,(i%2)==0,i);
        idle(40); frame(W*H,1,0);
        for(i=0;i<6000;i=i+1) begin
            r=random_word(); tick(r[0],r[7:2]==0,r[31:16]);
            if(i%997==0) reset_all();
        end
        // Carry boundaries include the original 19-bit full-resolution counter.
        for(k=1;k<$clog2(W*H+1);k=k+1) begin
            reset_all(); tick(1,1,1); idle(5);
            @(negedge clk);
            ref_dut.pixels=(32'h1<<k)-1; dut.pixels=(32'h1<<k)-1;
            tick(1,0,2); idle(8); boundaries=boundaries+1;
        end
        reset_all();
        @(negedge clk);
        ref_dut.source_sequence=32'hffffffff; dut.source_sequence=32'hffffffff;
        ref_dut.short_frame_count=32'hffffffff; dut.short_frame_count=32'hffffffff;
        ref_dut.overflow_count=32'hffffffff; dut.overflow_count=32'hffffffff;
        tick(1,1,1); idle(8);
        if(dut.source_sequence!==32'd0) $fatal(1,"sequence wrap");
        tick(1,1,1); idle(8);
        if(dut.short_frame_count!==32'd0) $fatal(1,"short count wrap");
        for(i=0;i<200;i=i+1) tick(1,(i%2)==0,i);
        idle(40);
        if(dut.overflow_count===32'hffffffff) $fatal(1,"overflow count did not advance");
        reset_all(); frame(W*H,1,1);
        if(records<6 || overflows==0 || shorts==0 || fires<6*W*H) $fatal(1,"missing coverage");
        $display("MOTION_TC04_PASS comparisons=%0d records=%0d fires=%0d overflows=%0d shorts=%0d boundaries=%0d",comparisons,records,fires,overflows,shorts,boundaries);
        $finish;
    end
    initial begin #100000000; $fatal(1,"timeout"); end
endmodule
