`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_frame_read_scheduler.sv
 * @brief 验证已提交帧的顺序 DDR3 记录读命令调度。
 *
 * @details
 * 测试覆盖不可提交帧不产生读命令、命令背压保持、单 outstanding 响应配对、
 * 连续地址推进、末响应完成脉冲，以及等待响应期间的运行中复位。
 */
module tb_rgb565_axis4_frame_read_scheduler;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        desc_valid = 1'b0;
    logic        desc_ready;
    logic [27:0] desc_start_addr = 28'd0;
    logic [31:0] desc_records = 32'd0;
    logic        desc_committed = 1'b0;
    logic        read_cmd_valid;
    logic        read_cmd_ready = 1'b0;
    logic [27:0] read_cmd_addr;
    logic        read_response_accepted = 1'b0;
    logic        read_response_frame_end = 1'b0;
    logic        read_response_ready;
    logic        read_response_frame_end_normalized;
    logic        read_response_protocol_error;
    logic        frame_done_pulse;
    logic        frame_fault_pulse;
    logic        active;

    rgb565_axis4_frame_read_scheduler #(
        .ADDR_STEP(28'd4)
    ) dut (.*);

    always #5ns clk = ~clk;

    initial begin
        #5us;
        $fatal(1, "frame read scheduler timeout");
    end

    task automatic submit_descriptor(input logic [27:0] start_addr,
                                     input logic [31:0] records,
                                     input logic committed);
        begin
            while (!desc_ready)
                @(posedge clk);
            @(negedge clk);
            desc_start_addr = start_addr;
            desc_records = records;
            desc_committed = committed;
            desc_valid = 1'b1;
            @(posedge clk);
            #1ns;
            desc_valid = 1'b0;
            desc_start_addr = 28'd0;
            desc_records = 32'd0;
            desc_committed = 1'b0;
        end
    endtask

    task automatic accept_command(input logic [27:0] expected_addr,
                                  input logic final_response);
        begin
            wait (read_cmd_valid);
            #1ns;
            if (read_cmd_addr !== expected_addr)
                $fatal(1, "read command address mismatch: got=%0d expected=%0d",
                       read_cmd_addr, expected_addr);
            read_cmd_ready = 1'b1;
            @(posedge clk);
            #1ns;
            read_cmd_ready = 1'b0;
            if (read_cmd_valid)
                $fatal(1, "scheduler issued a second command with one response outstanding");
            if (!read_response_ready)
                $fatal(1, "scheduler did not enable the outstanding response");

            @(negedge clk);
            read_response_accepted = 1'b1;
            read_response_frame_end = final_response;
            #1ns;
            if (read_response_frame_end_normalized !== final_response ||
                read_response_protocol_error)
                $fatal(1, "normal response metadata was not preserved");
            @(posedge clk);
            #1ns;
            read_response_accepted = 1'b0;
            read_response_frame_end = 1'b0;
            if (frame_done_pulse !== final_response)
                $fatal(1, "frame completion pulse mismatch at address %0d", expected_addr);
            if (frame_fault_pulse)
                $fatal(1, "normal response produced frame fault at address %0d", expected_addr);
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        submit_descriptor(28'd4, 32'd2, 1'b0);
        repeat (2) @(posedge clk);
        #1ns;
        if (read_cmd_valid || active || frame_done_pulse)
            $fatal(1, "uncommitted descriptor produced scheduler activity");

        submit_descriptor(28'd10, 32'd3, 1'b1);
        #1ns;
        if (!read_cmd_valid || read_cmd_addr !== 28'd10 || !active)
            $fatal(1, "committed descriptor did not open scheduler");

        repeat (2) @(posedge clk);
        #1ns;
        if (!read_cmd_valid || read_cmd_addr !== 28'd10)
            $fatal(1, "read command was not held under backpressure");

        accept_command(28'd10, 1'b0);
        accept_command(28'd14, 1'b0);
        accept_command(28'd18, 1'b1);
        @(posedge clk);
        #1ns;
        if (active || read_cmd_valid || frame_done_pulse || !desc_ready)
            $fatal(1, "scheduler did not return idle after final response");

        submit_descriptor(28'd20, 32'd2, 1'b1);
        wait (read_cmd_valid);
        read_cmd_ready = 1'b1;
        @(posedge clk);
        #1ns;
        read_cmd_ready = 1'b0;
        if (!active || read_cmd_valid)
            $fatal(1, "runtime-reset precondition did not create outstanding read");
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (active || read_cmd_valid || frame_done_pulse || !desc_ready)
            $fatal(1, "runtime reset did not clear scheduler state");
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        submit_descriptor(28'd30, 32'd1, 1'b1);
        accept_command(28'd30, 1'b1);

        submit_descriptor(28'd40, 32'd0, 1'b1);
        #1ns;
        if (active || read_cmd_valid || !frame_done_pulse || !frame_fault_pulse)
            $fatal(1, "zero-record committed descriptor did not fault-complete");
        @(posedge clk);

        submit_descriptor(28'd50, 32'd3, 1'b1);
        wait (read_cmd_valid);
        read_cmd_ready = 1'b1;
        @(posedge clk);
        #1ns;
        read_cmd_ready = 1'b0;
        @(negedge clk);
        read_response_frame_end = 1'b1;
        read_response_accepted = 1'b1;
        #1ns;
        if (!read_response_ready || !read_response_frame_end_normalized ||
            !read_response_protocol_error)
            $fatal(1, "early frame end was not normalized as a protocol fault");
        @(posedge clk);
        #1ns;
        read_response_accepted = 1'b0;
        read_response_frame_end = 1'b0;
        if (active || !frame_done_pulse || !frame_fault_pulse)
            $fatal(1, "early frame end did not terminate the scheduler");
        @(posedge clk);

        submit_descriptor(28'd60, 32'd1, 1'b1);
        wait (read_cmd_valid);
        read_cmd_ready = 1'b1;
        @(posedge clk);
        #1ns;
        read_cmd_ready = 1'b0;
        @(negedge clk);
        read_response_accepted = 1'b1;
        #1ns;
        if (!read_response_frame_end_normalized || !read_response_protocol_error)
            $fatal(1, "missing final frame end was not repaired as a protocol fault");
        @(posedge clk);
        #1ns;
        read_response_accepted = 1'b0;
        if (active || !frame_done_pulse || !frame_fault_pulse)
            $fatal(1, "missing final frame end did not terminate the scheduler");
        @(posedge clk);

        submit_descriptor(28'd70, 32'd1, 1'b1);
        wait (read_cmd_valid);
        @(negedge clk);
        read_cmd_ready = 1'b1;
        read_response_accepted = 1'b1;
        read_response_frame_end = 1'b1;
        #1ns;
        if (!read_response_ready)
            $fatal(1, "zero-latency response was not accepted with its command");
        @(posedge clk);
        #1ns;
        read_cmd_ready = 1'b0;
        read_response_accepted = 1'b0;
        read_response_frame_end = 1'b0;
        if (active || read_cmd_valid || !frame_done_pulse || frame_fault_pulse)
            $fatal(1, "zero-latency final response did not complete cleanly");

        $display("INFO: scheduler pairing, frame-end recovery, zero-record, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
