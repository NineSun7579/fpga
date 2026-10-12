`timescale 1ns/1ps

module motion_case #(
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
    block_motion_detector_tc01 #(.WIDTH(W), .HEIGHT(H), .SAMPLE_STEP(STEP),
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

    reg [15:0] image [0:W*H-1];
    integer reference [0:NS-1];
    integer hits [0:NB-1];
    bit reference_ok=0;
    reg [NB-1:0] expected_bitmap;
    integer expected_samples, expected_blocks;
    integer expected_min_x, expected_max_x, expected_min_y, expected_max_y;
    integer expected_sequence=0, publications=0, ticks=0;
    bit expected_valid, expected_bbox;
    bit last_published_valid;
    // Wide zero-extension gives a simple whole-payload stability assertion.
    reg [NB+256-1:0] previous_payload=0;
    wire [NB+256-1:0] payload = {block_bitmap, changed_blocks, changed_samples,
        bbox_valid, bbox_min_x, bbox_max_x, bbox_min_y, bbox_max_y, frame_sequence};

    function automatic integer gray(input reg [15:0] color);
        integer r,g,b;
        begin
            r=(color[15:11]*8)+(color[15:13]);
            g=(color[10:5]*4)+(color[10:9]);
            b=(color[4:0]*8)+(color[4:2]);
            gray=(r+2*g+b)/4;
        end
    endfunction

    task automatic tick(input bit fs, fe, pv, input reg [15:0] color,
                        input bit expect_publish);
        integer j;
        begin
            @(negedge clk);
            frame_start=fs; frame_end=fe; pixel_valid=pv; pixel_rgb565=color;
            @(posedge clk); #1;
            ticks=ticks+1;
            if (result_strobe !== expect_publish)
                $fatal(1,"W=%0d STEP=%0d tick=%0d publication timing: got %b expected %b",
                       W,STEP,ticks,result_strobe,expect_publish);
            if (expect_publish) begin
                last_published_valid=result_valid;
                publications=publications+1;
                if (result_valid !== expected_valid || block_bitmap !== expected_bitmap ||
                    changed_samples !== expected_samples || changed_blocks !== expected_blocks ||
                    bbox_valid !== expected_bbox || bbox_min_x !== expected_min_x ||
                    bbox_max_x !== expected_max_x || bbox_min_y !== expected_min_y ||
                    bbox_max_y !== expected_max_y || frame_sequence !== expected_sequence)
                    $fatal(1,"W=%0d STEP=%0d seq=%0d got valid=%b map=%h samples=%0d blocks=%0d bbox=%b:(%0d,%0d)-(%0d,%0d); expected valid=%b map=%h samples=%0d blocks=%0d bbox=%b:(%0d,%0d)-(%0d,%0d)",
                        W,STEP,frame_sequence,result_valid,block_bitmap,changed_samples,changed_blocks,
                        bbox_valid,bbox_min_x,bbox_min_y,bbox_max_x,bbox_max_y,
                        expected_valid,expected_bitmap,expected_samples,expected_blocks,
                        expected_bbox,expected_min_x,expected_min_y,expected_max_x,expected_max_y);
            end else begin
                if (result_valid !== 0) $fatal(1,"result_valid is not a publication pulse");
                if (payload !== previous_payload) $fatal(1,"Published fields changed without strobe");
            end
            // Check the complete history at end, before a legal next frame
            // can overwrite address zero on the delayed publication edge.
            if (fe && !fs && dut.end_pending) begin
                for (j=0;j<NS;j=j+1)
                    if (dut.history[j] !== reference[j][7:0])
                        $fatal(1,"History mismatch W=%0d sample=%0d (dummy/address overwrite)",W,j);
            end
            previous_payload=payload;
        end
    endtask

    task automatic build(input integer mode);
        integer px,py,sx,sy,local_index;
        begin
            for (py=0;py<H;py=py+1) for (px=0;px<W;px=px+1) begin
                sx=px/STEP; sy=py/STEP;
                local_index=(sy%BSY)*BSX+(sx%BSX);
                image[py*W+px]=16'h0000;
                case (mode)
                    1: image[py*W+px]=16'hffff;
                    2: if (sx/BSX==BX-1 && sy/BSY==BY-1) image[py*W+px]=16'hffff;
                    3: if (px%STEP!=0 || py%STEP!=0) image[py*W+px]=16'hffff;
                    10: if (sx/BSX==0 && sy/BSY==0 && local_index<BTH-1)
                            image[py*W+px]=16'h0100; // green 8 => luma 16
                    11: if (sx/BSX==0 && sy/BSY==0 && local_index<BTH)
                            image[py*W+px]=16'h0100;
                    12: image[py*W+px]=16'h00e0; // green 7 => luma 14
                    13: image[py*W+px]=16'h0100;
                    14: case ((px+3*py)%5)
                            0: image[py*W+px]=16'hf800;
                            1: image[py*W+px]=16'h07e0;
                            2: image[py*W+px]=16'h001f;
                            3: image[py*W+px]=16'h8410;
                            4: image[py*W+px]=16'hffff;
                        endcase
                    // Attainable RGB565 lumas 18,33,34,35: exact 15/16/17
                    // differences from a common reference (not from black).
                    15: image[py*W+px]=16'h0009;
                    16: image[py*W+px]=16'h0010;
                    17: image[py*W+px]=16'h004f;
                    18: image[py*W+px]=16'h0011;
                    20: if (px%STEP==0 && py==0 && sx<8)
                            image[py*W+px]=16'hffff;
                    21: if (px%STEP==0 && py==0 && sx<7)
                            image[py*W+px]=16'hffff;
                    22: if (px%STEP==0 && py==0 &&
                            (sx<4 || (sx>=BSX && sx<BSX+4)))
                            image[py*W+px]=16'hffff;
                    23: if (px%STEP==0 && py%STEP==0 &&
                            ((sy==(BY-1)*BSY && sx>=(BX-1)*BSX &&
                              sx<(BX-1)*BSX+7) || (sx==SX-1 && sy==SY-1)))
                            image[py*W+px]=16'hffff;
                endcase
            end
        end
    endtask

    // These explicit oracles do not derive their answers from gray(), hits[],
    // reference[] or score_complete(). Data remain stable after the valid pulse.
    task automatic literal_check(input string label, input bit valid,
        input integer samples, blocks, input reg [NB-1:0] bitmap,
        input integer minx, miny, maxx, maxy);
        begin
            if (last_published_valid !== valid || changed_samples !== samples ||
                changed_blocks !== blocks || block_bitmap !== bitmap ||
                bbox_valid !== (blocks!=0) || bbox_min_x !== minx ||
                bbox_min_y !== miny || bbox_max_x !== maxx || bbox_max_y !== maxy)
                $fatal(1,"Literal oracle failed: %s seq=%0d samples=%0d blocks=%0d map=%h",
                       label,frame_sequence,changed_samples,changed_blocks,block_bitmap);
            $display("PASS literal %s seq=%0d valid=%b samples=%0d blocks=%0d map=%h bbox=%b:(%0d,%0d)-(%0d,%0d)",
                label,frame_sequence,last_published_valid,changed_samples,changed_blocks,
                block_bitmap,bbox_valid,bbox_min_x,bbox_min_y,bbox_max_x,bbox_max_y);
        end
    endtask

    // Golden model operates in frame space, not the DUT clock pipeline.
    task automatic score_complete;
        integer px,py,j,index,delta,value,b;
        begin
            expected_bitmap=0; expected_samples=0; expected_blocks=0;
            expected_bbox=0;
            expected_min_x=0; expected_max_x=0; expected_min_y=0; expected_max_y=0;
            expected_valid=reference_ok;
            for (j=0;j<NB;j=j+1) hits[j]=0;
            index=0;
            for (py=0;py<H;py=py+STEP) for (px=0;px<W;px=px+STEP) begin
                value=gray(image[py*W+px]);
                delta=value-reference[index]; if (delta<0) delta=-delta;
                if (reference_ok && delta>=PTH) begin
                    expected_samples=expected_samples+1;
                    b=(py/STEP/BSY)*BX+(px/STEP/BSX);
                    hits[b]=hits[b]+1;
                end
                reference[index]=value;
                index=index+1;
            end
            for (j=0;j<NB;j=j+1) if (hits[j]>=BTH) begin
                expected_bitmap[j]=1;
                expected_blocks=expected_blocks+1;
                if (!expected_bbox || j%BX<expected_min_x) expected_min_x=j%BX;
                if (!expected_bbox || j%BX>expected_max_x) expected_max_x=j%BX;
                if (!expected_bbox || j/BX<expected_min_y) expected_min_y=j/BX;
                if (!expected_bbox || j/BX>expected_max_y) expected_max_y=j/BX;
                expected_bbox=1;
            end
            reference_ok=1;
            expected_sequence=expected_sequence+1;
        end
    endtask

    task automatic send_pixels(input integer count, input bit gaps);
        integer i;
        begin
            for (i=0;i<count;i=i+1) begin
                if (gaps && (i%7==0 || i%W==W-1)) begin
                    tick(0,0,0,16'hffff,0);
                    if (i%W==W-1) tick(0,0,0,16'hffff,0);
                end
                tick(0,0,1,image[i],0);
            end
        end
    endtask

    task automatic full_frame(input integer mode, input bit gaps, input integer tails);
        integer j;
        begin
            build(mode);
            tick(1,0,1,16'hdead,0); // marker pixel must be ignored
            send_pixels(W*H,gaps);
            for (j=0;j<tails;j=j+1) tick(0,0,1,16'hf81f,0);
            score_complete;
            tick(0,1,1,16'hffff,0); // end-edge dummy must be ignored
            tick(0,0,0,0,0); // final registered decision commits
            tick(0,0,0,0,1);
            tick(0,0,1,16'hffff,0); // valid outside frame is ignored
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        @(negedge clk); rst_n=1;
        tick(0,1,1,16'hffff,0); // stray end
        if (DEFAULT_CASE) begin
            // Exactly the six-frame 640x480 oracle requested by review.
            full_frame(0,0,0);
            literal_check("640 oracle 1 black seed",0,0,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 oracle 2 black static",1,0,0,192'b0,0,0,0,0);
            full_frame(20,0,0);
            literal_check("640 oracle 3 eight white block0",1,8,1,192'b1,0,0,0,0);
            full_frame(20,0,0);
            literal_check("640 oracle 4 same eight static",1,0,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 oracle 5 black removes eight",1,8,1,192'b1,0,0,0,0);
            full_frame(1,0,0);
            literal_check("640 oracle 6 all white",1,19200,192,{192{1'b1}},0,0,15,11);
            if (frame_sequence !== 32'd6) $fatal(1,"Six-frame oracle sequence failed");

            full_frame(1,1,2);
            literal_check("640 static white with gaps/dummies",1,0,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 uniform falling all samples",1,19200,192,{192{1'b1}},0,0,15,11);
            full_frame(21,0,0);
            literal_check("640 seven hits below block threshold",1,7,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 seven falling hits below threshold",1,7,0,192'b0,0,0,0,0);
            full_frame(22,1,0);
            literal_check("640 eight hits split four plus four blocks0/1",1,8,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 split four plus four falling",1,8,0,192'b0,0,0,0,0);

            // Last sampled coordinate is (636,476). The seven earlier hits
            // are (600..624 step4,440), all in block191. The eighth must mark it.
            full_frame(23,0,0);
            literal_check("640 final eighth rising at raw(636,476), no tail",1,8,1,
                          {1'b1,{191{1'b0}}},15,11,15,11);
            full_frame(0,1,3);
            literal_check("640 final eighth falling at raw(636,476), gaps/tails",1,8,1,
                          {1'b1,{191{1'b0}}},15,11,15,11);
            full_frame(3,1,3);
            literal_check("640 unsampled-only changes",1,0,0,192'b0,0,0,0,0);
            full_frame(0,0,0);
            literal_check("640 unsampled-only falling changes",1,0,0,192'b0,0,0,0,0);
        end else begin
        full_frame(0,1,3); // seed
        full_frame(0,0,0); // static
        full_frame(1,0,2); // rising difference, all blocks
        full_frame(1,1,0); // static white
        full_frame(0,0,0); // falling difference
        full_frame(2,1,4); // localized bottom/right edge block
        full_frame(0,0,0);
        end
        if (!DEFAULT_CASE) begin
            full_frame(3,1,3); // only unsampled pixels change
            full_frame(0,0,0);
            full_frame(10,0,0); // block threshold minus one
            full_frame(0,0,0);
            full_frame(11,1,0); // exact block and pixel thresholds
            full_frame(0,0,0);
            full_frame(12,0,0); // below pixel threshold
            full_frame(0,0,0);
            full_frame(13,0,0); // exact pixel threshold throughout
            full_frame(14,1,2); // RGB bit replication, varied adjacent samples
            full_frame(14,0,0); // static RGB: verifies correct previous address

            // The 1x1 configuration gives independent literal answers for
            // exact differences in both directions, with BTH=1 and PTH=16.
            if (W==1 && H==1 && STEP==1 && BTH==1 && PTH==16) begin
                if (gray(16'h0009)!=18 || gray(16'h0010)!=33 ||
                    gray(16'h004f)!=34 || gray(16'h0011)!=35)
                    $fatal(1,"Exact luma boundary color constants invalid");
                full_frame(15,0,0); // common reference: blue9 => luma18
                full_frame(16,0,0);
                literal_check("luma difference +15 (18 to 33)",1,0,0,1'b0,0,0,0,0);
                full_frame(15,0,0);
                literal_check("luma difference -15 (33 to 18)",1,0,0,1'b0,0,0,0,0);
                full_frame(17,0,0);
                literal_check("luma difference +16 (18 to 34)",1,1,1,1'b1,0,0,0,0);
                full_frame(15,0,0);
                literal_check("luma difference -16 (34 to 18)",1,1,1,1'b1,0,0,0,0);
                full_frame(18,0,0);
                literal_check("luma difference +17 (18 to 35)",1,1,1,1'b1,0,0,0,0);
                full_frame(15,0,0);
                literal_check("luma difference -17 (35 to 18)",1,1,1,1'b1,0,0,0,0);
            end

            // Short frame explicitly ended: no publication, reference invalid.
            build(1); tick(1,0,0,0,0); send_pixels(W*H-1,1);
            tick(0,1,0,0,0); tick(0,0,0,0,0); reference_ok=0;
            full_frame(14,1,3); // reseed
            full_frame(14,0,0); // comparison recovered

            // Restart immediately after a pending sample: discard old pipeline.
            build(1); tick(1,0,0,0,0); send_pixels(1,0); reference_ok=0;
            full_frame(0,0,2); full_frame(0,0,0);

            // A complete pixel stream without end is still an aborted frame.
            build(1); tick(1,0,0,0,0); send_pixels(W*H,0); reference_ok=0;
            full_frame(14,0,1); full_frame(14,0,0);

            // Earliest legal next start precedes publication. The old final
            // sample must commit before clear, even for dense and 1x1 frames.
            build(0); tick(1,0,0,0,0); send_pixels(W*H,0); score_complete;
            tick(0,1,0,0,0); tick(1,0,1,16'hffff,0);
            build(1);
            tick(0,0,1,image[0],1); // new first pixel coincides with old publish
            begin : remaining_pixels
                integer k;
                for (k=1;k<W*H;k=k+1) tick(0,0,1,image[k],0);
            end
            score_complete;
            tick(0,1,0,0,0); tick(0,0,0,0,0);
            tick(0,0,0,0,1); tick(0,0,0,0,0);

            // Reset populated history; the next complete frame must seed.
            @(negedge clk); rst_n=0;
            @(posedge clk); #1;
            if (payload !== 0 || result_strobe !== 0 || result_valid !== 0)
                $fatal(1,"Reset outputs failed");
            previous_payload=0; reference_ok=0; expected_sequence=0;
            @(negedge clk); rst_n=1;
            full_frame(14,0,3); full_frame(14,0,0);
        end
        $display("PASS motion W=%0d H=%0d STEP=%0d blocks=%0dx%0d publications=%0d cycles=%0d",
                 W,H,STEP,BX,BY,publications,ticks);
        done=1;
    end
endmodule

module tb_block_motion_detector;
    reg success=0;
    wire done_sparse, done_dense, done_single, done_default, done_packed;
    motion_case sparse(done_sparse);
    motion_case #(.W(5),.H(3),.STEP(1)) dense(done_dense);
    motion_case #(.W(1),.H(1),.STEP(1),.BSX(1),.BSY(1),.BTH(1)) single(done_single);
    motion_case #(.W(640),.H(480),.STEP(4),.BSX(10),.BSY(10),.BTH(8),.DEFAULT_CASE(1))
        defaults(done_default);
    // Direct core invocation retains packed dimensions up to the DUT boundary.
    motion_case #(.W(11'd640),.H(11'd480),.STEP(4),.BSX(10),.BSY(10),.BTH(8),.DEFAULT_CASE(1))
        packed_dimensions(done_packed);
    initial begin
        if ($bits(packed_dimensions.dut.WIDTH)!=32 ||
            $bits(packed_dimensions.dut.HEIGHT)!=32 ||
            packed_dimensions.dut.TOTAL_PIXELS!=307200 ||
            $bits(packed_dimensions.dut.pixel_count)!=19 ||
            packed_dimensions.dut.TOTAL_SAMPLES!=19200 ||
            packed_dimensions.dut.TOTAL_BLOCKS!=192)
            $fatal(1,"direct core packed 11-bit geometry truncated");
    end
    initial begin
        wait(done_sparse && done_dense && done_single && done_default && done_packed);
        success=1;
        $display("PASS ALL block_motion_detector self-checks");
        $finish;
    end
    initial begin
        #100000000;
        $fatal(1,"Simulation timeout");
    end
endmodule
