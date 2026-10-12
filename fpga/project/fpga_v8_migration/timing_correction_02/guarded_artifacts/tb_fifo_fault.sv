`timescale 1ns/1ps
module tb_fifo_fault;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg free_clk=0,aclk=0,pclk=0;
    always #20 free_clk=~free_clk;
    always #7 aclk=~aclk;
    always #8 pclk=~pclk;
    reg button=0,perst=0,arst=1,ddr=0,link=0;
    wire pclko,prst,admit_a,admit_p,fault,fa,fp,idle_axi,idle_pcie;
    fpga_v8_reset_fault_guard_02 #(.ALIVE_LIMIT(32),.QUALIFY_CYCLES(8)) guard(
        .free_clk(free_clk),.button_rst_n(button),.perst_n(perst),
        .axi_clk(aclk),.axi_rst(arst),.ddr_init_done(ddr),.startup_idle_axi(idle_axi),.startup_idle_pcie(idle_pcie),
        .pcie_clk(pclko),.pcie_rst(prst),.smlh_link_up(link),.rdlh_link_up(link),
        .fault(fault),.admit_axi(admit_a),.admit_pcie(admit_p),.fault_axi(fa),.fault_pcie(fp));
    wire awvalid,wvalid,wlast,bready,arvalid,rready;
    wire [31:0] awaddr;
    wire [3:0] awlen;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    reg bvalid=0;
    integer aws=0,ws=0,bs=0,mode;
    fpga_v8_pcie_fifo_h2f_tc02 dut(
        .i_admit(admit_p),.i_admit_axi(admit_a),.button_rst_n(button),.perst_n(perst),
        .startup_idle_axi(idle_axi),.startup_idle_pcie(idle_pcie),
        .ref_clk_n(~pclk),.ref_clk_p(pclk),.rxn(2'b0),.rxp(2'b0),
        .fifo_pcie_clk(pclko),.fifo_pcie_rst(prst),
        .i_msi_req(4'b0),.axi_clk(aclk),.axi_rst(arst),
        .axi_awaddr(awaddr),.axi_awlen(awlen),.axi_awvalid(awvalid),.axi_awready(1'b1),
        .axi_wdata(wdata),.axi_wstrb(wstrb),.axi_wlast(wlast),.axi_wvalid(wvalid),.axi_wready(1'b1),
        .axi_bid(4'b0),.axi_bresp(2'b0),.axi_bvalid(bvalid),.axi_bready(bready),
        .axi_arvalid(arvalid),.axi_arready(1'b1),.axi_rid(4'b0),.axi_rdata(128'b0),
        .axi_rresp(2'b0),.axi_rlast(1'b0),.axi_rvalid(1'b0),.axi_rready(rready));
    always @(posedge aclk) if(!arst) begin
        if(awvalid) begin aws<=aws+1;$display("AW t=%0t addr=%h",$time,awaddr);end
        if(wvalid) begin ws<=ws+1;$display("W t=%0t last=%b",$time,wlast);end
        if(bvalid && bready) begin bs<=bs+1;$display("B t=%0t",$time);end
    end
    initial begin
        if(!$value$plusargs("MODE=%d",mode))mode=0;
        #100;button=1;perst=1;arst=0;ddr=1;link=1;
        #3000;if(!admit_p)$fatal(1,"not admitted");
        // Public simulation-shell BAR API drives exact candidate controller.
        dut.pango_pcie_top.h2f(32'h40010100,16,32'hcafebabe,32'h01000000,1);
        wait(ws==1);#100;
        if(aws!=1 || bs!=0 || !bready)$fatal(1,"pending B fixture");
        case(mode)
          0: begin perst=0;#100;perst=1;end
          1: begin link=0;#100;link=1;end
          2: begin ddr=0;arst=1;#100;ddr=1;arst=0;end
        endcase
        #100;if(!fault || admit_p || admit_a)$fatal(1,"fault gate");
        if(mode<2) begin
            // PERST/link isolation must NOT reset writer or abandon accepted B.
            if(!bready)$fatal(1,"guard reset writer/pending B");
            @(negedge aclk);bvalid=1;@(negedge aclk);bvalid=0;
            #500;if(bs!=1)$fatal(1,"old B did not drain");
        end else begin
            // Actual DDR reset destroys state. No fake B drain/recovery claim.
            if(bready)$fatal(1,"DDR fixture state did not reset");
        end
        // New BAR command cannot use an old B credit, even after local resets.
        dut.pango_pcie_top.h2f(32'h40010100,16,32'hdeadbeef,32'h01000000,1);
        #3000;
        if(aws!=1 || ws!=1 || admit_p || !fault)$fatal(1,"new command after fault");
        $display("FIFO_FAULT_PASS mode=%0d aws=%0d ws=%0d bs=%0d",mode,aws,ws,bs);
        $finish;
    end
    initial begin #50000;$fatal(1,"FIFO watchdog");end
endmodule
