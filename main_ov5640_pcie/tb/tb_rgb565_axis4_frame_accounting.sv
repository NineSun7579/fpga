`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_frame_accounting.sv
 * @brief M3-B 帧统计描述符自检。
 *
 * @details
 * 覆盖有效 byte/beat 累计、协议错误传播、空载帧尾和描述符背压。
 */
module tb_rgb565_axis4_frame_accounting;
    logic rst_n = 1'b0, clk = 1'b0, in_valid = 1'b0, in_ready;
    logic [3:0] in_keep = 4'h0; logic [4:0] in_user = 5'h0;
    logic desc_valid, desc_ready = 1'b0; logic [31:0] desc_bytes, desc_beats;
    logic desc_protocol_error;
    int unsigned descriptors;
    rgb565_axis4_frame_accounting dut (.*);
    always #5ns clk = ~clk;

    always @(posedge clk) begin
        #1ns;
        if (desc_valid && desc_ready) begin
            if (desc_bytes !== 32'd5 || desc_beats !== 32'd2 || !desc_protocol_error) $fatal(1, "Descriptor mismatch");
            descriptors = descriptors + 1;
        end
    end

    task automatic drive_beat(input logic [3:0] keep, input logic [4:0] user);
        begin
            while (!in_ready) @(posedge clk);
            in_keep = keep; in_user = user; in_valid = 1'b1;
            @(posedge clk); in_valid = 1'b0; in_keep = 4'h0; in_user = 5'h0;
        end
    endtask

    initial begin
        #20us; $fatal(1, "M3-B frame accounting timeout");
    end

    initial begin
        descriptors = 0; repeat (2) @(posedge clk); rst_n = 1'b1;
        drive_beat(4'hf, 5'b00001); drive_beat(4'h1, 5'b10100);
        drive_beat(4'h0, 5'b01000);
        repeat (2) @(posedge clk); desc_ready = 1'b1; @(posedge clk); desc_ready = 1'b0;
        repeat (1) @(posedge clk);
        if (descriptors != 1) $fatal(1, "Descriptor count mismatch: %0d", descriptors);
        $display("INFO: M3-B frame byte/beat accounting and error propagation verified");
        $display("TEST PASS"); $finish;
    end
endmodule

`default_nettype wire
