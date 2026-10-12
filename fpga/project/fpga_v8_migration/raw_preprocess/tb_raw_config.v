`timescale 1ns/1ps
module tb_raw_config;
    parameter integer WIDTH = 0;
    parameter integer HEIGHT = 3;
    parameter integer OUT_HEIGHT = 5;
    parameter integer TOP_ROWS = 1;
    parameter integer FILL_VALUE = 114;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst_n = 1'b0;
    wire start_ready, busy, done, frame_error, config_error, s_ready, m_valid, m_last;
    wire [23:0] m_data;
    fpga_v8_raw_letterbox #(.WIDTH(WIDTH), .HEIGHT(HEIGHT),
        .OUT_HEIGHT(OUT_HEIGHT), .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE)) dut (
        .clk(clk), .rst_n(rst_n), .start_valid(1'b1), .start_ready(start_ready),
        .busy(busy), .done(done), .frame_error(frame_error), .config_error(config_error),
        .s_data(16'hffff), .s_valid(1'b1), .s_ready(s_ready), .s_last(1'b1),
        .m_data(m_data), .m_valid(m_valid), .m_ready(1'b1), .m_last(m_last));
    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        repeat (12) begin
            @(negedge clk);
            if (config_error !== 1'b1 || start_ready !== 1'b0 || busy !== 1'b0 ||
                s_ready !== 1'b0 || m_valid !== 1'b0 || done !== 1'b0) begin
                $display("FAIL invalid config was not rejected");
                $finish;
            end
        end
        $display("PASS tb_raw_config");
        $finish;
    end
endmodule
