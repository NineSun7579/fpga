`timescale 1ns/1ps
module tb_guard;
    reg free_clk=0, axi_clk=0, pcie_clk=0;
    reg run_axi=1,run_pcie=1;
    always #20 free_clk=~free_clk;
    always #7 if(run_axi) axi_clk=~axi_clk;
    always #8 if(run_pcie) pcie_clk=~pcie_clk;
    reg button=1,perst=0,ddr=0,prst=1,arst=1,sl=0,rl=0,idle=0;
    wire fault,active,reconfigure,admit_a,admit_p,fa,fp;
    integer mode;
    fpga_v8_reset_fault_guard #(.ALIVE_LIMIT(24),.QUALIFY_CYCLES(8)) dut(
        .free_clk(free_clk),.button_rst_n(button),.perst_n(perst),
        .axi_clk(axi_clk),.axi_rst(arst),.ddr_init_done(ddr),.startup_idle_axi(idle),
        .pcie_clk(pcie_clk),.pcie_rst(prst),.smlh_link_up(sl),.rdlh_link_up(rl),.startup_idle_pcie(idle),
        .fault(fault),.runtime_active(active),.reconfiguration_required(reconfigure),
        .admit_axi(admit_a),.admit_pcie(admit_p),.fault_axi(fa),.fault_pcie(fp));
    task closed;
        begin #1; if(admit_a || admit_p) $fatal(1,"admission leaked mode %0d",mode); end
    endtask
    initial begin
        if(!$value$plusargs("MODE=%d",mode)) mode=0;
        #1;button=0;#80;button=1;
        run_pcie=0;
        #80;ddr=1;arst=0;perst=1;prst=0;sl=1;rl=1;idle=1;
        #2000;closed();if(active || fault) $fatal(1,"startup stopped clock accepted/faulted");
        run_pcie=1;idle=0;
        #2000;closed();if(active) $fatal(1,"startup busy accepted");
        idle=1;#2000;
        if(!active || !admit_a || !admit_p || fault) $fatal(1,"startup did not qualify");
        case(mode)
          0: begin perst=0;#2;perst=1;end // pulse shorter than free_clk
          1: begin prst=1;#2;prst=0;end
          2: begin ddr=0;arst=1;#2;ddr=1;arst=0;end
          3: begin rl=0;#2;rl=1;end
          4: begin run_axi=0;#2000;end
          5: begin run_pcie=0;#2000;end
          6: begin button=0;#100;closed();button=1;#2000;
              if(fault || !reconfigure) $fatal(1,"button clearing/recovery policy");
              closed();$display("GUARD_PASS mode=%0d BUTTON_NO_RECOVERY",mode);$finish;end
          7: begin idle=0;#2000; // runtime busy is not reset/fault (normal ARM/capture)
              if(fault || !admit_a || !admit_p) $fatal(1,"normal active work faulted");
              $display("GUARD_PASS mode=%0d NORMAL_BUSY",mode);$finish;end
          8: begin sl=0;#2;sl=1;end
          9: begin arst=1;#2;arst=0;end
        endcase
        #200;closed();if(!fault) $fatal(1,"loss not sticky");
        run_axi=1;run_pcie=1;#3000;closed();
        if(!fault || !fa || !fp) $fatal(1,"fault did not survive return of local domains");
        // Repeated local resets cannot clear the supervisor or issue a new permit.
        arst=1;prst=1;#100;arst=0;prst=0;#2000;closed();
        if(!fault || !fa || !fp) $fatal(1,"local reset cleared supervisor");
        $display("GUARD_PASS mode=%0d STICKY",mode);$finish;
    end
    initial begin #30000;$fatal(1,"watchdog");end
endmodule
