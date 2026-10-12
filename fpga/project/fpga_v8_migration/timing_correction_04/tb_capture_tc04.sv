`timescale 1ns/1ps
module tb_capture_tc04;
    parameter LEN=38400, SEED=1;
    reg clk=0, rst=1, epoch=0, lease=0, abort_dma=0, done_dma=0, cam_en=1;
    reg valid=0, hs=0, vs=0, ready=0, cmd_ready=0;
    reg [15:0] data=0;
    reg [1:0] ack=0;
    always #5 clk=~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    wire [15:0] available[0:1];
    wire [127:0] payload[0:1];
    wire dv[0:1], last[0:1], cv[0:1], ar[0:1];
    wire [31:0] addr[0:1], len[0:1], seq[0:1], fault[0:1], rejects[0:1], pixels[0:1];
    wire [31:0] cnt[0:1], num[0:1], zdin[0:1], zout[0:1], state[0:1], lc[0:1], wc[0:1];
    wire [1:0] req[0:1];
    wire sof[0:1], bank[0:1], pub[0:1], err[0:1], ei[0:1], flush[0:1], good[0:1], ov[0:1];
`define CAP_PORTS(N) \
    .axi_clk(clk),.axi_rst(rst),.epoch_start(epoch),.lease_block(lease), \
    .dma_abort(abort_dma),.dma_abort_req(ar[N]),.dma_done(done_dma), \
    .axi_data_available(available[N]),.axi_cam_en(cam_en), \
    .s_data(data),.s_data_valid(valid),.s_hsync(hs),.s_vsync(vs), \
    .axi_data(payload[N]),.axi_data_valid(dv[N]),.axi_data_last(last[N]),.axi_data_ready(ready), \
    .axi_cmd_addr(addr[N]),.axi_cmd_len(len[N]),.axi_cmd_valid(cv[N]),.axi_cmd_ready(cmd_ready), \
    .xdma_req(req[N]),.xdma_ack(ack),.admitted_sof(sof[N]),.capture_bank(bank[N]), \
    .publish(pub[N]),.publish_seq(seq[N]),.retired_error(err[N]),.engine_idle(ei[N]), \
    .capture_flush_o(flush[N]),.frame_good_o(good[N]),.capture_overflow_o(ov[N]), \
    .dbg_fault_snapshot(fault[N]),.dbg_reject_counts(rejects[N]),.dbg_input_pixels(pixels[N]), \
    .dbg_axi_cnt(cnt[N]),.dbg_axi_num(num[N]),.dbg_zdin(zdin[N]),.dbg_zout(zout[N]), \
    .dbg_state(state[N]),.dbg_last_cnt(lc[N]),.dbg_wd_cnt(wc[N])
    fpga_v8_capture_ov5640_ddr #(.CAM_DATA_LEN(LEN)) ref_dut(`CAP_PORTS(0));
    fpga_v8_capture_ov5640_ddr_tc04 #(.CAM_DATA_LEN(LEN)) dut(`CAP_PORTS(1));
`undef CAP_PORTS
    wire [599:0] all_outputs[0:1];
    genvar g;
    generate for(g=0;g<2;g=g+1) begin
        assign all_outputs[g]={available[g],payload[g],dv[g],last[g],addr[g],len[g],cv[g],ar[g],
            req[g],sof[g],bank[g],pub[g],seq[g],err[g],ei[g],flush[g],good[g],ov[g],
            fault[g],rejects[g],pixels[g],cnt[g],num[g],zdin[g],zout[g],state[g],lc[g],wc[g]};
    end endgenerate
    reg [31:0] rng=SEED;
    function [31:0] random_word;
        begin rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5); random_word=rng; end
    endfunction
    integer comparisons=0, admissions=0, complete=0, overflows=0, publications=0, beats=0, boundaries=0;
    // A minimal command/data consumer returns done after the advertised byte ledger.
    integer remaining=0;
    reg pending_done=0, auto_sink=1, stall_sink=0;
    always @(negedge clk) begin
        if(auto_sink) begin
            ready=!stall_sink && ((random_word()&7)!=0);
            cmd_ready=((random_word()&3)!=0);
            done_dma=pending_done; pending_done=0;
        end
    end
    always @(posedge clk) begin
        if(rst || epoch) begin remaining=0; pending_done=0; end
        else if(auto_sink) begin
            if(cv[0] && cmd_ready) remaining=len[0]/16;
            if(dv[0] && ready) begin
                beats=beats+1;
                if(remaining>0) begin remaining=remaining-1; if(remaining==0) pending_done=1; end
            end
        end
        if(sof[0]) admissions=admissions+1;
        if(good[0]) complete=complete+1;
        if(ov[0]) overflows=overflows+1;
        if(pub[0]) publications=publications+1;
        #1;
        if(all_outputs[0] !== all_outputs[1] || ref_dut.pixel_count !== dut.pixel_count ||
           ref_dut.pixel_limit !== dut.pixel_limit || ref_dut.diag_input_count !== dut.diag_input_count)
            $fatal(1,"capture mismatch cycle=%0d ref_pixel_count=%h new_pixel_count=%h state=%h",comparisons,ref_dut.pixel_count,dut.pixel_count,state[0]);
        comparisons=comparisons+1;
    end
    task tick(input bit v,input bit s,input [15:0] p);
        begin @(negedge clk); valid=v; vs=s; hs=v; data=p; @(posedge clk); #2; end
    endtask
    task idle(input integer n);
        integer i; begin for(i=0;i<n;i=i+1) tick(0,0,0); end
    endtask
    task reset_all;
        begin @(negedge clk); rst=1; lease=0; abort_dma=0; ack=0; stall_sink=0;
            idle(8); @(negedge clk); rst=0; idle(10); end
    endtask
    task start_frame;
        begin tick(0,1,0); idle(16); end
    endtask
    task frame(input integer n,input bit stalls);
        integer i; reg [31:0] r;
        begin start_frame(); for(i=0;i<n;i=i+1) begin
            r=random_word(); if(stalls && r[2:0]==0) idle(1+(r[5:3]%5)); tick(1,0,r[15:0]);
        end idle(100); end
    endtask
    integer i,k; reg [31:0] r;
    initial begin
        reset_all(); frame(LEN*8,0); idle(100); ack=3; idle(5); ack=0;
        frame(LEN*8,1); idle(100);
        reset_all(); frame(123,1); start_frame(); idle(20);
        abort_dma=1; idle(1); abort_dma=0; idle(20);
        reset_all(); stall_sink=1; frame(10000,0); idle(20);
        if(overflows==0) $fatal(1,"real FIFO overflow not reached");
        @(negedge clk); epoch=1; idle(1); epoch=0; stall_sink=0; idle(20);
        frame(LEN*8,1); idle(100);
        reset_all(); lease=1; frame(100,0); lease=0; idle(30); frame(LEN*8,1); idle(100);
        // Upper carry bits and wrap are reached by paired state deposits only.
        // Real w_en and FIFO logic remain active, and all public outputs are compared.
        for(k=1;k<=32;k=k+1) begin
            reset_all(); start_frame();
            @(negedge clk); ref_dut.pixel_count=(64'h1<<k)-1; dut.pixel_count=(64'h1<<k)-1;
            tick(1,0,16'habcd); idle(3); boundaries=boundaries+1;
        end
        reset_all();
        @(negedge clk);
        ref_dut.diag_input_count=32'hffffffff; dut.diag_input_count=32'hffffffff;
        tick(1,0,16'h5678); idle(2);
        if(ref_dut.diag_input_count!==32'd0) $fatal(1,"input diagnostic wrap");
        start_frame();
        if(pixels[0]!==32'd0) $fatal(1,"input diagnostic SOF latch");
        reset_all();
        for(i=0;i<8000;i=i+1) begin
            r=random_word(); tick(r[0],r[9:2]==0,r[31:16]);
            if(i%991==0) begin @(negedge clk); epoch=1; idle(1); epoch=0; end
            if(i%503==0) begin abort_dma=1; idle(1); abort_dma=0; end
        end
        if(admissions<10 || complete==0 || publications<3 || beats<3*LEN || boundaries!=32) $fatal(1,"missing coverage pubs=%0d beats=%0d",publications,beats);
        $display("CAPTURE_TC04_PASS comparisons=%0d admissions=%0d complete=%0d overflows=%0d publications=%0d beats=%0d boundaries=%0d",comparisons,admissions,complete,overflows,publications,beats,boundaries);
        $finish;
    end
    initial begin #100000000; $fatal(1,"timeout"); end
endmodule
