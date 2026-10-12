`timescale 1ns/1ps
module tb_cam6;
    parameter LEN=38400, SEED=1;
    reg clk=0, rst=1, abort_dma=0, done_dma=0, cam_en=1;
    reg valid=0, hs=0, vs=0, ready=0, cmd_ready=0;
    reg [15:0] data=0;
    reg [1:0] ack=0;
    reg [31:0] base1=32'h01c00000, base2=32'h01e00000;
    reg [$clog2(LEN):0] dynamic_len=LEN;
    always #5 clk=~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    wire [15:0] available[0:1];
    wire [127:0] payload[0:1];
    wire dv[0:1], last[0:1], cv[0:1], ar[0:1];
    wire [31:0] addr[0:1], len[0:1], prev[0:1], fault[0:1], rejects[0:1], pixels[0:1];
    wire [31:0] cnt[0:1], num[0:1], zdin[0:1], zout[0:1], state[0:1], lc[0:1], wc[0:1];
    wire [1:0] req[0:1];
`define PORTS(N) \
    .axi_clk(clk),.axi_rst(rst),.dma_abort(abort_dma),.dma_abort_req(ar[N]),.dma_done(done_dma), \
    .axi_data_available(available[N]),.axi_cam_en(cam_en), \
    .cam_data_addr_1(base1),.cam_data_addr_2(base2),.cam_data_len(dynamic_len), \
    .s_data(data),.s_data_valid(valid),.s_hsync(hs),.s_vsync(vs), \
    .axi_data(payload[N]),.axi_data_valid(dv[N]),.axi_data_last(last[N]),.axi_data_ready(ready), \
    .axi_cmd_addr(addr[N]),.axi_cmd_len(len[N]),.axi_cmd_valid(cv[N]),.axi_cmd_ready(cmd_ready), \
    .xdma_req(req[N]),.xdma_ack(ack),.prev_frame_base(prev[N]), \
    .dbg_fault_snapshot(fault[N]),.dbg_reject_counts(rejects[N]),.dbg_input_pixels(pixels[N]), \
    .dbg_axi_cnt(cnt[N]),.dbg_axi_num(num[N]),.dbg_zdin(zdin[N]),.dbg_zout(zout[N]), \
    .dbg_state(state[N]),.dbg_last_cnt(lc[N]),.dbg_wd_cnt(wc[N])
    ov5640_ddr #(.CAM_DATA_LEN(LEN)) ref_dut(`PORTS(0));
    ov5640_ddr_tc04 #(.CAM_DATA_LEN(LEN)) dut(`PORTS(1));
`undef PORTS
    wire [565:0] outputs[0:1];
    genvar g;
    generate for(g=0;g<2;g=g+1) begin
        assign outputs[g]={available[g],payload[g],dv[g],last[g],addr[g],len[g],cv[g],ar[g],
            req[g],prev[g],fault[g],rejects[g],pixels[g],cnt[g],num[g],zdin[g],zout[g],state[g],lc[g],wc[g]};
    end endgenerate
    reg [31:0] rng=SEED;
    function [31:0] random_word;
        begin rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5); random_word=rng; end
    endfunction
    integer comparisons=0, admissions=0, complete=0, overflows=0, publications=0, beats=0;
    integer boundaries=0, dynamic_cases=0, stalls=0, zero_rejects=0, short_faults=0;
    integer remaining=0;
    reg pending_done=0, auto_sink=1, stall_sink=0, stall_cmd=0;
    always @(negedge clk) begin
        if(auto_sink) begin
            ready=!stall_sink && ((random_word()&7)!=0);
            cmd_ready=!stall_cmd && ((random_word()&3)!=0);
            done_dma=pending_done; pending_done=0;
        end
    end
    always @(posedge clk) begin
        if(rst) begin remaining=0; pending_done=0; end
        else if(auto_sink) begin
            if(cv[0] && cmd_ready) remaining=len[0]/16;
            if(dv[0] && ready) begin
                beats=beats+1;
                if(remaining>0) begin remaining=remaining-1; if(remaining==0) pending_done=1; end
            end
        end
        if(ref_dut.m_vsync) admissions=admissions+1;
        if(ref_dut.frame_good) complete=complete+1;
        if(ref_dut.capture_overflow) overflows=overflows+1;
        if(ref_dut.ov5640_ddr_w_ctrl.publish) publications=publications+1;
        if(cv[0] && !cmd_ready || dv[0] && !ready) stalls=stalls+1;
        if(ref_dut.diag_fault && ref_dut.diag_short) short_faults=short_faults+1;
        #1;
        if(outputs[0] !== outputs[1] || ref_dut.pixel_count !== dut.pixel_count ||
           ref_dut.pixel_limit !== dut.pixel_limit || ref_dut.diag_input_count !== dut.diag_input_count)
            $fatal(1,"cam6 mismatch cycle=%0d ref_count=%h new_count=%h state=%h",comparisons,ref_dut.pixel_count,dut.pixel_count,state[0]);
        comparisons=comparisons+1;
    end
    task tick(input bit v,input bit s,input [15:0] p);
        begin @(negedge clk); valid=v; vs=s; hs=v; data=p; @(posedge clk); #2; end
    endtask
    task idle(input integer n);
        integer i; begin for(i=0;i<n;i=i+1) tick(0,0,0); end
    endtask
    task reset_all;
        begin @(negedge clk); rst=1; abort_dma=0; ack=0; stall_sink=0; stall_cmd=0; cam_en=1;
            idle(8); @(negedge clk); rst=0; idle(10); end
    endtask
    task start_frame;
        begin tick(0,1,0); idle(16); end
    endtask
    task frame(input integer n,input bit stalled);
        integer i; reg [31:0] r;
        begin start_frame(); for(i=0;i<n;i=i+1) begin
            r=random_word(); if(stalled && r[2:0]==0) idle(1+(r[5:3]%5)); tick(1,0,r[15:0]);
        end idle(200); end
    endtask
    integer i,k,j,oldpub; reg [31:0] r, boundary_value, expect_count;
    initial begin
        reset_all(); frame(LEN*8,0); idle(100); ack=3; idle(5); ack=0;
        frame(LEN*8,1); idle(100);
        if(publications<2) $fatal(1,"full-length frame publication missing");
        // Dynamic lengths include zero, minimal beat, odd lengths, and maximum port value.
        for(j=0;j<6;j=j+1) begin
            reset_all();
            @(negedge clk); base1=32'hfffffff0-j*256; base2=32'h00800000+j*4096;
            case(j) 0:dynamic_len=1; 1:dynamic_len=7; 2:dynamic_len=129;
                3:dynamic_len=LEN/2; 4:dynamic_len=0; 5:dynamic_len={($clog2(LEN)+1){1'b1}}; endcase
            if(j<4) begin
                oldpub=publications; frame(dynamic_len*8,1);
                if(publications!=oldpub+1) $fatal(1,"dynamic frame failed j=%0d",j);
                dynamic_cases=dynamic_cases+1;
            end else if(j==4) begin
                start_frame(); idle(20);
                if(!ar[0] || ref_dut.pixel_limit!=0) $fatal(1,"zero-length admission semantics");
                zero_rejects=zero_rejects+1;
            end else begin
                start_frame();
                if(ref_dut.pixel_limit!==dynamic_len*8) $fatal(1,"max dynamic length quota");
                frame(123,0); reset_all(); dynamic_cases=dynamic_cases+1;
            end
        end
        // Original command holds through backpressure while live previous-bank output follows addresses.
        reset_all(); dynamic_len=LEN; stall_cmd=1; start_frame(); idle(20);
        if(!cv[0]) $fatal(1,"command stall not reached");
        r=addr[0]; boundary_value=len[0];
        @(negedge clk); base1=32'habcdef00; base2=32'h12345670; dynamic_len=7;
        idle(20);
        if(addr[0]!==r || len[0]!==boundary_value || prev[0]!==base2 || ref_dut.pixel_limit!==LEN*8)
            $fatal(1,"dynamic command/quota hold or live prev_frame_base");
        stall_cmd=0; idle(20); reset_all(); dynamic_cases=dynamic_cases+1;
        dynamic_len=LEN;
        frame(123,1); start_frame(); idle(20);
        abort_dma=1; idle(1); abort_dma=0; idle(20);
        reset_all(); stall_sink=1; frame(10000,0); idle(20);
        if(overflows==0) $fatal(1,"actual FIFO overflow not reached");
        // Reset while the actual FIFO is full, then verify recovery publication.
        reset_all(); oldpub=publications; frame(LEN*8,1);
        if(publications!=oldpub+1) $fatal(1,"overflow/reset recovery publication");
        reset_all(); cam_en=0; frame(100,0); cam_en=1; idle(30); frame(LEN*8,1);
        // Paired deposits exercise every carry/wrap in increment, hold, and reset priority.
        for(k=1;k<=32;k=k+1) begin
            for(j=0;j<3;j=j+1) begin
                reset_all(); start_frame();
                boundary_value=(64'h1<<k)-1;
                @(negedge clk); ref_dut.pixel_count=boundary_value; dut.pixel_count=boundary_value;
                if(j==2) rst=1;
                expect_count=(j==2) ? 0 : ((j==0) ? boundary_value+32'd1 : boundary_value);
                tick(j==0,0,16'habcd);
                if(ref_dut.pixel_count!==expect_count) $fatal(1,"boundary did not exercise requested operation k=%0d j=%0d got=%h expected=%h",k,j,ref_dut.pixel_count,expect_count);
                idle(3); boundaries=boundaries+1;
            end
        end
        reset_all();
        for(i=0;i<8000;i=i+1) begin
            r=random_word(); tick(r[0],r[9:2]==0,r[31:16]);
            if(i%991==0) reset_all();
            if(i%503==0) begin abort_dma=1; idle(1); abort_dma=0; end
            if(i%37==0) begin @(negedge clk); base1=random_word(); base2=random_word(); dynamic_len=random_word(); end
        end
        if(admissions<10 || complete==0 || publications<8 || beats<3*LEN || boundaries!=96 ||
           dynamic_cases!=6 || stalls==0 || zero_rejects!=1 || short_faults==0) $fatal(1,"missing coverage");
        $display("CAM6_TC04_PASS comparisons=%0d admissions=%0d complete=%0d overflows=%0d publications=%0d beats=%0d boundaries=%0d dynamic_cases=%0d stalls=%0d zero_rejects=%0d short_faults=%0d",comparisons,admissions,complete,overflows,publications,beats,boundaries,dynamic_cases,stalls,zero_rejects,short_faults);
        $finish;
    end
    initial begin #100000000; $fatal(1,"timeout"); end
endmodule
