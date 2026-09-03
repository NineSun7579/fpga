`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_pcie_mwr_path.sv
 * @brief 验证规范化 staging→PCIe MWR 请求路径的串接行为。
 */
module tb_rgb565_axis4_pcie_mwr_path;
    logic rst_n=0, clk=0, in_valid=0, in_ready;
    logic [31:0] in_data=0; logic [3:0] in_keep=0; logic in_last=0;
    logic in_frame_end=0, in_protocol_error=0;
    logic mwr32_req, mwr32_req_ack=0; logic [9:0] req_length;
    logic [63:0] req_addr; logic [31:0] req_data; logic [3:0] req_keep;
    logic cross_4kb_boundary, req_last, req_frame_end, req_protocol_error, busy;
    integer accepted=0;

    rgb565_axis4_pcie_mwr_path #(.BASE_ADDR(64'h0ffc)) dut (.*);
    always #5ns clk=~clk;
    initial begin #5us; $fatal(1, "PCIe MWR path timeout"); end

    task automatic send_beat(input logic [31:0] data, input logic [3:0] keep,
                             input logic last, input logic frame_end, input logic error);
        begin
            while (!in_ready) @(posedge clk);
            @(negedge clk); in_data=data; in_keep=keep; in_last=last;
            in_frame_end=frame_end; in_protocol_error=error; in_valid=1;
            @(posedge clk); #1ns; in_valid=0;
        end
    endtask

    initial begin
        repeat(2) @(posedge clk); rst_n=1;
        send_beat(32'hdeadbeef, 4'hf, 0, 0, 0);
        @(posedge clk); #1ns;
        if (!busy || !mwr32_req || req_addr !== 64'h0ffc || req_length !== 1 ||
            req_data !== 32'hdeadbeef || req_keep !== 4'hf || cross_4kb_boundary ||
            req_last || req_frame_end || req_protocol_error)
            $fatal(1, "PCIe MWR path first request mismatch");

        // 第一条请求等待 ack 时预取下一条记录，当前请求的全部字段仍必须保持。
        send_beat(32'h01020304, 4'h3, 1, 1, 1);
        repeat(2) begin @(posedge clk); #1ns;
            if (req_addr !== 64'h0ffc || req_data !== 32'hdeadbeef ||
                req_keep !== 4'hf || req_last || req_frame_end ||
                req_protocol_error || !mwr32_req)
                $fatal(1, "PCIe MWR path request was not held");
        end
        mwr32_req_ack=1; @(posedge clk); #1ns; mwr32_req_ack=0;
        @(posedge clk); #1ns;
        if (!busy || req_addr !== 64'h1000 || req_length !== 1 || req_keep !== 4'h3 ||
            !req_last || !req_frame_end || !req_protocol_error || cross_4kb_boundary)
            $fatal(1, "PCIe MWR path second request mismatch: busy=%b addr=%h len=%0d data=%h keep=%h last=%b frame=%b err=%b cross=%b",
                   busy, req_addr, req_length, req_data, req_keep, req_last,
                   req_frame_end, req_protocol_error, cross_4kb_boundary);
        mwr32_req_ack=1; @(posedge clk); #1ns; mwr32_req_ack=0;
        send_beat(32'h00000000, 4'h0, 1, 1, 0);
        repeat(2) @(posedge clk);
        if (busy || mwr32_req)
            $fatal(1, "Zero-keep control record must complete without PCIe request");
        $display("INFO: normalized staging to PCIe MWR request path verified");
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
