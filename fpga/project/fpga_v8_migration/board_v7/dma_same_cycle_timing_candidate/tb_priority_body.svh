always #4 clk=~clk;
integer mask, n, vectors=0;
reg [32-$clog2(WIDTH/8):0] expected_len;
reg [31:0] lengths[0:15];
initial begin
    lengths[0]=0; lengths[1]=1; lengths[2]=15; lengths[3]=16;
    lengths[4]=17; lengths[5]=31; lengths[6]=32; lengths[7]=33;
    lengths[8]=255; lengths[9]=256; lengths[10]=4080; lengths[11]=4095;
    lengths[12]=4096; lengths[13]=4097; lengths[14]=32'hffffffff; lengths[15]=32'h80000001;
    rst=1; repeat(4) @(negedge clk); rst=0;
    for(n=0;n<16;n=n+1) for(mask=0;mask<64;mask=mask+1) begin
        @(negedge clk);
        rst=(mask&1)!=0; cmd_valid=(mask&2)!=0;
        old_dut.cmd_ready=(mask&4)!=0; new_dut.cmd_ready=(mask&4)!=0;
        m_axi_awready=(mask&8)!=0;
        old_dut.m_axi_awvalid=(mask&16)!=0; new_dut.m_axi_awvalid=(mask&16)!=0;
        old_dut.m_axi_awlen=7; new_dut.m_axi_awlen=7;
        old_dut.len=19; new_dut.len=19;
        old_dut.trans=1; new_dut.trans=1;
        old_dut.abort_r=(mask&32)!=0; new_dut.abort_r=(mask&32)!=0;
        old_dut.burst_trans=0; new_dut.burst_trans=0;
        old_dut.w_done=0; new_dut.w_done=0;
        cmd_len=lengths[n]; cmd_addr=32'h01800ff0;
        m_axi_bvalid=0; abort_req=0; data_in_valid=0; data_in_available=0;
        #1;
        if(rst) expected_len=0;
        else if(cmd_valid && old_cmd_ready)
            expected_len=(cmd_len >> $clog2(WIDTH/8)) + (|(cmd_len & (WIDTH/8-1)));
        else if(old_m_axi_awvalid && m_axi_awready) expected_len=11;
        else if(old_dut.abort_done == 1'b1) expected_len=0;
        else expected_len=19;
        @(posedge clk); #1;
        if({@OLDBUS@} !== {@NEWBUS@}) $fatal(1,"priority outputs mismatch");
        @CHECK@
        if(old_dut.len !== expected_len || new_dut.len !== expected_len)
            $fatal(1,"len priority mask=%0d len=%h expected=%h actual=%h",mask,cmd_len,expected_len,old_dut.len);
        vectors=vectors+1;
    end
    $display("PRIORITY_PASS vectors=%0d",vectors); $finish;
end
initial begin #200000; $fatal(1,"priority timeout"); end
endmodule
