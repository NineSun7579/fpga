`timescale 1ns/1ps
module cdc_case #(parameter WIDTH=320, ID=0, SRC_MIN=2, DST_MIN=7)
    (output reg done=0);
    reg src_clk=0, dst_clk=0;
    reg src_rst=1, dst_rst=1, src_valid=0;
    reg [WIDTH-1:0] src_data=0;
    wire src_busy, dst_valid;
    wire [31:0] src_dropped_count;
    wire [WIDTH-1:0] dst_data;
    motion_result_cdc #(.WIDTH(WIDTH)) dut (.*);

    // Independent reproducible PRNG states for clocks and stimulus.
    reg [31:0] src_rng=32'h18345678+ID, dst_rng=32'h87345621+ID;
    reg [31:0] stim_rng=32'hbcd01234+ID;
    function automatic [31:0] step(input [31:0] x);
        reg [31:0] y;
        begin y=x^(x<<13); y=y^(y>>17); step=y^(y<<5); end
    endfunction
    initial forever begin
        src_rng=step(src_rng);
        #(SRC_MIN + src_rng%5 + 0.13) src_clk=~src_clk;
    end
    initial begin
        #(0.37+ID*0.19);
        forever begin
            dst_rng=step(dst_rng);
            #(DST_MIN + dst_rng%7 + 0.29) dst_clk=~dst_clk;
        end
    end

    reg [WIDTH-1:0] expected[$];
    reg [WIDTH-1:0] old_hold, old_out, wanted;
    reg old_req, old_valid, old_ack, was_busy, accepted;
    reg [31:0] drops=0;
    integer sent=0, received=0, rejected=0, resets=0;
    integer dst_edges=0, launch_edge=0, min_edges=100000, max_edges=0;

    always @(posedge src_rst) begin
        expected.delete(); drops=0; resets=resets+1;
    end
    always @(posedge src_clk) begin
        old_hold=dut.held_data; old_req=dut.req_toggle;
        was_busy=src_busy; accepted=!src_rst && src_valid && !src_busy;
        if (!src_rst && src_valid) begin
            if (src_busy) begin drops=drops+1; rejected=rejected+1; end
            else begin
                if (expected.size()!=0) $fatal(1,"case %0d multiple outstanding",ID);
                expected.push_back(src_data); sent=sent+1;
                launch_edge=dst_edges;
            end
        end
        #0.01;
        if (src_rst) begin
            drops=0;
            if (src_busy!==0 || src_dropped_count!==0 || dut.held_data!==0)
                $fatal(1,"case %0d source reset",ID);
        end else begin
            if (src_dropped_count!==drops) $fatal(1,"case %0d dropped count",ID);
            if (!accepted && (dut.held_data!==old_hold || dut.req_toggle!==old_req))
                $fatal(1,"case %0d held bus/request changed without acceptance",ID);
            if (was_busy && accepted) $fatal(1,"accepted while busy");
        end
    end

    always @(posedge dst_clk) begin
        dst_edges=dst_edges+1;
        old_out=dst_data; old_valid=dst_valid; old_ack=dut.ack_toggle;
        #0.02;
        if (dst_rst) begin
            if (dst_valid!==0 || dst_data!==0 || dut.ack_toggle!==0)
                $fatal(1,"case %0d destination reset",ID);
        end else if (dst_valid) begin
            if (old_valid) $fatal(1,"case %0d valid longer than one clock",ID);
            if (expected.size()!=1) $fatal(1,"case %0d unsolicited/duplicate delivery",ID);
            wanted=expected.pop_front();
            if (dst_data!==wanted) $fatal(1,"case %0d incoherent data got %h expected %h",ID,dst_data,wanted);
            if (dut.ack_toggle!==dut.req_toggle) $fatal(1,"ack not tied to captured request");
            if (dst_edges-launch_edge!=4) $fatal(1,"case %0d latency %0d edges",ID,dst_edges-launch_edge);
            if (dst_edges-launch_edge<min_edges) min_edges=dst_edges-launch_edge;
            if (dst_edges-launch_edge>max_edges) max_edges=dst_edges-launch_edge;
            received=received+1;
        end else begin
            if (dst_data!==old_out) $fatal(1,"case %0d output changed without valid",ID);
            if (dut.ack_toggle!==old_ack) $fatal(1,"case %0d acknowledgement before capture",ID);
        end
    end

    task automatic drive(input bit v);
        integer b;
        begin
            @(negedge src_clk);
            src_valid=v;
            for (b=0;b<WIDTH;b=b+1) begin
                stim_rng=step(stim_rng); src_data[b]=stim_rng[0];
            end
        end
    endtask
    task automatic drain;
        begin
            drive(0);
            wait (!src_busy);
            repeat (8) @(negedge dst_clk);
            if (expected.size()!=0) $fatal(1,"case %0d lost delivery",ID);
        end
    endtask
    task automatic reset_idle;
        begin
            @(negedge src_clk); src_rst=1; dst_rst=1; src_valid=0;
            #100;
            @(negedge src_clk); src_rst=0;
            @(negedge dst_clk); dst_rst=0;
            repeat (8) @(negedge dst_clk);
            if (src_busy || dst_valid || dst_data!==0 || src_dropped_count!==0)
                $fatal(1,"case %0d false activity after idle reset",ID);
        end
    endtask

    integer i, epoch;
    initial begin
        #100;
        @(negedge src_clk); src_rst=0;
        @(negedge dst_clk); dst_rst=0;
        repeat (8) @(negedge dst_clk);
        for (epoch=0;epoch<3;epoch=epoch+1) begin
            // Adjacent pulses must reject the second; then input changes while busy.
            drive(1); drive(1); drive(0); drain();
            for (i=0;i<1600;i=i+1) begin
                stim_rng=step(stim_rng);
                drive((stim_rng%4)!=0);
            end
            drain();
            if (epoch!=2) reset_idle();
        end
        if (sent!=received || rejected<100 || received<20)
            $fatal(1,"case %0d insufficient coverage sent=%0d received=%0d rejected=%0d",ID,sent,received,rejected);
        $display("CDC CASE PASS id=%0d width=%0d accepted=%0d delivered=%0d rejected=%0d idle_resets=%0d latency_dst_edges=%0d..%0d",ID,WIDTH,sent,received,rejected,resets,min_edges,max_edges);
        done=1;
    end
endmodule

module tb_motion_result_cdc;
    wire [2:0] done;
    cdc_case #(.WIDTH(320),.ID(0),.SRC_MIN(2),.DST_MIN(7)) a(done[0]);
    cdc_case #(.WIDTH(37),.ID(1),.SRC_MIN(9),.DST_MIN(2)) b(done[1]);
    cdc_case #(.WIDTH(1),.ID(2),.SRC_MIN(4),.DST_MIN(4)) c(done[2]);
    initial begin
        wait (&done);
        $display("PASS tb_motion_result_cdc: all widths, asynchronous clock ratios, drops, immutable held data, stable outputs, idle resets, exact delivery and latency");
        $finish;
    end
    initial begin #2000000; $fatal(1,"CDC test timeout"); end
endmodule
