`timescale 1ns/1ps
`ifndef FIFO_MODULE
`define FIFO_MODULE pcie_fifo
`endif
module tb_fpga_v8_pcie_retirement;
    reg core_clk=0,pcie_clk=0;
    always #5 core_clk=!core_clk;
    always #8 pcie_clk=!pcie_clk;
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
    wire endpoint_aw=awvalid && aw_gate && !memory_mode;
    wire endpoint_w=wvalid && route_aw && w_gate && !memory_mode;
    // Models the AW-selected route in the original crossbar. WREADY is low
    // before routing AW, avoiding fictitious pre-command FIFO reads.
    assign awready=aw_gate && (memory_mode ? !mem_aw && !mem_b : ea_ready);
    assign wready=route_aw && w_gate && (memory_mode ? mem_aw : ew_ready);
    assign bvalid=(memory_mode ? mem_b : eb_valid) && release_b;
    assign bresp=memory_mode ? 2'b00 : eb_resp;
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
        if(cycle>2500000) $fatal(1,"global watchdog op=%0d",op);
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
            if(dut.pango_pcie_top.ack32 || dut.pango_pcie_top.ack64)
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
    initial begin
        trace=$fopen("events.trace","w");
        if(!$value$plusargs("MODE=%d",mode)) mode=0;
        common_reset();
        if(mode==0) begin
            publish();
            // Delayed local control acceptance demonstrates early MSI before
            // CLAIM execution, separately from the intentionally delayed B.
            ctrl_aw_gate=0;ctrl_w_gate=0;
            fork
                begin tick(100);ctrl_aw_gate=1;tick(7);ctrl_w_gate=1;end
                ctl_write(1,32'h30,0);
            join
            if(bank0!=3) $fatal(1,"CLAIM did not execute");
            ctl_write(2,32'h40,0);
            ctl_write(3,32'h44,32'h10203040);
            ctl_write(4,32'h48,32'h11223344);
            ctl_write(5,32'h4c,1);
            if(bank0!=0) $fatal(1,"ACK did not free bank0");
            // Repeated rejected claim/ACK gives real SLVERR retirement.
            ctl_write(6,32'h30,0);
            ctl_write(7,32'h4c,1);
            // AW stall plus separate local W stall; toggle alternates across
            // each 16-byte descriptor and cannot reuse earlier retirement.
            aw_gate=0;ctrl_w_gate=0;
            fork
                begin tick(100);aw_gate=1;tick(20);ctrl_w_gate=1;end
                ctl_write(8,32'h40,32'h12345678);
            join
            // Common reset while B is outstanding: no completion is allowed
            // to leak into the next command. CPU-only reset is not modeled.
            op=9;b_delay=10000;
            dut.pango_pcie_top.h2f(32'h40010100,16,0,32'h01000000,1);
            tick(80);$fdisplay(trace,"%0d %0t PENDING_RESET",op,$time);
            common_reset();b_delay=23;ctl_write(10,32'h40,32'hcafebabe);
        end else if(mode==1) begin
            memory_write(20,4092,32'h01000000);
            common_reset();memory_write(21,4100,32'h01000000);
            common_reset();memory_write(22,1228800,32'h01000000);
        end else if(mode==2) begin
            // Actual controller does not shorten first chunk at host +4.
            memory_write(30,8192,32'h01000004);
        end else if(mode==3) begin
            // Legacy single-beat prefetch does not retain WVALID when W stalls.
            w_gate=0;
            fork
                begin tick(70);w_gate=1;end
                ctl_write(40,32'h40,32'hcafebabe);
            join
            common_reset();ctl_write(41,32'h40,32'habcdef01);
        end else if(mode==4) begin
            // Wrong BID must never produce a retirement credit.
            force_wrong_id=1;
            ctl_write(50,32'h40,32'hcafebabe);
            common_reset();ctl_write(51,32'h40,32'habcdef01);
        end
        $fclose(trace);
        $display("RETIREMENT_TB_DONE mode=%0d MSI=%0d B=%0d W=%0d",mode,msi_count,b_count,w_count);
        $finish;
    end
endmodule
