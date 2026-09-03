`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_word_skid_buffer.sv
 * @brief 验证 camera-side word 短突发缓冲的顺序、背压保持和溢出报告。
 */
module tb_rgb565_word_skid_buffer;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        in_valid = 1'b0;
    logic [127:0] in_data = 128'h0;
    logic [15:0] in_keep = 16'h0;
    logic        in_frame_start = 1'b0;
    logic        in_line_start = 1'b0;
    logic        in_line_end = 1'b0;
    logic        in_frame_end = 1'b0;
    logic        in_protocol_error = 1'b0;
    logic        in_ready;
    logic        out_valid;
    logic        out_ready = 1'b0;
    logic [127:0] out_data;
    logic [15:0] out_keep;
    logic        out_frame_start;
    logic        out_line_start;
    logic        out_line_end;
    logic        out_frame_end;
    logic        out_protocol_error;
    logic        overflow;
    integer received = 0;

    rgb565_word_skid_buffer dut (.*);

    always #5ns clk = ~clk;
    initial begin
        #2us;
        $fatal(1, "word skid buffer timeout");
    end

    task automatic send_word(input logic [127:0] value, input logic [15:0] keep,
                             input logic frame_start, input logic frame_end);
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_data = value;
            in_keep = keep;
            in_frame_start = frame_start;
            in_frame_end = frame_end;
            @(posedge clk);
            #1ns;
            in_valid = 1'b0;
            in_frame_start = 1'b0;
            in_frame_end = 1'b0;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        // 下游暂停时，两个输入 word 必须按顺序保存。
        send_word(128'h1000, 16'hffff, 1'b1, 1'b0);
        send_word(128'h2000, 16'h000f, 1'b0, 1'b1);
        if (!in_ready)
            $display("INFO: word skid buffer is full after two words");

        // 第三个 word 不得覆盖已保存数据，同时必须记录溢出。
        send_word(128'h3000, 16'h0003, 1'b0, 1'b0);
        if (!overflow || in_ready)
            $fatal(1, "word skid overflow contract mismatch: overflow=%b ready=%b",
                   overflow, in_ready);

        out_ready = 1'b1;
        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h1000 || out_keep !== 16'hffff ||
            !out_frame_start || out_frame_end || !out_valid || !out_ready)
            $fatal(1, "first buffered word mismatch: data=%h keep=%h fs=%b fe=%b",
                   out_data, out_keep, out_frame_start, out_frame_end);
        @(posedge clk);

        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h2000 || out_keep !== 16'h000f ||
            out_frame_start || !out_frame_end || !out_valid || !out_ready)
            $fatal(1, "second buffered word mismatch: data=%h keep=%h fs=%b fe=%b",
                   out_data, out_keep, out_frame_start, out_frame_end);
        @(posedge clk);

        repeat (2) @(posedge clk);
        if (out_valid)
            $fatal(1, "word skid buffer did not drain");
        $display("INFO: word short-burst buffering and sticky overflow verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
