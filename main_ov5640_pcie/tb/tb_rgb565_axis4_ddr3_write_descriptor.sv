`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_ddr3_write_descriptor.sv
 * @brief 验证按帧装载槽基 token 的规范化 DDR3 写记录。
 *
 * @details
 * 测试覆盖槽分配前输入背压、分配槽号/槽基保持、帧内地址推进、输出背压
 * 保持、帧尾后重新请求分配，以及超过单槽记录容量时地址夹断并强制错误。
 */
module tb_rgb565_axis4_ddr3_write_descriptor;
    logic         rst_n = 1'b0;
    logic         clk = 1'b0;
    logic         frame_alloc_valid = 1'b0;
    logic         frame_alloc_ready;
    logic         frame_alloc_slot_id = 1'b0;
    logic [27:0]  frame_alloc_base_addr = 28'd0;
    logic [31:0]  frame_alloc_record_capacity = 32'd0;
    logic         in_valid = 1'b0;
    logic         in_ready;
    logic [31:0]  in_data = 32'd0;
    logic [3:0]   in_keep = 4'd0;
    logic         in_last = 1'b0;
    logic         in_frame_end = 1'b0;
    logic         in_protocol_error = 1'b0;
    logic         write_valid;
    logic         write_ready = 1'b0;
    logic         write_slot_id;
    logic [27:0]  write_addr;
    logic [3:0]   write_awlen;
    logic [127:0] write_data;
    logic [15:0]  write_strb;
    logic         write_last;
    logic         write_frame_end;
    logic         write_protocol_error;

    rgb565_axis4_ddr3_write_descriptor #(
        .ADDR_STEP(28'd4)
    ) dut (.*);

    always #5ns clk = ~clk;

    initial begin
        #8us;
        $fatal(1, "DDR3 write descriptor timeout");
    end

    task automatic allocate_frame(input logic slot_id,
                                  input logic [27:0] base_addr);
        begin
            wait (frame_alloc_ready);
            @(negedge clk);
            frame_alloc_slot_id = slot_id;
            frame_alloc_base_addr = base_addr;
            frame_alloc_record_capacity = 32'd3;
            frame_alloc_valid = 1'b1;
            @(posedge clk);
            #1ns;
            frame_alloc_valid = 1'b0;
            frame_alloc_slot_id = 1'b0;
            frame_alloc_base_addr = 28'd0;
            frame_alloc_record_capacity = 32'd0;
        end
    endtask

    task automatic stage_record(input logic [31:0] data,
                                input logic [3:0] keep,
                                input logic last,
                                input logic frame_end,
                                input logic protocol_error);
        begin
            wait (in_ready);
            @(negedge clk);
            in_data = data;
            in_keep = keep;
            in_last = last;
            in_frame_end = frame_end;
            in_protocol_error = protocol_error;
            in_valid = 1'b1;
            @(posedge clk);
            #1ns;
            in_valid = 1'b0;
            in_data = 32'd0;
            in_keep = 4'd0;
            in_last = 1'b0;
            in_frame_end = 1'b0;
            in_protocol_error = 1'b0;
        end
    endtask

    task automatic check_and_accept(input logic expected_slot,
                                    input logic [27:0] expected_addr,
                                    input logic [31:0] expected_data,
                                    input logic [15:0] expected_strb,
                                    input logic expected_last,
                                    input logic expected_frame_end,
                                    input logic expected_error,
                                    input integer hold_cycles);
        begin
            #1ns;
            if (!write_valid || write_slot_id !== expected_slot ||
                write_addr !== expected_addr || write_awlen !== 4'd0 ||
                write_data !== {89'd0, expected_error, expected_frame_end,
                                expected_last, expected_strb[3:0], expected_data} ||
                write_strb !== {11'd0, 1'b1, expected_strb[3:0]} ||
                write_last !== expected_last ||
                write_frame_end !== expected_frame_end ||
                write_protocol_error !== expected_error || in_ready)
                $fatal(1, "DDR3 slotted write record mismatch");
            repeat (hold_cycles) begin
                @(posedge clk);
                #1ns;
                if (!write_valid || write_slot_id !== expected_slot ||
                    write_addr !== expected_addr ||
                    write_data !== {89'd0, expected_error, expected_frame_end,
                                    expected_last, expected_strb[3:0], expected_data} ||
                    write_strb !== {11'd0, 1'b1, expected_strb[3:0]} ||
                    write_last !== expected_last ||
                    write_frame_end !== expected_frame_end ||
                    write_protocol_error !== expected_error)
                    $fatal(1, "DDR3 slotted record changed under backpressure");
            end
            @(negedge clk);
            write_ready = 1'b1;
            @(posedge clk);
            #1ns;
            write_ready = 1'b0;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        #1ns;
        if (!frame_alloc_ready || in_ready || write_valid)
            $fatal(1, "writer accepted data before frame allocation");

        allocate_frame(1'b1, 28'h20);
        stage_record(32'hcafe_babe, 4'hf, 1'b0, 1'b0, 1'b0);
        check_and_accept(1'b1, 28'h20, 32'hcafe_babe, 16'h000f,
                         1'b0, 1'b0, 1'b0, 2);
        stage_record(32'h1122_3344, 4'h3, 1'b0, 1'b0, 1'b0);
        check_and_accept(1'b1, 28'h24, 32'h1122_3344, 16'h0003,
                         1'b0, 1'b0, 1'b0, 0);
        stage_record(32'h0000_0000, 4'h0, 1'b1, 1'b1, 1'b0);
        check_and_accept(1'b1, 28'h28, 32'h0000_0000, 16'h0000,
                         1'b1, 1'b1, 1'b0, 0);
        #1ns;
        if (!frame_alloc_ready || in_ready || write_valid)
            $fatal(1, "frame end did not return writer to allocation state");

        allocate_frame(1'b0, 28'h40);
        for (integer index = 0; index < 5; index = index + 1) begin
            stage_record(32'h8000_0000 + index, 4'hf, index == 4,
                         index == 4, 1'b0);
            check_and_accept(1'b0,
                             (index < 3) ? (28'h40 + index * 4) : 28'h48,
                             32'h8000_0000 + index, 16'h000f,
                             index == 4, index == 4, index >= 3,
                             (index == 3) ? 2 : 0);
        end

        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (write_valid || in_ready || !frame_alloc_ready)
            $fatal(1, "runtime reset did not clear slotted writer state");

        $display("INFO: slotted DDR3 writer allocation, capacity clamp, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
