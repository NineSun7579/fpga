`timescale 1ns/1ps
`default_nettype none

/** @file tb_rgb565_axis4_mwr_descriptor.sv */
module tb_rgb565_axis4_mwr_descriptor;
    logic rst_n=0, clk=0, in_valid=0, in_ready;
    logic [31:0] in_data=0; logic [3:0] in_keep=0; logic in_last=0;
    logic in_frame_end=0, in_protocol_error=0;
    logic req_valid, req_ready=0; logic [63:0] req_addr;
    logic [9:0] req_length_dw; logic [31:0] req_data;
    logic [3:0] req_keep; logic req_last, req_frame_end, req_protocol_error;
    logic req_cross_4kb_boundary;
    int unsigned count;
    rgb565_axis4_mwr_descriptor #(.BASE_ADDR(64'h0000_0000_0000_0ffc)) dut (.*);
    always #5ns clk=~clk;

    task automatic send(input logic [31:0] data, input logic [3:0] keep,
                        input logic last_value); begin
        while (!in_ready) @(posedge clk);
        in_data=data; in_keep=keep; in_last=last_value; in_valid=1'b1;
        @(posedge clk); in_valid=1'b0; in_last=1'b0; in_keep=4'd0;
    end endtask

    always @(posedge clk) begin
        if (req_valid && req_ready) begin
            if (count == 0 && (req_addr !== 64'hffc || req_data !== 32'h11223344 ||
                req_keep !== 4'hf || req_length_dw !== 10'd1 ||
                req_cross_4kb_boundary))
                $fatal(1, "First request mismatch");
            if (count == 1 && (req_addr !== 64'h1000 || req_keep !== 4'h3 ||
                req_length_dw !== 10'd1 || !req_last || !req_frame_end))
                $fatal(1, "Second request mismatch");
            count=count+1;
        end
    end

    initial begin
        #5us; $fatal(1, "MWR descriptor timeout");
    end
    initial begin
        count=0; repeat(2) @(posedge clk); rst_n=1;
        send(32'h11223344,4'hf,1'b0);
        req_ready=1'b1; @(posedge clk);
        in_frame_end=1'b1; send(32'haabbccdd,4'h3,1'b1); in_frame_end=1'b0;
        send(32'h00000000,4'h0,1'b1);
        repeat(3) @(posedge clk);
        if (count != 2) $fatal(1, "Request count mismatch: %0d", count);
        if (req_valid || req_addr !== 64'h1002)
            $fatal(1, "Zero-keep control record must not create MWR or advance address");
        $display("INFO: normalized MWR requests verified");
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
