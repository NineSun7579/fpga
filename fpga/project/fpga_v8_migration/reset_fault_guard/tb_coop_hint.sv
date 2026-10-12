`timescale 1ns/1ps
module tb_coop_hint;
    reg clk=0;always #7 clk=~clk;
    reg rstn=0,fault=0,iv=0,bridge_busy=0,done=0;
    wire ir,cv,busy,release_valid;wire [1:0] bank0,bank1;
    reg [31:0] ar=0;reg av=0;
    wire rr,arr;wire [31:0] rd;
    fpga_v8_coop_control_axil_rfg01 dut(
        .core_clk(clk),.rst_n(rstn),.session_fault(fault),
        .input_valid(iv),.input_ready(ir),.input_raw_valid(1'b1),
        .input_src_addr(32'h01800000),.input_source_seq(32'd1),.input_generation(32'd7),
        .input_camera(3'd4),.input_camera_bank(1'b0),.input_lease_token(64'd123),
        .cmd_valid(cv),.cmd_ready(1'b1),.bridge_busy(bridge_busy),.bridge_done(done),
        .bridge_error(1'b0),.bridge_cmd_error(1'b0),.src_release_valid(release_valid),
        .src_release_ready(1'b0),.busy(busy),.bank0_state(bank0),.bank1_state(bank1),
        .s_axil_awaddr(32'b0),.s_axil_awprot(3'b0),.s_axil_awvalid(1'b0),
        .s_axil_wdata(32'b0),.s_axil_wstrb(4'b0),.s_axil_wvalid(1'b0),.s_axil_bready(1'b1),
        .s_axil_araddr(ar),.s_axil_arprot(3'b0),.s_axil_arvalid(av),.s_axil_arready(arr),
        .s_axil_rdata(rd),.s_axil_rvalid(rr),.s_axil_rready(1'b1));
    task read_word(input [31:0] address,output [31:0] value);
        begin @(negedge clk);ar=address;av=1;@(negedge clk);av=0;
            wait(rr);value=rd;@(negedge clk);end
    endtask
    reg [31:0] before_status,after_status,hint;
    initial begin
        #100;rstn=1;
        @(negedge clk);iv=1;@(negedge clk);iv=0;
        #100;bridge_busy=1;
        if(!busy || bank0!=1)$fatal(1,"cooperative busy fixture");
        read_word(4,before_status);fault=1;#100;
        read_word(4,after_status);read_word('h6c,hint);
        // STATUS bit6 is error; busy/ownership must remain byte-identical.
        if(after_status!=(before_status | 32'h40) || hint!=32'h52534647 ||
           !busy || release_valid || bank0!=1)$fatal(1,"fault hint changed active work");
        bridge_busy=0;done=1;@(negedge clk);@(negedge clk);done=0;#100;
        if(busy || bank0!=2 || !release_valid)$fatal(1,"accepted operation failed to retire normally");
        $display("COOP_HINT_PASS BUSY_PRESERVED_ACCEPTED_WORK_RETURNS_READY");$finish;
    end
    initial begin #10000;$fatal(1,"coop watchdog");end
endmodule
