`timescale 1ns/1ps
`ifndef FIFO_MODULE
`define FIFO_MODULE fpga_v8_pcie_fifo_h2f
`endif
module tb_fpga_v8_h2f_transport;
    reg core_clk=0,pcie_clk=0;
    always #5 core_clk=!core_clk;
    always #8 pcie_clk=!pcie_clk;
    reg pre_aw_ready=0,periodic_w=0;
    reg [1:0] memory_resp=0;
    reg rst_n=0;
    GTP_GRS GRS_INST(.GRS_N(rst_n));
    wire [3:0] awid,bid,arid;
    wire [31:0] awaddr,araddr;
    wire [3:0] awlen,arlen;
    wire [2:0] awsize,arsize,awprot,arprot;
    wire [1:0] awburst,arburst;
    wire awlock,arlock,awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire [3:0] awcache,awqos,arcache,arqos;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    wire [1:0] bresp;
    integer op=0,cycle=0,trace,mode=0,msi_count=0,b_count=0,w_count=0;
    integer claim_time=0,last_b_time=0,last_msi_time=0;
    reg memory_mode=0,aw_gate=1,w_gate=1,force_wrong_id=0;
    integer b_delay=23,b_age=0;
    reg route_aw=0;
    wire ea_ready,ew_ready,eb_valid,eb_ready;
    wire [3:0] eb_id;
    wire [1:0] eb_resp;
    reg mem_aw=0,mem_b=0;
    integer mem_left=0,mem_w=0,mem_expected=0;
    wire release_b=b_age>=b_delay;
    wire gate_w = w_gate && (!periodic_w || cycle%17>=7);
    wire endpoint_aw=awvalid && aw_gate && !memory_mode;
    wire endpoint_w=wvalid && route_aw && gate_w && !memory_mode;
    // Models the AW-selected route in the original crossbar. WREADY is low
    // before routing AW, avoiding fictitious pre-command FIFO reads.
    assign awready=aw_gate && (memory_mode ? !mem_aw && !mem_b : ea_ready);
    assign wready=(pre_aw_ready && !route_aw) || (route_aw && gate_w && (memory_mode ? mem_aw : ew_ready));
    assign bvalid=(memory_mode ? mem_b : eb_valid) && release_b;
    assign bresp=memory_mode ? memory_resp : eb_resp;
    assign bid=force_wrong_id ? 4'h1 : (memory_mode ? 4'h0 : eb_id);
    assign eb_ready=bready && release_b && !memory_mode;
    `FIFO_MODULE dut (
        .button_rst_n(rst_n),.perst_n(rst_n),.ref_clk_p(pcie_clk),.ref_clk_n(!pcie_clk),
        .rxn(2'b0),.rxp(2'b0),.i_msi_req(4'b0),
        .axi_clk(core_clk),.axi_rst(!rst_n),
        .axi_awid(awid),.axi_awaddr(awaddr),.axi_awlen(awlen),.axi_awsize(awsize),
        .axi_awburst(awburst),.axi_awlock(awlock),.axi_awcache(awcache),
        .axi_awprot(awprot),.axi_awqos(awqos),.axi_awvalid(awvalid),.axi_awready(awready),
        .axi_wdata(wdata),.axi_wstrb(wstrb),.axi_wlast(wlast),
        .axi_wvalid(wvalid),.axi_wready(wready),
        .axi_bid(bid),.axi_bresp(bresp),.axi_bvalid(bvalid),.axi_bready(bready),
        .axi_arid(arid),.axi_araddr(araddr),.axi_arlen(arlen),.axi_arsize(arsize),
        .axi_arburst(arburst),.axi_arlock(arlock),.axi_arcache(arcache),
        .axi_arprot(arprot),.axi_arqos(arqos),.axi_arvalid(),.axi_arready(1'b0),
        .axi_rid(4'b0),.axi_rdata(128'b0),.axi_rresp(2'b0),
        .axi_rlast(1'b0),.axi_rvalid(1'b0)
    );
    wire [31:0] ca,cd,cr_addr;
    wire [2:0] cp,cr_prot;
    wire [3:0] cs;
    wire cav,cwv,cbr,carv,crr,car,cwr,cbv,carr,crv;
    wire [1:0] cbp,crp;
    wire [31:0] crd;
    reg ctrl_aw_gate=1,ctrl_w_gate=1;
    fpga_v8_coop_axi128_endpoint #(.ID_WIDTH(4)) endpoint (
        .clk(core_clk),.rst_n(rst_n),
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen({4'b0,awlen}),
        .s_axi_awsize(awsize),.s_axi_awburst(awburst),.s_axi_awlock(awlock),
        .s_axi_awcache(awcache),.s_axi_awprot(awprot),.s_axi_awqos(awqos),.s_axi_awregion(4'b0),
        .s_axi_awvalid(endpoint_aw),.s_axi_awready(ea_ready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(wlast),
        .s_axi_wvalid(endpoint_w),.s_axi_wready(ew_ready),
        .s_axi_bid(eb_id),.s_axi_bresp(eb_resp),.s_axi_bvalid(eb_valid),.s_axi_bready(eb_ready),
        .s_axi_arid(4'b0),.s_axi_araddr(32'b0),.s_axi_arlen(8'b0),.s_axi_arsize(3'b0),
        .s_axi_arburst(2'b0),.s_axi_arlock(1'b0),.s_axi_arcache(4'b0),
        .s_axi_arprot(3'b0),.s_axi_arqos(4'b0),.s_axi_arregion(4'b0),
        .s_axi_arvalid(1'b0),.s_axi_rready(1'b0),
        .m_axil_awaddr(ca),.m_axil_awprot(cp),.m_axil_awvalid(cav),.m_axil_awready(car && ctrl_aw_gate),
        .m_axil_wdata(cd),.m_axil_wstrb(cs),.m_axil_wvalid(cwv),.m_axil_wready(cwr && ctrl_w_gate),
        .m_axil_bresp(cbp),.m_axil_bvalid(cbv),.m_axil_bready(cbr),
        .m_axil_araddr(cr_addr),.m_axil_arprot(cr_prot),.m_axil_arvalid(carv),.m_axil_arready(carr),
        .m_axil_rdata(crd),.m_axil_rresp(crp),.m_axil_rvalid(crv),.m_axil_rready(crr)
    );
    reg input_valid=0,bridge_busy=0,bridge_done=0;
    wire input_ready,cmd_valid;
    wire [1:0] bank0,bank1;
    fpga_v8_coop_control_axil control (
        .core_clk(core_clk),.rst_n(rst_n),.input_valid(input_valid),.input_ready(input_ready),
        .input_raw_valid(1'b1),.input_src_addr(32'h01000000),.input_source_seq(32'h10203040),
        .input_generation(32'h11223344),.input_camera(3'd2),.input_camera_bank(1'b0),
        .input_lease_token(64'h0123456789abcdef),.cmd_valid(cmd_valid),.cmd_ready(1'b1),
        .bridge_busy(bridge_busy),.bridge_done(bridge_done),.bridge_error(1'b0),.bridge_cmd_error(1'b0),
        .src_release_ready(1'b1),.bank0_state(bank0),.bank1_state(bank1),
        .s_axil_awaddr(ca),.s_axil_awprot(cp),.s_axil_awvalid(cav && ctrl_aw_gate),.s_axil_awready(car),
        .s_axil_wdata(cd),.s_axil_wstrb(cs),.s_axil_wvalid(cwv && ctrl_w_gate),.s_axil_wready(cwr),
        .s_axil_bresp(cbp),.s_axil_bvalid(cbv),.s_axil_bready(cbr),
        .s_axil_araddr(cr_addr),.s_axil_arprot(cr_prot),.s_axil_arvalid(carv),.s_axil_arready(carr),
        .s_axil_rdata(crd),.s_axil_rresp(crp),.s_axil_rvalid(crv),.s_axil_rready(crr)
    );
    reg [1:0] old_bank=0;
    reg old_done=0,old_eb=0,old_msi=0;
    always @(negedge core_clk) cycle=cycle+1;
    always @(posedge core_clk) begin
        if(cycle>15000000) $fatal(1,"global watchdog op=%0d",op);
        if(!rst_n) begin
            route_aw<=0;b_age<=0;mem_aw<=0;mem_b<=0;mem_left<=0;old_bank<=0;old_eb<=0;
        end else begin
            if(awvalid && awready) begin
                route_aw<=1;
                if(memory_mode) begin mem_aw<=1;mem_left<=awlen+1;end
                $fdisplay(trace,"%0d %0t AW %08x %x",op,$time,awaddr,awlen);
            end
            if(wvalid && wready) begin
                w_count=w_count+1;
                $fdisplay(trace,"%0d %0t W %032x %04x %0d",op,$time,wdata,wstrb,wlast);
                if(memory_mode) begin
                    mem_w=mem_w+1;mem_left<=mem_left-1;
                    if(wlast) begin mem_aw<=0;mem_b<=1;end
                end
            end
            if(memory_mode ? mem_b : eb_valid) b_age<=b_age+1;
            else b_age<=0;
            if(eb_valid && !old_eb && !memory_mode)
                $fdisplay(trace,"%0d %0t E_BVALID %x",op,$time,eb_resp);
            old_eb<=eb_valid;
            if(bvalid && bready) begin
                b_count=b_count+1;last_b_time=$time;route_aw<=0;mem_b<=0;
                $fdisplay(trace,"%0d %0t B %x %x",op,$time,bid,bresp);
            end
            if(cav && car && ctrl_aw_gate) $fdisplay(trace,"%0d %0t CAW %08x",op,$time,ca);
            if(cwv && cwr && ctrl_w_gate) $fdisplay(trace,"%0d %0t CW %08x",op,$time,cd);
            if(bank0!=old_bank) begin
                if(bank0==3) claim_time=$time;
                $fdisplay(trace,"%0d %0t BANK %x",op,$time,bank0);
            end
            old_bank<=bank0;
        end
    end
    always @(posedge pcie_clk) begin
        if(!rst_n) begin old_done<=0;old_msi<=0;end
        else begin
            if((dut.pango_pcie_top.ack32 || dut.pango_pcie_top.ack64) && !dut.pango_pcie_top.ack_seen)
                $fdisplay(trace,"%0d %0t FETCH %016x %x %0d",op,$time,
                          dut.pango_pcie_top.req_addr,dut.pango_pcie_top.req_length,
                          dut.fpga_ddr3_length);
            if(dut.fpga_rx_done && !old_done)
                $fdisplay(trace,"%0d %0t RX_DONE %0d %0d",op,$time,dut.rx_cnt,dut.dma_total_beats);
            if(dut.pango_pcie_top.msi && !old_msi) begin
                msi_count=msi_count+1;last_msi_time=$time;
                $fdisplay(trace,"%0d %0t MSI",op,$time);
            end
            old_done<=dut.fpga_rx_done;old_msi<=dut.pango_pcie_top.msi;
        end
    end
    task tick(input integer n); repeat(n) @(negedge core_clk); endtask
    task common_reset;
        begin
            @(negedge core_clk);rst_n=0;input_valid=0;bridge_busy=0;bridge_done=0;
            aw_gate=1;w_gate=1;ctrl_aw_gate=1;ctrl_w_gate=1;force_wrong_id=0;
            tick(10);rst_n=1;tick(15);
            $fdisplay(trace,"%0d %0t RESET",op,$time);
        end
    endtask
    task publish;
        begin
            @(negedge core_clk);input_valid=1;
            wait(input_ready);@(posedge core_clk);@(negedge core_clk);input_valid=0;
            wait(cmd_valid);@(posedge core_clk);@(negedge core_clk);bridge_busy=1;
            tick(5);bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;tick(5);
            if(bank0!=2) $fatal(1,"real producer did not publish READY");
        end
    endtask
    task wait_finish(input integer old_m,input integer old_b,input integer limit);
        integer n;
        begin
            n=0;
            while((msi_count==old_m || b_count<=old_b) && n<limit) begin tick(1);n=n+1;end
            if(n==limit) begin
                $fdisplay(trace,"%0d %0t TIMEOUT state=%0d rx=%0d beats=%0d fifo=%0d",op,$time,
                          dut.state,dut.rx_cnt,dut.beats_remain,dut.fifo_rx_water_level);
                $display("CASE_TIMEOUT op=%0d state=%0d rx=%0d beats=%0d fifo=%0d",op,
                         dut.state,dut.rx_cnt,dut.beats_remain,dut.fifo_rx_water_level);
            end
            tick(12);
        end
    endtask
    task ctl_write(input integer nextop,input [31:0] local_offset,word);
        integer m,b;
        begin
            op=nextop;m=msi_count;b=b_count;
            dut.pango_pcie_top.h2f(32'h40010000+local_offset*4,16,word,32'h01000000,1);
            wait_finish(m,b,400);
        end
    endtask
    task memory_write(input integer nextop,input integer bytes,input [31:0] hostaddr);
        integer m,b;
        begin
            op=nextop;m=msi_count;b=b_count;memory_mode=1;mem_w=0;
            dut.pango_pcie_top.h2f(32'h08000000,bytes,0,hostaddr,0);
            wait_finish(m,b+((bytes+255)/256)-1,1000000);
            $fdisplay(trace,"%0d %0t MEMORY_END %0d %0d",op,$time,mem_w,(bytes+15)/16);
        end
    endtask
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
