`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_frame_readout_gate.sv
 * @brief 验证已提交帧才允许进入 PCIe MWR 输入流。
 *
 * @details
 * 测试覆盖已提交帧的记录透传、下游背压保持、作废帧面对待发送读记录时
 * 仍只产生一次 drop 事件，以及运行中复位关闭已打开的读窗口。
 */
module tb_rgb565_axis4_frame_readout_gate;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        desc_valid = 1'b0;
    logic        desc_ready;
    logic        desc_committed = 1'b0;
    logic        read_valid = 1'b0;
    logic        read_ready;
    logic [31:0] read_data = 32'h0;
    logic [3:0]  read_keep = 4'h0;
    logic        read_last = 1'b0;
    logic        read_frame_end = 1'b0;
    logic        read_protocol_error = 1'b0;
    logic        out_valid;
    logic        out_ready = 1'b0;
    logic [31:0] out_data;
    logic [3:0]  out_keep;
    logic        out_last;
    logic        out_frame_end;
    logic        out_protocol_error;
    logic        drop_frame_pulse;

    rgb565_axis4_frame_readout_gate dut (.*);
    always #5ns clk = ~clk;

    initial begin
        #5us;
        $fatal(1, "frame readout gate timeout");
    end

    task automatic submit_descriptor(input logic committed);
        begin
            while (!desc_ready)
                @(posedge clk);
            @(negedge clk);
            desc_committed = committed;
            desc_valid = 1'b1;
            @(posedge clk);
            #1ns;
            desc_valid = 1'b0;
            desc_committed = 1'b0;
        end
    endtask

    task automatic transfer_record(input logic [31:0] data,
                                   input logic [3:0] keep,
                                   input logic last,
                                   input logic frame_end,
                                   input logic protocol_error);
        begin
            while (!read_ready)
                @(posedge clk);
            @(negedge clk);
            read_data = data;
            read_keep = keep;
            read_last = last;
            read_frame_end = frame_end;
            read_protocol_error = protocol_error;
            read_valid = 1'b1;
            #1ns;
            if (!out_valid || !read_ready || out_data !== data || out_keep !== keep ||
                out_last !== last || out_frame_end !== frame_end ||
                out_protocol_error !== protocol_error)
                $fatal(1, "committed frame readout mismatch");
            @(posedge clk);
            #1ns;
            read_valid = 1'b0;
            read_data = 32'h0;
            read_keep = 4'h0;
            read_last = 1'b0;
            read_frame_end = 1'b0;
            read_protocol_error = 1'b0;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        out_ready = 1'b1;

        submit_descriptor(1'b1);
        transfer_record(32'h11223344, 4'hf, 1'b1, 1'b0, 1'b0);
        transfer_record(32'h00000000, 4'h0, 1'b1, 1'b1, 1'b0);
        @(posedge clk);
        #1ns;
        if (out_valid)
            $fatal(1, "committed frame readout did not close at frame end");

        @(negedge clk);
        read_data = 32'hdeadbeef;
        read_keep = 4'hf;
        read_last = 1'b1;
        read_frame_end = 1'b1;
        read_protocol_error = 1'b1;
        read_valid = 1'b1;
        submit_descriptor(1'b0);
        #1ns;
        if (!drop_frame_pulse || read_ready || out_valid)
            $fatal(1, "invalid frame leaked a pending read record");
        @(posedge clk);
        #1ns;
        if (drop_frame_pulse || read_ready || out_valid)
            $fatal(1, "invalid frame drop event was not one cycle");
        @(negedge clk);
        read_valid = 1'b0;
        read_data = 32'h0;
        read_keep = 4'h0;
        read_last = 1'b0;
        read_frame_end = 1'b0;
        read_protocol_error = 1'b0;

        submit_descriptor(1'b1);
        out_ready = 1'b0;
        @(negedge clk);
        read_data = 32'haabbccdd;
        read_keep = 4'h3;
        read_last = 1'b1;
        read_frame_end = 1'b1;
        read_protocol_error = 1'b0;
        read_valid = 1'b1;
        repeat (2) @(posedge clk);
        #1ns;
        if (!out_valid || read_ready || out_data !== 32'haabbccdd || out_keep !== 4'h3 ||
            !out_last || !out_frame_end)
            $fatal(1, "readout fields were not held under backpressure");
        out_ready = 1'b1;
        @(posedge clk);
        #1ns;
        read_valid = 1'b0;
        read_data = 32'h0;
        read_keep = 4'h0;
        read_last = 1'b0;
        read_frame_end = 1'b0;

        submit_descriptor(1'b1);
        out_ready = 1'b1;
        @(negedge clk);
        read_data = 32'h55667788;
        read_keep = 4'hf;
        read_valid = 1'b1;
        #1ns;
        if (!out_valid || !read_ready)
            $fatal(1, "reset precondition did not open committed read window");
        rst_n = 1'b0;
        #1ns;
        if (read_ready || out_valid || drop_frame_pulse || !desc_ready)
            $fatal(1, "runtime reset did not close readout gate");
        read_valid = 1'b0;
        read_data = 32'h0;
        read_keep = 4'h0;
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        #1ns;
        if (read_ready || out_valid || drop_frame_pulse)
            $fatal(1, "readout gate reopened without a post-reset descriptor");

        $display("INFO: committed readout, invalid isolation, backpressure, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
