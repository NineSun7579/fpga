`timescale 1ns/1ps
`default_nettype none

/** @file tb_rgb565_axis4_ddr3_write_descriptor.sv */
module tb_rgb565_axis4_ddr3_write_descriptor;
    logic rst_n=0, clk=0, in_valid=0, in_ready;
    logic [31:0] in_data=0; logic [3:0] in_keep=0; logic in_last=0;
    logic in_frame_end=0, in_protocol_error=0, write_valid, write_ready=0;
    logic [27:0] write_addr; logic [3:0] write_awlen;
    logic [127:0] write_data; logic [15:0] write_strb;
    logic write_last, write_frame_end, write_protocol_error;
    rgb565_axis4_ddr3_write_descriptor #(.BASE_ADDR(28'h12), .ADDR_STEP(28'h4)) dut (.*);
    always #5ns clk=~clk;
    initial begin #5us; $fatal(1, "DDR3 write descriptor timeout"); end
    initial begin
        repeat(2) @(posedge clk); rst_n=1;
        @(posedge clk); in_data=32'hcafebabe; in_keep=4'h7; in_last=1;
        in_frame_end=1; in_valid=1; @(posedge clk); #1ns; in_valid=0;
        if (!write_valid || write_addr !== 28'h12 || write_awlen !== 0 ||
            write_data !== 128'h000000000000000000000000cafebabe ||
            write_strb !== 16'h0007 || !write_last || !write_frame_end || in_ready)
            $fatal(1, "DDR3 write descriptor mismatch");
        repeat(2) begin @(posedge clk); #1ns; if (!write_valid || write_data !== 128'h000000000000000000000000cafebabe) $fatal(1,"DDR3 record not held"); end
        write_ready=1; @(posedge clk); #1ns;
        if (write_valid || write_addr !== 28'h16) $fatal(1, "DDR3 record release mismatch");
        $display("INFO: normalized DDR3 write descriptor verified");
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
