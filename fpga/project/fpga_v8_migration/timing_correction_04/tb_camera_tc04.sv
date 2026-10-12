`timescale 1ns/1ps
module tb_camera_tc04;
    GTP_GRS GRS_INST (.GRS_N(1'b1));
    parameter integer CAM_HALF=5, VIDEO_HALF=7, SEED=1;
    reg cam_clk=0, video_clk=0, cam_rst=0, video_rst=0;
    reg [15:0] s_data=0;
    reg s_valid=0, s_hsync=0, s_vsync=0;
    wire [15:0] a_data,b_data;
    wire a_valid,b_valid,a_hsync,b_hsync,a_vsync,b_vsync;
    wire [31:0] a_input,b_input,a_output,b_output,a_drop,b_drop,a_seq,b_seq;
`define PORTS(P) .cam_clk(cam_clk),.cam_rst(cam_rst),.video_clk(video_clk),.video_rst(video_rst),.s_data(s_data),.s_valid(s_valid),.s_hsync(s_hsync),.s_vsync(s_vsync),.video_data(P``_data),.video_valid(P``_valid),.video_hsync(P``_hsync),.video_vsync(P``_vsync),.dbg_cdc_input(P``_input),.dbg_cdc_output(P``_output),.dbg_cdc_drop(P``_drop),.dbg_cdc_seq(P``_seq)
    // Explicit frozen V5/TC03 reference and isolated TC04 binding.
    ov5640_cdc_tc03 #(.DATA_WIDTH(16)) reference_dut (`PORTS(a));
    ov5640_cdc_tc04 #(.DATA_WIDTH(16)) candidate_dut (`PORTS(b));
    always #CAM_HALF cam_clk=~cam_clk;
    always #VIDEO_HALF video_clk=~video_clk;
    integer comparisons=0, accepted=0, dropped=0, frames=0, reads=0, resets=0;
    integer boundary_cases=0, natural_count_carries=0, natural_drop_carries=0;
    integer i,k,n,seed_state;
    reg natural_phase=0;
    reg [31:0] expected_count,expected_drop;
    task compare;
        integer p;
        begin
            comparisons=comparisons+1;
            if ({a_data,a_valid,a_hsync,a_vsync,a_input,a_output,a_drop,a_seq} !==
                {b_data,b_valid,b_hsync,b_vsync,b_input,b_output,b_drop,b_seq})
                $fatal(1,"public output mismatch time=%0t",$time);
            if ({reference_dut.src_count,reference_dut.src_drop,reference_dut.src_snapshot,reference_dut.src_seq,reference_dut.src_toggle,reference_dut.src_vs_q} !==
                {candidate_dut.src_count,candidate_dut.src_drop,candidate_dut.src_snapshot,candidate_dut.src_seq,candidate_dut.src_toggle,candidate_dut.src_vs_q})
                $fatal(1,"source state mismatch time=%0t",$time);
            if ({reference_dut.wr_en,reference_dut.rd_en,reference_dut.full,reference_dut.empty} !==
                {candidate_dut.wr_en,candidate_dut.rd_en,candidate_dut.full,candidate_dut.empty})
                $fatal(1,"FIFO control mismatch time=%0t",$time);
            for(p=1;p<8;p=p+1) begin
                if (candidate_dut.count_prefix[p] !== ((candidate_dut.src_count & ((32'h1<<(p*4))-1)) == ((32'h1<<(p*4))-1)) ||
                    candidate_dut.drop_prefix[p] !== ((candidate_dut.src_drop & ((32'h1<<(p*4))-1)) == ((32'h1<<(p*4))-1)))
                    $fatal(1,"prefix invariant mismatch slice=%0d time=%0t",p,$time);
            end
        end
    endtask
    always @(posedge cam_clk) begin
        if (cam_rst) begin expected_count=0;expected_drop=0;end
        else if (s_vsync && !reference_dut.src_vs_q) begin
            expected_count={31'd0,s_valid};expected_drop={31'd0,(s_valid && reference_dut.full)};
            frames=frames+1;
        end else begin
            expected_count=reference_dut.src_count+(s_valid ? 32'd1:32'd0);
            expected_drop=reference_dut.src_drop+((s_valid && reference_dut.full) ? 32'd1:32'd0);
            if(natural_phase) begin
                if(s_valid && reference_dut.src_count[15:0]==16'hffff) natural_count_carries=natural_count_carries+1;
                if(s_valid && reference_dut.full && reference_dut.src_drop[15:0]==16'hffff) natural_drop_carries=natural_drop_carries+1;
            end
        end
        if (!cam_rst && s_valid) begin
            if (reference_dut.full) dropped=dropped+1; else accepted=accepted+1;
        end
        #1;compare();
        if (candidate_dut.src_count !== expected_count || candidate_dut.src_drop !== expected_drop)
            $fatal(1,"independent modulo counter oracle mismatch");
    end
    always @(posedge video_clk) begin
        if (!video_rst && reference_dut.rd_en) reads=reads+1;
        #1;compare();
    end
    always @(negedge cam_clk or negedge video_clk) begin #1;compare();end
    always @(posedge cam_rst) begin
        resets=resets+1;
        #1;compare();
        if ({candidate_dut.src_count,candidate_dut.src_drop,candidate_dut.src_snapshot,candidate_dut.src_seq,candidate_dut.src_toggle,candidate_dut.src_vs_q,candidate_dut.count_prefix,candidate_dut.drop_prefix} !== 0)
            $fatal(1,"asynchronous reset mismatch");
    end
    task reset_both;
        begin
            #2;cam_rst=1;video_rst=1;
            repeat(6) @(negedge cam_clk);
            cam_rst=0;
            repeat(6) @(negedge video_clk);
            video_rst=0;
        end
    endtask
    // Deposits include all prediction state, not FIFO state. Start BEFORE
    // each boundary to exercise predictor creation, stalls, carry and wrap.
    task boundary(input [31:0] value,input integer full_value,input integer frame_value);
        integer p,t;
        reg [31:0] deposited;
        begin
            @(negedge cam_clk);s_vsync=0;s_valid=0;
            repeat(2) @(negedge cam_clk);
            #2;deposited=value-2;
            reference_dut.src_count=deposited;candidate_dut.src_count=deposited;
            reference_dut.src_drop=deposited;candidate_dut.src_drop=deposited;
            for(p=1;p<8;p=p+1) begin
                candidate_dut.count_prefix[p]=((deposited & ((32'h1<<(p*4))-1)) == ((32'h1<<(p*4))-1));
                candidate_dut.drop_prefix[p]=candidate_dut.count_prefix[p];
            end
            force reference_dut.full=full_value;
            force candidate_dut.full=full_value;
            for(t=0;t<8;t=t+1) begin
                s_valid=(t!=2 && t!=4);s_vsync=(frame_value && t==5);
                @(posedge cam_clk);#2;compare();
                @(negedge cam_clk);
            end
            boundary_cases=boundary_cases+1;
            s_valid=0;s_vsync=0;
            release reference_dut.full;release candidate_dut.full;
        end
    endtask
    initial begin
        seed_state=SEED;k=$urandom(seed_state);
        reset_both();
        // Natural real-FIFO overflow, from reset, no force or deposits.
        @(negedge video_clk);video_rst=1;natural_phase=1;
        for(i=0;i<74000;i=i+1) begin
            @(negedge cam_clk);s_valid=(i%19!=18);s_data=i;s_hsync=1;s_vsync=(i==0);
        end
        @(negedge cam_clk);s_valid=0;s_vsync=0;s_hsync=0;natural_phase=0;
        if(natural_count_carries<1 || natural_drop_carries<1) $fatal(1,"natural 16-bit carry missing");
        @(negedge video_clk);video_rst=0;
        repeat(1500) @(negedge video_clk);
        if (dropped==0 || accepted==0 || reads==0) $fatal(1,"natural FIFO coverage missing");
        for(i=4;i<=32;i=i+4) begin
            boundary((64'h1<<i)-1,0,0);
            boundary((64'h1<<i)-1,1,0);
            boundary((64'h1<<i)-1,0,1);
            boundary((64'h1<<i)-1,1,1);
        end
        // First-frame override while OLD prefixes are all true.
        @(negedge cam_clk);s_valid=0;s_vsync=0;
        repeat(2) @(negedge cam_clk);
        #2;reference_dut.src_count=32'hffffffff;candidate_dut.src_count=32'hffffffff;
        reference_dut.src_drop=32'hffffffff;candidate_dut.src_drop=32'hffffffff;
        candidate_dut.count_prefix=7'h7f;candidate_dut.drop_prefix=7'h7f;
        force reference_dut.full=1;force candidate_dut.full=1;
        s_valid=1;s_vsync=1;
        @(posedge cam_clk);#2;compare();
        // Reset takes priority over simultaneous valid/frame/full, even
        // with every OLD predictor asserted. Assert reset before next edge.
        @(negedge cam_clk);s_valid=0;s_vsync=0;
        repeat(2) @(negedge cam_clk);
        #0.5;reference_dut.src_count=32'hffffffff;candidate_dut.src_count=32'hffffffff;
        reference_dut.src_drop=32'hffffffff;candidate_dut.src_drop=32'hffffffff;
        candidate_dut.count_prefix=7'h7f;candidate_dut.drop_prefix=7'h7f;
        s_valid=1;s_vsync=1;
        reset_both();
        release reference_dut.full;release candidate_dut.full;
        for(i=0;i<24000;i=i+1) begin
            @(negedge cam_clk);
            s_data=$urandom;s_valid=($urandom_range(0,7)!=0);
            s_hsync=$urandom_range(0,1);s_vsync=($urandom_range(0,63)==0);
            if(i==5000 || i==17000) reset_both();
        end
        @(negedge cam_clk);s_valid=0;s_vsync=1;
        repeat(40) @(negedge video_clk);
        if (frames<10 || resets<4 || boundary_cases!=32) $fatal(1,"coverage missing");
        if ($isunknown({a_input,a_output,a_drop,a_seq})) $fatal(1,"unknown debug outputs");
        $display("CAMERA_TC04_PASS seed=%0d cam_half=%0d video_half=%0d comparisons=%0d accepted=%0d dropped=%0d reads=%0d frames=%0d resets=%0d boundaries=%0d natural_count_carries=%0d natural_drop_carries=%0d",SEED,CAM_HALF,VIDEO_HALF,comparisons,accepted,dropped,reads,frames,resets,boundary_cases,natural_count_carries,natural_drop_carries);
        $finish;
    end
    initial begin #10000000;$fatal(1,"timeout");end
endmodule
