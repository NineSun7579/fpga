`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_word_to_axis4_adapter.sv
 * @brief M3-B 128-bit 到 4-byte AXIS staging adapter 自检。
 *
 * @details
 * 通过公开端口检查字节顺序、4-bit keep、末 beat、事件位置和背压；不验证
 * PCIe TLP、DDR3 事务或主机内存协议。
 */
module tb_rgb565_word_to_axis4_adapter;
    logic rst_n = 1'b0;
    logic clk = 1'b0;
    logic in_valid = 1'b0;
    logic in_ready;
    logic [127:0] in_data = 128'h0;
    logic [15:0] in_keep = 16'h0;
    logic in_frame_start = 1'b0;
    logic in_line_start = 1'b0;
    logic in_line_end = 1'b0;
    logic in_frame_end = 1'b0;
    logic in_protocol_error = 1'b0;
    logic out_valid;
    logic out_ready = 1'b1;
    logic [127:0] out_data;
    logic [3:0] out_keep;
    logic out_last;
    logic [7:0] out_user;
    int unsigned beat_count;
    int unsigned control_count;

    rgb565_word_to_axis4_adapter dut (.*);
    always #5ns clk = ~clk;

    always @(posedge clk) begin
        #1ns;
        if (out_valid && out_ready) begin
            case (beat_count)
                0: if (out_data[31:0] !== 32'h04030201 || out_keep !== 4'hf || out_last || out_user[1:0] !== 2'b11) $fatal(1, "Full beat 0 mismatch");
                1: if (out_data[31:0] !== 32'h08070605 || out_keep !== 4'hf || out_last || out_user[1:0] !== 2'b00) $fatal(1, "Full beat 1 mismatch");
                2: if (out_data[31:0] !== 32'h0c0b0a09 || out_keep !== 4'hf || out_last || out_user[1:0] !== 2'b00) $fatal(1, "Full beat 2 mismatch");
                3: if (out_data[31:0] !== 32'h100f0e0d || out_keep !== 4'hf || !out_last || out_user[2] !== 1'b1 || out_user[3] !== 1'b1) $fatal(1, "Full beat 3 mismatch");
                4: if (out_data[31:0] !== 32'h0000bbaa || out_keep !== 4'h3 || !out_last || out_user[2] !== 1'b1 || out_user[4] !== 1'b1) $fatal(1, "Partial beat mismatch");
                default: begin
                    if (out_keep !== 4'h0 || !out_last || out_user[3] !== 1'b1) $fatal(1, "Control beat mismatch");
                    control_count = control_count + 1;
                end
            endcase
            beat_count = beat_count + 1;
        end
    end

    task automatic drive_word(input logic [127:0] data, input logic [15:0] keep,
                               input logic frame_start_value, input logic line_start_value,
                               input logic line_end_value, input logic frame_end_value,
                               input logic protocol_error_value);
        begin
            while (!in_ready) @(posedge clk);
            in_data = data; in_keep = keep; in_frame_start = frame_start_value;
            in_line_start = line_start_value; in_line_end = line_end_value;
            in_frame_end = frame_end_value; in_protocol_error = protocol_error_value;
            in_valid = 1'b1;
            @(posedge clk);
            in_valid = 1'b0; in_data = 128'h0; in_keep = 16'h0;
            in_frame_start = 1'b0; in_line_start = 1'b0; in_line_end = 1'b0;
            in_frame_end = 1'b0; in_protocol_error = 1'b0;
        end
    endtask

    initial begin
        #20us;
        $fatal(1, "M3-B adapter test timeout");
    end

    initial begin
        beat_count = 0; control_count = 0;
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        drive_word(128'h100f0e0d0c0b0a090807060504030201, 16'hffff, 1'b1, 1'b1, 1'b1, 1'b1, 1'b0);
        out_ready = 1'b0; repeat (2) @(posedge clk); out_ready = 1'b1;
        drive_word(128'h0000bbaa, 16'h0003, 1'b0, 1'b0, 1'b1, 1'b0, 1'b1);
        repeat (2) @(posedge clk);
        drive_word(128'h0, 16'h0000, 1'b0, 1'b0, 1'b0, 1'b1, 1'b0);
        repeat (2) @(posedge clk);
        if (beat_count != 6 || control_count != 1) $fatal(1, "Count mismatch: beats=%0d controls=%0d", beat_count, control_count);
        $display("INFO: M3-B staging beat order, keep, events and backpressure verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
