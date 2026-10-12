`timescale 1ns/1ps
module tb_fifo_read;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg fc=0,ac=0,pc=0;always #20 fc=~fc;always #7 ac=~ac;always #8 pc=~pc;
    reg button=0,perst=0,arst=1,ddr=0,link=0,rv=0;
    wire prst,pclko,admit,ap,fault,fa,fp,idlea,idlep,arv,rr;
    wire [31:0] araddr;wire [3:0] arlen;
    integer mode,ars=0,rs=0;
    fpga_v8_reset_fault_guard #(.ALIVE_LIMIT(32),.QUALIFY_CYCLES(8)) supervisor(
        .free_clk(fc),.button_rst_n(button),.perst_n(perst),.axi_clk(ac),.axi_rst(arst),
        .ddr_init_done(ddr),.startup_idle_axi(idlea),.startup_idle_pcie(idlep),
        .pcie_clk(pclko),.pcie_rst(prst),.smlh_link_up(link),.rdlh_link_up(link),
        .fault(fault),.admit_axi(admit),.admit_pcie(ap),.fault_axi(fa),.fault_pcie(fp));
    fpga_v8_pcie_fifo_h2f_rfg01 dut(
        .i_admit(ap),.i_admit_axi(admit),.startup_idle_axi(idlea),.startup_idle_pcie(idlep),
        .button_rst_n(button),.perst_n(perst),.ref_clk_n(~pc),.ref_clk_p(pc),.rxn(2'b0),.rxp(2'b0),
        .fifo_pcie_clk(pclko),.fifo_pcie_rst(prst),.i_msi_req(4'b0),.axi_clk(ac),.axi_rst(arst),
        .axi_awready(1'b1),.axi_wready(1'b1),.axi_bid(4'b0),.axi_bresp(2'b0),.axi_bvalid(1'b0),
        .axi_araddr(araddr),.axi_arlen(arlen),.axi_arvalid(arv),.axi_arready(1'b1),
        .axi_rid(4'b0),.axi_rdata(128'h4),.axi_rresp(2'b0),.axi_rlast(1'b1),.axi_rvalid(rv),.axi_rready(rr));
    always @(posedge ac)begin
        if(arv)ars<=ars+1;
        if(rv && rr)rs<=rs+1;
    end
    initial begin
        if(!$value$plusargs("MODE=%d",mode))mode=0;
        #100;button=1;perst=1;arst=0;ddr=1;link=1;#3000;
        if(!ap)$fatal(1,"startup admission");
        if(mode==1)begin link=0;#100;link=1;#200;end
        // mode1 proves diagnostic F2H read can start after fault; H2F still closed.
        dut.pango_pcie_top.f2h_public(32'h40010410);
        wait(ars==1);#100;
        if(araddr!=32'h40010410 || arlen!=0 || rs)$fatal(1,"F2H read fixture");
        if(mode==0)begin link=0;#100;link=1;#200;end
        if(!fault || ap || admit || !rr)$fatal(1,"fault cut accepted R or reopened command");
        @(negedge ac);rv=1;@(negedge ac);rv=0;#100;
        if(rs!=1 || ars!=1)$fatal(1,"R did not drain");
        $display("FIFO_READ_PASS mode=%0d R_DRAIN_OR_DIAGNOSTIC_ONLY_NO_POSTED_VISIBILITY_CLAIM",mode);
        $finish;
    end
    initial begin #30000;$fatal(1,"read watchdog");end
endmodule
