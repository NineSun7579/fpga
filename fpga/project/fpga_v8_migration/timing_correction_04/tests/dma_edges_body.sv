always #4 clk=~clk;
integer cycles=0, vectors=0, natural=0;
reg [23:0] expected_count;
reg expected_abort, clear_before;
always @(posedge clk) begin
    clear_before = rst || old_dut.abort_r ||
        (old_dut.waiting_source ? (data_in_available != old_dut.available_q) :
         (!old_dut.burst_trans || old_dut.w_progress || data_in_valid || !old_dut.t_m_axi_wready));
    expected_count = clear_before ? 24'd0 :
        (old_dut.wd_cnt == 24'hffffff ? old_dut.wd_cnt : old_dut.wd_cnt + 24'd1);
    expected_abort = old_dut.abort_r;
    if(rst || old_dut.abort_done) expected_abort=0;
    else if((old_dut.trans && abort_req) ||
            (old_dut.waiting_source && old_dut.wd_cnt == LIMIT) ||
            (!old_dut.abort_r && old_dut.burst_trans && old_dut.act_burst_len != 0 &&
             !data_in_valid && old_dut.t_m_axi_wready && !old_dut.w_progress && old_dut.wd_cnt == LIMIT)) expected_abort=1;
    #1;
    if({@OLDBUS@} !== {@NEWBUS@}) $fatal(1,"public mismatch cycle=%0d",cycles);
    if({old_dut.wd_cnt,old_dut.abort_r,old_dut.available_q,old_dut.len,old_dut.trans,old_dut.burst_trans,old_dut.act_burst_len} !==
       {new_dut.wd_cnt,new_dut.abort_r,new_dut.available_q,new_dut.len,new_dut.trans,new_dut.burst_trans,new_dut.act_burst_len})
        $fatal(1,"internal mismatch cycle=%0d",cycles);
    if(old_dut.wd_cnt !== expected_count || new_dut.wd_cnt !== expected_count ||
       old_dut.abort_r !== expected_abort || new_dut.abort_r !== expected_abort)
        $fatal(1,"watchdog/abort edge oracle cycle=%0d",cycles);
    cycles=cycles+1;
end

task reset_pair;
begin
    @(negedge clk); rst=1; cmd_valid=0; abort_req=0;
    data_in_valid=0; data_in_available=0; m_axi_awready=0; m_axi_wready=1; m_axi_bvalid=0; m_axi_bresp=0;
    repeat(4) @(negedge clk);
    rst=0;
end
endtask

task command;
begin
    wait(old_cmd_ready); @(negedge clk);
    cmd_valid=1; cmd_len=256; cmd_addr=32'h01800000; cmd_id=3;
    @(negedge clk); cmd_valid=0;
end
endtask

// Natural local timeout and accepted-AW dummy retirement, with explicit
// protocol assertions in addition to the complete cycle differential.
task natural_timeout;
integer n;
begin
    reset_pair;
    if(WAIT) begin
        command;
        for(n=0;n<LIMIT+3;n=n+1) @(negedge clk);
        if(!old_data_in_abort && !old_cmd_ready) $fatal(1,"waiting timeout did not retire");
        if(old_m_axi_awvalid || old_m_axi_wvalid) $fatal(1,"waiting timeout issued AXI");
        natural=natural+1;
    end
    reset_pair;
    data_in_available=32; data_in_valid=1;
    command;
    wait(old_m_axi_awvalid);
    // Abort while AW is stalled: it must remain advertised.
    @(negedge clk); abort_req=1;
    repeat(3) begin @(negedge clk); if(!old_m_axi_awvalid) $fatal(1,"cancelled stalled AW"); end
    m_axi_awready=1; m_axi_wready=0; data_in_valid=0; data_in_available=0;
    @(negedge clk); m_axi_awready=0;
    repeat(6) @(negedge clk);
    if(old_m_axi_bready) $fatal(1,"BREADY before external last W");
    m_axi_wready=1;
    n=0;
    while(!old_m_axi_bready && n<80) begin
        if(old_m_axi_wvalid && old_m_axi_wstrb !== 0) $fatal(1,"abort dummy strobe");
        @(negedge clk); n=n+1;
    end
    if(!old_m_axi_bready) $fatal(1,"dummy burst failed to finish");
    repeat(5) @(negedge clk);
    if(old_data_in_abort) $fatal(1,"retired without real B");
    m_axi_bvalid=1; m_axi_bresp=2;
    @(negedge clk); m_axi_bvalid=0;
    if(!old_data_in_abort || old_data_in_last) $fatal(1,"abort retirement pulse");
    natural=natural+1;
    // Timeout itself during a real open burst, without explicit abort_req.
    reset_pair; data_in_available=32; data_in_valid=1; command;
    wait(old_m_axi_awvalid);
    @(negedge clk); m_axi_awready=1; data_in_valid=0;
    @(negedge clk); m_axi_awready=0;
    for(n=0;n<LIMIT+4;n=n+1) @(negedge clk);
    if(!old_dut.abort_r) $fatal(1,"accepted burst did not timeout");
    wait(old_m_axi_bready); @(negedge clk); m_axi_bvalid=1;
    @(negedge clk); m_axi_bvalid=0;
    if(!old_data_in_abort || old_data_in_last) $fatal(1,"timeout retirement pulse");
    natural=natural+1;
end
endtask

// Paired state deposits reach all 24 carry boundaries and saturation quickly.
// Matrix includes credit increase/decrease/flush, valid, W backpressure,
// reset+abort+progress, AW/B simultaneous retirement and timeout edges.
task vector;
input [23:0] count;
input integer mask;
input integer state_kind;
begin
    @(negedge clk);
    rst=(mask & 1)!=0; abort_req=(mask & 2)!=0;
    data_in_valid=(mask & 4)!=0; m_axi_wready=(mask & 8)!=0;
    m_axi_awready=(mask & 16)!=0; m_axi_bvalid=(mask & 32)!=0; m_axi_bresp=(mask & 64)!=0 ? 2 : 0;
    data_in_available=(mask & 128)!=0 ? 0 : ((mask & 256)!=0 ? 8 : 7);
    old_dut.wd_cnt=count; new_dut.wd_cnt=count;
    old_dut.available_q=7; new_dut.available_q=7;
    old_dut.trans=1; new_dut.trans=1;
    old_dut.addr=32'h01800000; new_dut.addr=32'h01800000;
    old_dut.len=16; new_dut.len=16;
    old_dut.abort_r=(mask & 512)!=0; new_dut.abort_r=(mask & 512)!=0;
    old_dut.burst_trans=state_kind==1 || state_kind==3;
    new_dut.burst_trans=state_kind==1 || state_kind==3;
    old_dut.m_axi_awvalid=state_kind==2; new_dut.m_axi_awvalid=state_kind==2;
    old_dut.act_burst_len=state_kind==1 ? 16 : 0; new_dut.act_burst_len=state_kind==1 ? 16 : 0;
    old_dut.w_done=state_kind==3; new_dut.w_done=state_kind==3;
    #1;
    vectors=vectors+1;
    @(negedge clk);
end
endtask

integer bit_index, mask, state_kind, k;
reg [23:0] boundary;
initial begin
    rst=1; data_in_keep=16'hffff; data_in=128'h123456;
    repeat(4) @(negedge clk);
    if(LIMIT <= 7) natural_timeout;
    reset_pair;
    for(state_kind=0;state_kind<4;state_kind=state_kind+1)
        for(mask=0;mask<1024;mask=mask+1) begin
            vector(LIMIT,mask,state_kind);
            vector(24'hffffff,mask,state_kind);
        end
    for(bit_index=0;bit_index<24;bit_index=bit_index+1) begin
        boundary=(24'd1 << bit_index)-1;
        // waiting_source and active burst, counting and simultaneous clears.
        for(state_kind=0;state_kind<2;state_kind=state_kind+1) begin
            vector(boundary,8,state_kind);
            vector(boundary,136,state_kind);
            vector(boundary,12,state_kind);
            vector(boundary,523,state_kind);
        end
    end
    vector(24'hfffffe,8,0); vector(24'hffffff,8,0);
    vector(24'hfffffe,8,1); vector(24'hffffff,8,1);
    if(LIMIT>0) begin vector(LIMIT-1,8,0); vector(LIMIT-1,8,1); end
    // Random evolving state/input sequences exercise multi-cycle progress.
    reset_pair;
    for(k=0;k<32;k=k+1) begin
        reset_pair; data_in_available=32; data_in_valid=1; command;
        repeat(100) begin
            @(negedge clk);
            data_in_available=$urandom_range(0,40); data_in_valid=$urandom_range(0,1);
            data_in=$urandom; data_in_keep=$urandom;
            m_axi_awready=$urandom_range(0,1); m_axi_wready=$urandom_range(0,1);
            abort_req=$urandom_range(0,15)==0;
            m_axi_bvalid=old_dut.w_done && $urandom_range(0,1); m_axi_bresp=$urandom_range(0,3);
            if($urandom_range(0,99)==0) rst=1; else rst=0;
        end
    end
    reset_pair;
    $display("DMA_TC04_EDGES_PASS cycles=%0d vectors=%0d natural=%0d",cycles,vectors,natural);
    $finish;
end
initial begin #2000000; $fatal(1,"test timeout"); end
endmodule
