`timescale 1ns/1ps
module tb_guard_02;
    reg free_clk=0, axi_clk=0, pcie_clk=0;
    reg run_axi=1, run_pcie=1;
    always #20 free_clk=~free_clk;
    always #4 if(run_axi) axi_clk=~axi_clk;
    always #5 if(run_pcie) pcie_clk=~pcie_clk;
    reg button_rst_n=0, perst_n=0, axi_rst=1, ddr_init_done=0;
    reg pcie_rst=1, smlh_link_up=0, rdlh_link_up=0;
    reg startup_idle_axi=1, startup_idle_pcie=1;
    wire fault,runtime_active,reconfiguration_required,admit_axi,admit_pcie,fault_axi,fault_pcie;
    fpga_v8_reset_fault_guard_02 #(.ALIVE_LIMIT(64),.QUALIFY_CYCLES(8)) dut(.*);
    integer mode=0;
    initial begin
        if (!$value$plusargs("MODE=%d",mode)) mode=0;
        #103; button_rst_n=1;perst_n=1;axi_rst=0;ddr_init_done=1;
        pcie_rst=0;smlh_link_up=1;rdlh_link_up=1;
        wait(admit_axi && admit_pcie);
        // Deliberately put short loss pulses strictly between free_clk edges.
        @(negedge free_clk); #3;
        case(mode)
        0: begin perst_n=0; #2; perst_n=1; end
        1: begin ddr_init_done=0; #2; ddr_init_done=1; end
        2: begin smlh_link_up=0; #2; smlh_link_up=1; end
        3: begin axi_rst=1; #2; axi_rst=0; end
        4: begin pcie_rst=1; #2; pcie_rst=0; end
        5: begin button_rst_n=0; #2; button_rst_n=1; end
        6: run_axi=0;
        7: run_pcie=0;
        8: begin run_axi=0; run_pcie=0; perst_n=0; #2; perst_n=1; end
        endcase
        #4000;
        if(!fault || admit_axi || admit_pcie) $fatal(1,"fault did not latch / admission reopened");
        run_axi=1;run_pcie=1;
        button_rst_n=0; #80; button_rst_n=1;
        #4000;
        if(!fault || !reconfiguration_required || admit_axi || admit_pcie)
            $fatal(1,"runtime button restored authority");
        if(!fault_axi || !fault_pcie) $fatal(1,"fault readback missing");
        $display("GUARD02_PASS mode=%0d",mode); $finish;
    end
    initial begin #20000; $fatal(1,"timeout"); end
endmodule
