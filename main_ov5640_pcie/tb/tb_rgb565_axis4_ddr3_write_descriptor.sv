`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_ddr3_write_descriptor.sv
 * @brief 验证规范化 DDR3 单 beat 写记录的握手与地址合同。
 *
 * 本测试只验证板级无关记录层，不假设厂商 DDR3 控制器的地址单位、
 * 初始化时序或 burst 完成语义。
 */
module tb_rgb565_axis4_ddr3_write_descriptor;
    logic rst_n=0, clk=0, in_valid=0, in_ready;
    logic [31:0] in_data=0; logic [3:0] in_keep=0; logic in_last=0;
    logic in_frame_end=0, in_protocol_error=0, write_valid, write_ready=0;
    logic [27:0] write_addr; logic [3:0] write_awlen;
    logic [127:0] write_data; logic [15:0] write_strb;
    logic write_last, write_frame_end, write_protocol_error;
    rgb565_axis4_ddr3_write_descriptor #(.BASE_ADDR(28'h12), .ADDR_STEP(28'h4)) dut (.*);
    always #5ns clk=~clk;
    initial begin #5us; $fatal(1, "DDR3 write descriptor timeout"); end
    task automatic drive_record(
        input logic [31:0] data,
        input logic [3:0] keep,
        input logic last,
        input logic frame_end,
        input logic protocol_error
    );
        begin
            @(posedge clk);
            in_data=data; in_keep=keep; in_last=last;
            in_frame_end=frame_end; in_protocol_error=protocol_error;
            in_valid=1;
            @(posedge clk); #1ns; in_valid=0;
        end
    endtask

    task automatic check_record(
        input logic [27:0] expected_addr,
        input logic [31:0] expected_data,
        input logic [15:0] expected_strb,
        input logic expected_last,
        input logic expected_frame_end,
        input logic expected_protocol_error
    );
        begin
            if (!write_valid || write_addr !== expected_addr || write_awlen !== 0 ||
                write_data !== {96'd0, expected_data} || write_strb !== expected_strb ||
                write_last !== expected_last || write_frame_end !== expected_frame_end ||
                write_protocol_error !== expected_protocol_error || in_ready)
                $fatal(1, "DDR3 normalized record mismatch");
        end
    endtask

    initial begin
        repeat(2) @(posedge clk); rst_n=1;
        drive_record(32'hcafebabe, 4'h7, 1, 1, 0);
        check_record(28'h12, 32'hcafebabe, 16'h0007, 1, 1, 0);
        repeat(2) begin @(posedge clk); #1ns; if (!write_valid || write_data !== 128'h000000000000000000000000cafebabe) $fatal(1,"DDR3 record not held"); end
        write_ready=1; @(posedge clk); #1ns;
        if (write_valid || write_addr !== 28'h16) $fatal(1, "DDR3 record release mismatch");

        drive_record(32'h11223344, 4'h0, 1, 1, 1);
        check_record(28'h16, 32'h11223344, 16'h0000, 1, 1, 1);
        write_ready=0;
        repeat(2) begin
            @(posedge clk); #1ns;
            check_record(28'h16, 32'h11223344, 16'h0000, 1, 1, 1);
        end
        write_ready=1; @(posedge clk); #1ns;
        if (write_valid || write_addr !== 28'h1a) $fatal(1, "DDR3 second record release mismatch");

        rst_n=0; @(posedge clk); #1ns;
        if (write_valid || !in_ready || write_addr !== 28'h12)
            $fatal(1, "DDR3 reset contract mismatch");
        $display("INFO: normalized DDR3 write descriptor verified");
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
