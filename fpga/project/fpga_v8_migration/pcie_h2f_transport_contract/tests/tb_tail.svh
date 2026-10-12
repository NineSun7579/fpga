    reg pre_aw_ready=0,periodic_w=0;
    reg [1:0] memory_resp=0;
    integer aw_count=0,good_b_count=0,fifo_pop_count=0,retire_count=0;
    integer w_stalls=0,aw_stalls=0;
    reg prior_w_stall=0,prior_aw_stall=0;
    reg [144:0] saved_w;
    reg [38:0] saved_aw;
    reg prior_toggle=0;
    integer outstanding_aw=0;
    integer strict=1;
    always @(posedge core_clk) begin
        if(!rst_n) begin
            prior_w_stall<=0;prior_aw_stall<=0;prior_toggle<=0;outstanding_aw=0;
        end else begin
            if(awvalid && awready) aw_count=aw_count+1;
            if(bvalid && bready && bid==0) good_b_count=good_b_count+1;
            if(dut.fifo_rx_rd_en && !dut.fifo_rx_empty) begin
                fifo_pop_count=fifo_pop_count+1;
                $fdisplay(trace,"%0d %0t POP",op,$time);
            end
            if(strict) begin
                if(awvalid && awready && outstanding_aw!=0) $fatal(1,"multiple outstanding AW");
                if(bvalid && bready && outstanding_aw!=1) $fatal(1,"B without exactly one AW");
`ifndef BASELINE
                if(dut.rx_w_queue_count>2 || (dut.rx_w_queue_count+dut.rx_read_pending)>2)
                    $fatal(1,"synchronous RX FIFO response slot overcommit");
                if(dut.rx_read_pending && dut.rx_w_queue_count==2 && !(wvalid && wready))
                    $fatal(1,"FIFO result has no reserved holding slot");
`endif
                if(dut.fifo_rx_rd_en && dut.fifo_rx_empty) $fatal(1,"empty FIFO read");
                if(dut.fifo_rx_rd_en && !route_aw) $fatal(1,"FIFO pop before AW");
                if(wvalid && !route_aw) $fatal(1,"WVALID before AW");
                if(prior_w_stall && (!wvalid || {wdata,wstrb,wlast}!==saved_w))
                    $fatal(1,"W changed/dropped under stall op=%0d",op);
                if(prior_aw_stall && (!awvalid || {awaddr,awlen,awsize}!==saved_aw))
                    $fatal(1,"AW changed/dropped under stall");
                if(memory_mode && wvalid && wready && wlast!=(mem_left==1))
                    $fatal(1,"incorrect WLAST for accepted AW");
            end
            if(awvalid && awready) outstanding_aw=outstanding_aw+1;
            if(bvalid && bready) outstanding_aw=outstanding_aw-1;
            if(wvalid && !wready) w_stalls=w_stalls+1;
            if(awvalid && !awready) aw_stalls=aw_stalls+1;
            prior_w_stall<=wvalid && !wready;saved_w<={wdata,wstrb,wlast};
            prior_aw_stall<=awvalid && !awready;saved_aw<={awaddr,awlen,awsize};
            if(dut.rx_retired_toggle!=prior_toggle) begin
                retire_count=retire_count+1;
                $fdisplay(trace,"%0d %0t CREDIT",op,$time);
            end
            prior_toggle<=dut.rx_retired_toggle;
        end
    end
    always @(posedge pcie_clk) if(rst_n) begin
        if(dut.pango_pcie_top.tlp_valid && dut.pango_pcie_top.tlp_ready)
            $fdisplay(trace,"%0d %0t TLP %016x %0d %02x",op,$time,
                dut.pango_pcie_top.tlp_address,dut.pango_pcie_top.tlp_dwords,
                dut.pango_pcie_top.tlp_data[7:0]);
        if(dut.pango_pcie_top.ram_wr_en)
            $fdisplay(trace,"%0d %0t SRAM_W %0d %04x %032x",op,$time,
                dut.pango_pcie_top.ram_wr_addr,dut.pango_pcie_top.ram_wr_be,dut.pango_pcie_top.ram_wr_data);
    end
    integer stim,scan,case_id,kind,bytes,profile,mrrs_cfg,do_reset;
    reg [63:0] hostaddr;
    reg [31:0] target,word;
    integer base_m,base_b,base_w,base_aw,base_good,base_pop,base_credit;
    integer base_ws,base_as,n,needed,success;
    task await_transfer;
        begin
            n=0;needed=(bytes+255)/256;success=0;
            while(n<1200000 && !success) begin
                tick(1);n=n+1;
                if(msi_count>base_m && good_b_count>=base_good+needed) success=1;
                if(kind>=2 && n>=((kind==6) ? 800 : 300)) n=1200000;
                if(!strict && n>=1200 && !success) n=1200000;
            end
            tick(12);
            $fdisplay(trace,"%0d %0t END %0d %0d %0d %0d %0d %0d %0d %0d %0d",op,$time,
                success,aw_count-base_aw,w_count-base_w,b_count-base_b,msi_count-base_m,
                fifo_pop_count-base_pop,retire_count-base_credit,w_stalls-base_ws,aw_stalls-base_as);
        end
    endtask
    initial begin
        trace=$fopen("events.trace","w");stim=$fopen("cases.txt","r");
        if(!$value$plusargs("STRICT=%d",strict)) strict=1;
        common_reset();
        while(!$feof(stim)) begin
            scan=$fscanf(stim,"%d %d %d %h %h %h %d %d %d\n",
                case_id,kind,bytes,hostaddr,target,word,profile,mrrs_cfg,do_reset);
            if(scan==9) begin
                op=case_id;
                if(do_reset) common_reset();
                pre_aw_ready=0;periodic_w=0;memory_resp=0;
                aw_gate=1;w_gate=1;ctrl_aw_gate=1;ctrl_w_gate=1;
                force_wrong_id=0;b_delay=23;
                memory_mode=(kind!=1);
                if(kind==1 && target==32'h400100c0 && word==0 && bank0==0) publish();
                dut.pango_pcie_top.mrrs=mrrs_cfg;
                base_m=msi_count;base_b=b_count;base_w=w_count;base_aw=aw_count;
                base_good=good_b_count;base_pop=fifo_pop_count;base_credit=retire_count;
                base_ws=w_stalls;base_as=aw_stalls;
                if(profile==1) w_gate=0;
                if(profile==5) w_gate=0; // remain blocked until next common reset
                if(profile==6) w_gate=0;
                if(profile==2) begin aw_gate=0;pre_aw_ready=1;end
                if(profile==3 || profile==4) begin periodic_w=1;w_gate=0;end
                if(profile==4) begin aw_gate=0;ctrl_aw_gate=0;ctrl_w_gate=0;end
                if(kind==2) force_wrong_id=1;
                if(kind==3) b_delay=1000000;
                if(kind==4) memory_resp=2;
                if(kind==5) memory_resp=2; // final singleton error still retires
                $fdisplay(trace,"%0d %0t BEGIN %0d %0d %016x %08x %08x %0d %0d",op,$time,
                    kind,bytes,hostaddr,target,word,profile,mrrs_cfg);
                fork
                    begin
                        if(profile==1) begin
                            wait(wvalid);tick(25);w_gate=1;
                        end
                        if(profile==6) begin
                            wait(wvalid);tick(3000);w_gate=1;
                        end
                        if(profile==2 || profile==4) begin
                            if(strict) begin wait(awvalid);tick(25);end
                            else tick(120);
                            aw_gate=1;ctrl_aw_gate=1;tick(17);ctrl_w_gate=1;
                        end
                        if(profile==3 || profile==4) begin
                            wait(wvalid);tick(9);w_gate=1;
                        end
                    end
                    begin
                        dut.pango_pcie_top.h2f(target,bytes,word,hostaddr,kind==1);
                        await_transfer();
                    end
                join
                $display("CASE_DONE id=%0d success=%0d W=%0d B=%0d MSI=%0d",op,success,
                    w_count-base_w,b_count-base_b,msi_count-base_m);
                // A common reset in the next row is the only permitted fault
                // cleanup. Do not invent an independent CPU/link reset.
            end
        end
        $fclose(trace);$fclose(stim);
        $display("H2F_TB_DONE");$finish;
    end
endmodule
