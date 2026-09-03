`timescale 1ns/1ps
`default_nettype none

/** @file tb_rgb565_axis4_pcie_mwr_bridge.sv */
module tb_rgb565_axis4_pcie_mwr_bridge;
    logic rst_n=0, clk=0, in_valid=0, in_ready;
    logic [63:0] in_addr=0; logic [9:0] in_length_dw=10'd1;
    logic [31:0] in_data=0; logic [3:0] in_keep=0;
    logic in_cross_4kb_boundary=0, mwr32_req, mwr32_req_ack=0;
    logic in_last=0, in_frame_end=0, in_protocol_error=0;
    logic [9:0] req_length; logic [63:0] req_addr; logic [31:0] req_data;
    logic [3:0] req_keep; logic cross_4kb_boundary, busy;
    logic req_last, req_frame_end, req_protocol_error;
    rgb565_axis4_pcie_mwr_bridge dut (.*);
    always #5ns clk=~clk;

    initial begin
        #5us; $fatal(1, "PCIe MWR bridge timeout");
    end
    initial begin
        repeat(2) @(posedge clk); rst_n=1;
        @(posedge clk); in_addr=64'h1000; in_data=32'h12345678; in_keep=4'hf;
        in_valid=1; @(posedge clk); #1ns; in_valid=0;
        if (!busy || !mwr32_req || req_addr !== 64'h1000 || req_length !== 10'd1 ||
            req_data !== 32'h12345678 || req_keep !== 4'hf ||
            req_last || req_frame_end || req_protocol_error || in_ready !== 1'b0)
            $fatal(1, "Bridge request capture mismatch");
        in_last=1; in_frame_end=1; in_protocol_error=1;
        repeat(2) begin
            @(posedge clk); #1ns;
            if (req_addr !== 64'h1000 || req_data !== 32'h12345678 ||
                req_last || req_frame_end || req_protocol_error || !mwr32_req)
                $fatal(1, "Bridge request stability mismatch");
        end
        mwr32_req_ack=1; @(posedge clk); #1ns; mwr32_req_ack=0;
        @(posedge clk); #1ns;
        if (busy || mwr32_req) $fatal(1, "Bridge ack release mismatch");
        $display("INFO: provisional PCIe MWR bridge handshake verified");
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
