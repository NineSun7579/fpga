`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_committed_pcie_mwr_path.sv
 * @brief 验证帧提交决策到 PCIe MWR 请求的板级无关组合切片。
 *
 * @details
 * 先在读侧存在待发送记录时提交错误帧，确认只产生 drop 事件且不泄漏 MWR；
 * 随后提交正常帧并检查地址。最后在 MWR 等待确认时复位，验证旧请求和
 * 读窗口被清除，复位后的新帧从基地址重新开始。
 */
module tb_rgb565_axis4_committed_pcie_mwr_path;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        commit_valid = 1'b0;
    logic        commit_ready;
    logic [3:0]  commit_keep = 4'h0;
    logic        commit_frame_end = 1'b0;
    logic        commit_protocol_error = 1'b0;
    logic        read_valid = 1'b0;
    logic        read_ready;
    logic [31:0] read_data = 32'h0;
    logic [3:0]  read_keep = 4'h0;
    logic        read_last = 1'b0;
    logic        read_frame_end = 1'b0;
    logic        read_protocol_error = 1'b0;
    logic        drop_frame_pulse;
    logic        mwr32_req;
    logic        mwr32_req_ack = 1'b0;
    logic [9:0]  req_length;
    logic [63:0] req_addr;
    logic [31:0] req_data;
    logic [3:0]  req_keep;
    logic        cross_4kb_boundary;
    logic        req_last;
    logic        req_frame_end;
    logic        req_protocol_error;
    logic        busy;
    integer      drop_count = 0;

    rgb565_axis4_committed_pcie_mwr_path #(
        .BASE_ADDR(64'h0000_0000_0000_2000)
    ) dut (.*);

    always #5ns clk = ~clk;

    always @(posedge clk) begin
        #1ns;
        if (drop_frame_pulse)
            drop_count = drop_count + 1;
    end

    initial begin
        #10us;
        $fatal(1, "committed PCIe MWR path timeout");
    end

    task automatic send_commit_record(input logic [3:0] keep,
                                      input logic frame_end,
                                      input logic protocol_error);
        begin
            while (!commit_ready)
                @(posedge clk);
            @(negedge clk);
            commit_keep = keep;
            commit_frame_end = frame_end;
            commit_protocol_error = protocol_error;
            commit_valid = 1'b1;
            @(posedge clk);
            #1ns;
            commit_valid = 1'b0;
            commit_keep = 4'h0;
            commit_frame_end = 1'b0;
            commit_protocol_error = 1'b0;
        end
    endtask

    task automatic send_read_record(input logic [31:0] data,
                                    input logic [3:0] keep,
                                    input logic last,
                                    input logic frame_end,
                                    input logic protocol_error,
                                    input logic [63:0] expected_addr);
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
            @(posedge clk);
            #1ns;
            read_valid = 1'b0;
            read_data = 32'h0;
            read_keep = 4'h0;
            read_last = 1'b0;
            read_frame_end = 1'b0;
            read_protocol_error = 1'b0;

            wait (mwr32_req);
            #1ns;
            if (!busy || req_length !== 10'd0 || req_addr !== expected_addr ||
                req_data !== data || req_keep !== keep || req_last !== last ||
                req_frame_end !== frame_end || req_protocol_error !== protocol_error ||
                cross_4kb_boundary)
                $fatal(1, "committed PCIe request mismatch: addr=%h expected=%h data=%h keep=%h last=%b frame=%b error=%b",
                       req_addr, expected_addr, req_data, req_keep, req_last,
                       req_frame_end, req_protocol_error);
            mwr32_req_ack = 1'b1;
            @(posedge clk);
            #1ns;
            mwr32_req_ack = 1'b0;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        @(negedge clk);
        read_data = 32'hdeadbeef;
        read_keep = 4'hf;
        read_last = 1'b1;
        read_frame_end = 1'b1;
        read_protocol_error = 1'b1;
        read_valid = 1'b1;
        send_commit_record(4'hf, 1'b0, 1'b0);
        send_commit_record(4'h0, 1'b1, 1'b1);
        repeat (3) @(posedge clk);
        #1ns;
        if (drop_count != 1 || mwr32_req || read_ready)
            $fatal(1, "invalid frame was not isolated: drops=%0d req=%b read_ready=%b",
                   drop_count, mwr32_req, read_ready);
        @(negedge clk);
        read_valid = 1'b0;
        read_data = 32'h0;
        read_keep = 4'h0;
        read_last = 1'b0;
        read_frame_end = 1'b0;
        read_protocol_error = 1'b0;

        send_commit_record(4'hf, 1'b0, 1'b0);
        send_commit_record(4'h0, 1'b1, 1'b0);
        wait (read_ready);
        send_read_record(32'h44332211, 4'hf, 1'b1, 1'b0, 1'b0,
                         64'h0000_0000_0000_2000);
        send_read_record(32'h00000000, 4'h0, 1'b1, 1'b1, 1'b0,
                         64'h0000_0000_0000_2004);

        repeat (2) @(posedge clk);
        #1ns;
        if (read_ready || busy || mwr32_req || drop_count != 1)
            $fatal(1, "committed path did not close cleanly");

        send_commit_record(4'hf, 1'b0, 1'b0);
        send_commit_record(4'h0, 1'b1, 1'b0);
        wait (read_ready);
        @(negedge clk);
        read_data = 32'h88776655;
        read_keep = 4'hf;
        read_last = 1'b1;
        read_valid = 1'b1;
        @(posedge clk);
        #1ns;
        read_valid = 1'b0;
        read_data = 32'h0;
        read_keep = 4'h0;
        read_last = 1'b0;
        wait (mwr32_req);
        #1ns;
        if (!busy || req_addr !== 64'h0000_0000_0000_2004)
            $fatal(1, "runtime-reset precondition request mismatch");
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (mwr32_req || busy || read_ready || drop_frame_pulse)
            $fatal(1, "runtime reset did not clear request and read window");
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        send_commit_record(4'hf, 1'b0, 1'b0);
        send_commit_record(4'h0, 1'b1, 1'b0);
        wait (read_ready);
        send_read_record(32'h04030201, 4'hf, 1'b1, 1'b0, 1'b0,
                         64'h0000_0000_0000_2000);
        send_read_record(32'h00000000, 4'h0, 1'b1, 1'b1, 1'b0,
                         64'h0000_0000_0000_2004);

        $display("INFO: invalid isolation, committed MWR, and runtime reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
