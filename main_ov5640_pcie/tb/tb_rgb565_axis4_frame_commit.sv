`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_frame_commit.sv
 * @brief 验证规范化 DDR3 记录的帧提交、作废、背压和复位语义。
 *
 * @details
 * 覆盖正常帧统计、帧尾错误、前序 sticky error、描述符背压，以及运行中
 * 复位不会把旧帧计数或待消费描述符带入下一帧。
 */
module tb_rgb565_axis4_frame_commit;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        in_valid = 1'b0;
    logic        in_ready;
    logic [27:0] in_addr = 28'd0;
    logic [3:0]  in_keep = 4'h0;
    logic        in_frame_end = 1'b0;
    logic        in_protocol_error = 1'b0;
    logic        desc_valid;
    logic        desc_ready = 1'b0;
    logic [27:0] desc_start_addr;
    logic [31:0] desc_bytes;
    logic [31:0] desc_records;
    logic        desc_protocol_error;
    logic        desc_committed;

    rgb565_axis4_frame_commit dut (.*);
    always #5ns clk = ~clk;

    initial begin
        #5us;
        $fatal(1, "frame commit timeout");
    end

    task automatic send_record(input logic [27:0] addr,
                               input logic [3:0] keep,
                               input logic frame_end,
                               input logic protocol_error);
        begin
            while (!in_ready)
                @(posedge clk);
            @(negedge clk);
            in_addr = addr;
            in_keep = keep;
            in_frame_end = frame_end;
            in_protocol_error = protocol_error;
            in_valid = 1'b1;
            @(posedge clk);
            #1ns;
            in_valid = 1'b0;
            in_addr = 28'd0;
            in_keep = 4'h0;
            in_frame_end = 1'b0;
            in_protocol_error = 1'b0;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        send_record(28'd10, 4'hf, 1'b0, 1'b0);
        send_record(28'd11, 4'h3, 1'b0, 1'b0);
        send_record(28'd12, 4'h0, 1'b1, 1'b0);

        #1ns;
        if (!desc_valid || desc_start_addr !== 28'd10 ||
            desc_bytes !== 32'd6 || desc_records !== 32'd3 ||
            desc_protocol_error || !desc_committed)
            $fatal(1, "normal frame commit mismatch: valid=%b bytes=%0d records=%0d error=%b committed=%b",
                   desc_valid, desc_bytes, desc_records, desc_protocol_error, desc_committed);

        repeat (2) @(posedge clk);
        #1ns;
        if (!desc_valid || desc_start_addr !== 28'd10 ||
            desc_bytes !== 32'd6 || desc_records !== 32'd3 ||
            desc_protocol_error || !desc_committed)
            $fatal(1, "frame commit descriptor was not held under backpressure");

        desc_ready = 1'b1;
        @(posedge clk);
        #1ns;
        if (desc_valid)
            $fatal(1, "frame commit descriptor did not release");

        desc_ready = 1'b0;
        send_record(28'd20, 4'hf, 1'b0, 1'b0);
        send_record(28'd21, 4'h0, 1'b1, 1'b1);
        #1ns;
        if (!desc_valid || desc_start_addr !== 28'd20 ||
            desc_bytes !== 32'd4 || desc_records !== 32'd2 ||
            !desc_protocol_error || desc_committed)
            $fatal(1, "invalid frame commit mismatch: valid=%b bytes=%0d records=%0d error=%b committed=%b",
                   desc_valid, desc_bytes, desc_records, desc_protocol_error, desc_committed);

        desc_ready = 1'b1;
        @(posedge clk);
        #1ns;
        if (desc_valid)
            $fatal(1, "invalid frame descriptor did not release");

        desc_ready = 1'b0;
        send_record(28'd30, 4'h1, 1'b0, 1'b1);
        send_record(28'd31, 4'h0, 1'b1, 1'b0);
        #1ns;
        if (!desc_valid || desc_start_addr !== 28'd30 ||
            desc_bytes !== 32'd1 || desc_records !== 32'd2 ||
            !desc_protocol_error || desc_committed)
            $fatal(1, "sticky frame error mismatch");

        desc_ready = 1'b1;
        @(posedge clk);
        #1ns;
        if (desc_valid)
            $fatal(1, "sticky-error descriptor did not release");

        desc_ready = 1'b0;
        send_record(28'd40, 4'hf, 1'b0, 1'b1);
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (desc_valid)
            $fatal(1, "mid-frame reset did not clear descriptor state");
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        send_record(28'd50, 4'h3, 1'b1, 1'b0);
        #1ns;
        if (!desc_valid || desc_start_addr !== 28'd50 ||
            desc_bytes !== 32'd2 || desc_records !== 32'd1 ||
            desc_protocol_error || !desc_committed)
            $fatal(1, "post-reset frame inherited stale accounting state");

        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (desc_valid)
            $fatal(1, "reset did not discard pending descriptor");
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        $display("INFO: frame commit accounting, rejection, backpressure, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
