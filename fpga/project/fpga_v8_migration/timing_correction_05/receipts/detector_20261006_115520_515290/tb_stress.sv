`timescale 1ns/1ps

module stress_case #(
    parameter W=21, H=13, STEP=4, BSX=2, BSY=2, PTH=16, BTH=2,
    parameter DEFAULT_CASE=0
) (output reg done=0);
    localparam SX=(W+STEP-1)/STEP, SY=(H+STEP-1)/STEP;
    localparam BX=(SX+BSX-1)/BSX, BY=(SY+BSY-1)/BSY;
    localparam NS=SX*SY, NB=BX*BY;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, frame_start=0, frame_end=0, pixel_valid=0;
    reg [15:0] pixel_rgb565=0;
    wire result_strobe, result_valid, bbox_valid;
    wire [NB-1:0] block_bitmap;
    wire [$clog2(NB+1)-1:0] changed_blocks;
    wire [$clog2(NS+1)-1:0] changed_samples;
    wire [((BX>1)?$clog2(BX):1)-1:0] bbox_min_x, bbox_max_x;
    wire [((BY>1)?$clog2(BY):1)-1:0] bbox_min_y, bbox_max_y;
    wire [31:0] frame_sequence;
    block_motion_detector_tc05 #(.WIDTH(W), .HEIGHT(H), .SAMPLE_STEP(STEP),
        .BLOCK_SAMPLES_X(BSX), .BLOCK_SAMPLES_Y(BSY),
        .PIXEL_THRESHOLD(PTH), .BLOCK_THRESHOLD(BTH)) dut (.*);

    wire ref_result_strobe, ref_result_valid, ref_bbox_valid;
    wire [NB-1:0] ref_block_bitmap;
    wire [$clog2(NB+1)-1:0] ref_changed_blocks;
    wire [$clog2(NS+1)-1:0] ref_changed_samples;
    wire [((BX>1)?$clog2(BX):1)-1:0] ref_bbox_min_x, ref_bbox_max_x;
    wire [((BY>1)?$clog2(BY):1)-1:0] ref_bbox_min_y, ref_bbox_max_y;
    wire [31:0] ref_frame_sequence;
    block_motion_detector #(.WIDTH(W),.HEIGHT(H),.SAMPLE_STEP(STEP),
        .BLOCK_SAMPLES_X(BSX),.BLOCK_SAMPLES_Y(BSY),
        .PIXEL_THRESHOLD(PTH),.BLOCK_THRESHOLD(BTH)) original (
        .result_strobe(ref_result_strobe),.result_valid(ref_result_valid),.bbox_valid(ref_bbox_valid),.block_bitmap(ref_block_bitmap),.changed_blocks(ref_changed_blocks),.changed_samples(ref_changed_samples),.bbox_min_x(ref_bbox_min_x),.bbox_max_x(ref_bbox_max_x),.bbox_min_y(ref_bbox_min_y),.bbox_max_y(ref_bbox_max_y),.frame_sequence(ref_frame_sequence),.clk(clk),.rst_n(rst_n),.frame_start(frame_start),.frame_end(frame_end),.pixel_valid(pixel_valid),.pixel_rgb565(pixel_rgb565));
    integer paired_cycles=0;
    always @(posedge clk) begin
        #2;
        if (rst_n) begin
            paired_cycles=paired_cycles+1;
            if ({result_strobe,result_valid,bbox_valid,block_bitmap,changed_blocks,changed_samples,bbox_min_x,bbox_max_x,bbox_min_y,bbox_max_y,frame_sequence} !== {ref_result_strobe,ref_result_valid,ref_bbox_valid,ref_block_bitmap,ref_changed_blocks,ref_changed_samples,ref_bbox_min_x,ref_bbox_max_x,ref_bbox_min_y,ref_bbox_max_y,ref_frame_sequence})
                $fatal(1,"TC01 original cycle mismatch W=%0d STEP=%0d cycle=%0d",W,STEP,paired_cycles);
        end
    end

    wire tc01_result_strobe, tc01_result_valid, tc01_bbox_valid;
    wire [NB-1:0] tc01_block_bitmap;
    wire [$clog2(NB+1)-1:0] tc01_changed_blocks;
    wire [$clog2(NS+1)-1:0] tc01_changed_samples;
    wire [((BX>1)?$clog2(BX):1)-1:0] tc01_bbox_min_x, tc01_bbox_max_x;
    wire [((BY>1)?$clog2(BY):1)-1:0] tc01_bbox_min_y, tc01_bbox_max_y;
    wire [31:0] tc01_frame_sequence;
    block_motion_detector_tc01 #(.WIDTH(W),.HEIGHT(H),.SAMPLE_STEP(STEP),
        .BLOCK_SAMPLES_X(BSX),.BLOCK_SAMPLES_Y(BSY),
        .PIXEL_THRESHOLD(PTH),.BLOCK_THRESHOLD(BTH)) tc01_original (
        .result_strobe(tc01_result_strobe),.result_valid(tc01_result_valid),.bbox_valid(tc01_bbox_valid),.block_bitmap(tc01_block_bitmap),.changed_blocks(tc01_changed_blocks),.changed_samples(tc01_changed_samples),.bbox_min_x(tc01_bbox_min_x),.bbox_max_x(tc01_bbox_max_x),.bbox_min_y(tc01_bbox_min_y),.bbox_max_y(tc01_bbox_max_y),.frame_sequence(tc01_frame_sequence),.clk(clk),.rst_n(rst_n),.frame_start(frame_start),.frame_end(frame_end),.pixel_valid(pixel_valid),.pixel_rgb565(pixel_rgb565));
    integer tc01_cycles=0;
    always @(posedge clk) begin
        #2;
        if (rst_n) begin
            tc01_cycles=tc01_cycles+1;
            if ({result_strobe,result_valid,bbox_valid,block_bitmap,changed_blocks,changed_samples,bbox_min_x,bbox_max_x,bbox_min_y,bbox_max_y,frame_sequence} !== {tc01_result_strobe,tc01_result_valid,tc01_bbox_valid,tc01_block_bitmap,tc01_changed_blocks,tc01_changed_samples,tc01_bbox_min_x,tc01_bbox_max_x,tc01_bbox_min_y,tc01_bbox_max_y,tc01_frame_sequence})
                $fatal(1,"TC01 original cycle mismatch W=%0d STEP=%0d cycle=%0d",W,STEP,tc01_cycles);
        end
    end

    wire tc03_result_strobe, tc03_result_valid, tc03_bbox_valid;
    wire [NB-1:0] tc03_block_bitmap;
    wire [$clog2(NB+1)-1:0] tc03_changed_blocks;
    wire [$clog2(NS+1)-1:0] tc03_changed_samples;
    wire [((BX>1)?$clog2(BX):1)-1:0] tc03_bbox_min_x, tc03_bbox_max_x;
    wire [((BY>1)?$clog2(BY):1)-1:0] tc03_bbox_min_y, tc03_bbox_max_y;
    wire [31:0] tc03_frame_sequence;
    block_motion_detector_tc03 #(.WIDTH(W),.HEIGHT(H),.SAMPLE_STEP(STEP),
        .BLOCK_SAMPLES_X(BSX),.BLOCK_SAMPLES_Y(BSY),
        .PIXEL_THRESHOLD(PTH),.BLOCK_THRESHOLD(BTH)) tc03_original (
        .result_strobe(tc03_result_strobe),.result_valid(tc03_result_valid),.bbox_valid(tc03_bbox_valid),.block_bitmap(tc03_block_bitmap),.changed_blocks(tc03_changed_blocks),.changed_samples(tc03_changed_samples),.bbox_min_x(tc03_bbox_min_x),.bbox_max_x(tc03_bbox_max_x),.bbox_min_y(tc03_bbox_min_y),.bbox_max_y(tc03_bbox_max_y),.frame_sequence(tc03_frame_sequence),.clk(clk),.rst_n(rst_n),.frame_start(frame_start),.frame_end(frame_end),.pixel_valid(pixel_valid),.pixel_rgb565(pixel_rgb565));
    integer tc03_cycles=0;
    always @(posedge clk) begin
        #2;
        if (rst_n) begin
            tc03_cycles=tc03_cycles+1;
            if ({result_strobe,result_valid,bbox_valid,block_bitmap,changed_blocks,changed_samples,bbox_min_x,bbox_max_x,bbox_min_y,bbox_max_y,frame_sequence} !== {tc03_result_strobe,tc03_result_valid,tc03_bbox_valid,tc03_block_bitmap,tc03_changed_blocks,tc03_changed_samples,tc03_bbox_min_x,tc03_bbox_max_x,tc03_bbox_min_y,tc03_bbox_max_y,tc03_frame_sequence})
                $fatal(1,"TC01 original cycle mismatch W=%0d STEP=%0d cycle=%0d",W,STEP,tc03_cycles);
        end
    end


    integer history_checks=0, history_writes=0, history_resets=0;
    integer history_index, written_address;
    reg did_write;
    always @(posedge clk) begin
        did_write=dut.rst_n && dut.accept_sample;
        written_address=dut.sample_address;

        if ({dut.rst_n && dut.accept_sample,dut.sample_address,dut.luma} !==
            {original.rst_n && original.accept_sample,original.sample_address,original.luma})
            $fatal(1,"TC05 history transaction differs from original");

        if ({dut.rst_n && dut.accept_sample,dut.sample_address,dut.luma} !==
            {tc01_original.rst_n && tc01_original.accept_sample,tc01_original.sample_address,tc01_original.luma})
            $fatal(1,"TC05 history transaction differs from tc01_original");

        if ({dut.rst_n && dut.accept_sample,dut.sample_address,dut.luma} !==
            {tc03_original.rst_n && tc03_original.accept_sample,tc03_original.sample_address,tc03_original.luma})
            $fatal(1,"TC05 history transaction differs from tc03_original");

        #2;
        history_checks=history_checks+1;
        if (!dut.rst_n) history_resets=history_resets+1;
        if (dut.history_eligible !== (dut.active &&
            dut.pixel_count<dut.TOTAL_PIXELS &&
            (dut.x%dut.SAMPLE_STEP)==0 && (dut.y%dut.SAMPLE_STEP)==0))
            $fatal(1,"TC05 lookahead invariant");
        if (did_write) history_writes=history_writes+1;

        if ({dut.result_strobe,dut.result_valid,dut.bbox_valid,dut.block_bitmap,dut.changed_blocks,dut.changed_samples,dut.bbox_min_x,dut.bbox_max_x,dut.bbox_min_y,dut.bbox_max_y,dut.frame_sequence} !== {original.result_strobe,original.result_valid,original.bbox_valid,original.block_bitmap,original.changed_blocks,original.changed_samples,original.bbox_min_x,original.bbox_max_x,original.bbox_min_y,original.bbox_max_y,original.frame_sequence})
            $fatal(1,"TC05 public output mismatch vs original");
        if (dut.history_q !== original.history_q)
            $fatal(1,"TC05 read-first history_q mismatch vs original");
        if (did_write && dut.history[written_address] !== original.history[written_address])
            $fatal(1,"TC05 written history byte mismatch vs original");
        if (dut.frame_start || dut.frame_end || !dut.rst_n) begin
            for (history_index=0;history_index<NS;history_index=history_index+1)
                if (dut.history[history_index] !== original.history[history_index])
                    $fatal(1,"TC05 retained history mismatch vs original");
        end

        if ({dut.result_strobe,dut.result_valid,dut.bbox_valid,dut.block_bitmap,dut.changed_blocks,dut.changed_samples,dut.bbox_min_x,dut.bbox_max_x,dut.bbox_min_y,dut.bbox_max_y,dut.frame_sequence} !== {tc01_original.result_strobe,tc01_original.result_valid,tc01_original.bbox_valid,tc01_original.block_bitmap,tc01_original.changed_blocks,tc01_original.changed_samples,tc01_original.bbox_min_x,tc01_original.bbox_max_x,tc01_original.bbox_min_y,tc01_original.bbox_max_y,tc01_original.frame_sequence})
            $fatal(1,"TC05 public output mismatch vs tc01_original");
        if (dut.history_q !== tc01_original.history_q)
            $fatal(1,"TC05 read-first history_q mismatch vs tc01_original");
        if (did_write && dut.history[written_address] !== tc01_original.history[written_address])
            $fatal(1,"TC05 written history byte mismatch vs tc01_original");
        if (dut.frame_start || dut.frame_end || !dut.rst_n) begin
            for (history_index=0;history_index<NS;history_index=history_index+1)
                if (dut.history[history_index] !== tc01_original.history[history_index])
                    $fatal(1,"TC05 retained history mismatch vs tc01_original");
        end

        if ({dut.result_strobe,dut.result_valid,dut.bbox_valid,dut.block_bitmap,dut.changed_blocks,dut.changed_samples,dut.bbox_min_x,dut.bbox_max_x,dut.bbox_min_y,dut.bbox_max_y,dut.frame_sequence} !== {tc03_original.result_strobe,tc03_original.result_valid,tc03_original.bbox_valid,tc03_original.block_bitmap,tc03_original.changed_blocks,tc03_original.changed_samples,tc03_original.bbox_min_x,tc03_original.bbox_max_x,tc03_original.bbox_min_y,tc03_original.bbox_max_y,tc03_original.frame_sequence})
            $fatal(1,"TC05 public output mismatch vs tc03_original");
        if (dut.history_q !== tc03_original.history_q)
            $fatal(1,"TC05 read-first history_q mismatch vs tc03_original");
        if (did_write && dut.history[written_address] !== tc03_original.history[written_address])
            $fatal(1,"TC05 written history byte mismatch vs tc03_original");
        if (dut.frame_start || dut.frame_end || !dut.rst_n) begin
            for (history_index=0;history_index<NS;history_index=history_index+1)
                if (dut.history[history_index] !== tc03_original.history[history_index])
                    $fatal(1,"TC05 retained history mismatch vs tc03_original");
        end
    end


    reg [31:0] rng=32'h5c050001+W*17+H*3+STEP;
    function [31:0] random_word;
        begin rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5); random_word=rng; end
    endfunction
    task drive(input bit fs, fe, pv, input [15:0] color);
        begin @(negedge clk); frame_start=fs; frame_end=fe; pixel_valid=pv; pixel_rgb565=color;
            @(posedge clk); #3; end
    endtask
    integer k,j,f; reg [31:0] r;
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        // Dense consecutive samples, row transitions, exact limit and excess tails.
        for(f=0;f<4;f=f+1) begin
            drive(1,f[0],1,16'hdead);
            for(j=0;j<W*H;j=j+1) begin
                r=random_word(); if(f[1] && r[1:0]==0) drive(0,0,0,16'hffff);
                drive(0,0,1,r[15:0]);
            end
            repeat(3) drive(0,0,1,16'hbeef);
            drive(0,1,1,16'hffff); drive(1,0,1,16'hdead);
        end
        // Reset at every position near accepted samples/end/publication.
        for(k=0;k<8;k=k+1) begin
            drive(1,0,1,0);
            for(j=0;j<W*H;j=j+1) drive(0,0,1,j);
            drive(0,1,1,0);
            for(j=0;j<k;j=j+1) drive(0,0,1,j);
            @(negedge clk); #1; rst_n=0; #1;
            if(dut.history_eligible!==0 || dut.result_strobe!==0) $fatal(1,"async reset");
            drive(1,1,1,16'hffff); @(negedge clk); #1; rst_n=1;
        end
        for(k=0;k<24000;k=k+1) begin
            r=random_word();
            // Exhaust every marker/valid combination, then mostly pixels with sparse markers.
            if(k%64<8) drive(k[2],k[1],k[0],r[15:0]);
            else drive(r[12:8]==0,r[17:13]==0,r[0],r[31:16]);
            if(k%997==0) begin @(negedge clk); #1; rst_n=0; #1; @(negedge clk); #1; rst_n=1; end
        end
        #3; $display("TC05_STRESS W=%0d H=%0d STEP=%0d checks=%0d writes=%0d resets=%0d",W,H,STEP,history_checks,history_writes,history_resets);
        done=1;
    end
endmodule
module tb_stress;
    wire [7:0] done;
    stress_case #(.W(5),.H(3),.STEP(1)) a(done[0]);
    stress_case #(.W(1),.H(1),.STEP(1),.BSX(1),.BSY(1),.BTH(1)) b(done[1]);
    stress_case #(.W(7),.H(5),.STEP(3)) c(done[2]);
    stress_case #(.W(1),.H(7),.STEP(2)) d(done[3]);
    stress_case #(.W(9),.H(1),.STEP(2)) e(done[4]);
    stress_case #(.W(3),.H(2),.STEP(5)) f(done[5]);
    stress_case #(.W(16),.H(8),.STEP(4)) g(done[6]);
    stress_case #(.W(17),.H(11),.STEP(3),.BTH(1)) h(done[7]);
    initial begin wait(&done); $display("PASS TC05 STRESS ALL"); $finish; end
    initial begin #10000000; $fatal(1,"stress timeout"); end
endmodule
