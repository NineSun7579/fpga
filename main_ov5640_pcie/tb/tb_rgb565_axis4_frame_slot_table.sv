`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_frame_slot_table.sv
 * @brief 验证双槽分配、提交排队和带槽回收语义。
 *
 * @details
 * 测试覆盖分配描述符背压保持、两个槽同时占用、两个 committed 描述符排队、
 * FIFO 顺序、错误 read-done 不误释放、正常完成后重分配、错误帧立即释放、
 * 非法 commit fault，以及运行中复位清空槽状态和队列。
 */
module tb_rgb565_axis4_frame_slot_table;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        write_alloc_valid;
    logic        write_alloc_ready = 1'b0;
    logic        write_alloc_slot_id;
    logic [27:0] write_alloc_base_addr;
    logic [31:0] write_alloc_record_capacity;
    logic        commit_valid = 1'b0;
    logic        commit_ready;
    logic        commit_slot_id = 1'b0;
    logic [27:0] commit_start_addr = 28'd0;
    logic [31:0] commit_bytes = 32'd0;
    logic [31:0] commit_records = 32'd0;
    logic        commit_protocol_error = 1'b0;
    logic        commit_committed = 1'b0;
    logic        read_desc_valid;
    logic        read_desc_ready = 1'b0;
    logic        read_desc_slot_id;
    logic [27:0] read_desc_start_addr;
    logic [31:0] read_desc_bytes;
    logic [31:0] read_desc_records;
    logic        read_desc_protocol_error;
    logic        read_done_pulse = 1'b0;
    logic        read_done_slot_id = 1'b0;
    logic        drop_frame_pulse;
    logic        drop_slot_id;
    logic        fault_pulse;

    rgb565_axis4_frame_slot_table #(
        .SLOT0_BASE_ADDR(28'd100),
        .SLOT1_BASE_ADDR(28'd200),
        .SLOT_RECORD_CAPACITY(32'd16)
    ) dut (.*);

    always #5ns clk = ~clk;

    initial begin
        #8us;
        $fatal(1, "frame slot table timeout");
    end

    task automatic accept_allocation(input logic expected_slot,
                                     input logic [27:0] expected_base,
                                     input integer hold_cycles);
        logic held_slot;
        logic [27:0] held_base;
        begin
            wait (write_alloc_valid);
            #1ns;
            if (write_alloc_slot_id !== expected_slot ||
                write_alloc_base_addr !== expected_base ||
                write_alloc_record_capacity !== 32'd16)
                $fatal(1, "allocation mismatch: slot=%b base=%0d",
                       write_alloc_slot_id, write_alloc_base_addr);
            held_slot = write_alloc_slot_id;
            held_base = write_alloc_base_addr;
            repeat (hold_cycles) begin
                @(posedge clk);
                #1ns;
                if (!write_alloc_valid || write_alloc_slot_id !== held_slot ||
                    write_alloc_base_addr !== held_base)
                    $fatal(1, "allocation changed under backpressure");
            end
            @(negedge clk);
            write_alloc_ready = 1'b1;
            @(posedge clk);
            #1ns;
            write_alloc_ready = 1'b0;
        end
    endtask

    task automatic submit_commit(input logic slot_id,
                                 input logic [27:0] start_addr,
                                 input logic [31:0] bytes,
                                 input logic [31:0] records,
                                 input logic protocol_error,
                                 input logic committed);
        begin
            @(negedge clk);
            commit_slot_id = slot_id;
            commit_start_addr = start_addr;
            commit_bytes = bytes;
            commit_records = records;
            commit_protocol_error = protocol_error;
            commit_committed = committed;
            commit_valid = 1'b1;
            do begin
                @(posedge clk);
                #1ns;
            end while (!commit_ready);
            commit_valid = 1'b0;
            commit_slot_id = 1'b0;
            commit_start_addr = 28'd0;
            commit_bytes = 32'd0;
            commit_records = 32'd0;
            commit_protocol_error = 1'b0;
            commit_committed = 1'b0;
        end
    endtask

    task automatic accept_read_descriptor(input logic expected_slot,
                                          input logic [27:0] expected_start,
                                          input logic [31:0] expected_bytes,
                                          input logic [31:0] expected_records,
                                          input integer hold_cycles);
        begin
            wait (read_desc_valid);
            #1ns;
            if (read_desc_slot_id !== expected_slot ||
                read_desc_start_addr !== expected_start ||
                read_desc_bytes !== expected_bytes ||
                read_desc_records !== expected_records ||
                read_desc_protocol_error)
                $fatal(1, "read descriptor mismatch: slot=%b start=%0d bytes=%0d records=%0d error=%b",
                       read_desc_slot_id, read_desc_start_addr, read_desc_bytes,
                       read_desc_records, read_desc_protocol_error);
            repeat (hold_cycles) begin
                @(posedge clk);
                #1ns;
                if (!read_desc_valid || read_desc_slot_id !== expected_slot ||
                    read_desc_start_addr !== expected_start ||
                    read_desc_bytes !== expected_bytes ||
                    read_desc_records !== expected_records)
                    $fatal(1, "read descriptor changed under backpressure");
            end
            @(negedge clk);
            read_desc_ready = 1'b1;
            @(posedge clk);
            #1ns;
            read_desc_ready = 1'b0;
        end
    endtask

    task automatic complete_read(input logic slot_id,
                                 input logic expect_fault);
        begin
            @(negedge clk);
            read_done_slot_id = slot_id;
            read_done_pulse = 1'b1;
            @(posedge clk);
            #1ns;
            read_done_pulse = 1'b0;
            read_done_slot_id = 1'b0;
            if (fault_pulse !== expect_fault)
                $fatal(1, "read completion fault mismatch for slot %0d", slot_id);
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        accept_allocation(1'b0, 28'd100, 2);
        accept_allocation(1'b1, 28'd200, 0);
        repeat (2) @(posedge clk);
        #1ns;
        if (write_alloc_valid)
            $fatal(1, "allocator offered a third slot while both slots were writing");

        submit_commit(1'b0, 28'd100, 32'd64, 32'd16, 1'b0, 1'b1);
        submit_commit(1'b1, 28'd200, 32'd32, 32'd8, 1'b0, 1'b1);
        #1ns;
        if (write_alloc_valid)
            $fatal(1, "queued slots were reallocated");

        wait (read_desc_valid);
        #1ns;
        if (read_desc_slot_id !== 1'b0 || read_desc_start_addr !== 28'd100 ||
            read_desc_bytes !== 32'd64 || read_desc_records !== 32'd16)
            $fatal(1, "first queued descriptor mismatch before continuous-ready test");
        @(negedge clk);
        read_desc_ready = 1'b1;
        @(posedge clk);
        #1ns;
        repeat (2) begin
            if (read_desc_valid)
                $fatal(1, "slot table exposed a second descriptor while one frame was reading");
            @(posedge clk);
            #1ns;
        end
        read_desc_ready = 1'b0;

        complete_read(1'b1, 1'b1);
        #1ns;
        if (read_desc_valid || write_alloc_valid)
            $fatal(1, "wrong-slot completion changed ownership");

        complete_read(1'b0, 1'b0);
        #1ns;
        if (!read_desc_valid || read_desc_slot_id !== 1'b1)
            $fatal(1, "second committed descriptor did not remain queued");
        accept_read_descriptor(1'b1, 28'd200, 32'd32, 32'd8, 0);
        accept_allocation(1'b0, 28'd100, 1);

        submit_commit(1'b0, 28'd100, 32'd12, 32'd3, 1'b1, 1'b0);
        #1ns;
        if (!drop_frame_pulse || drop_slot_id !== 1'b0 || read_desc_valid)
            $fatal(1, "invalid frame was not released without read queue insertion");
        @(posedge clk);
        #1ns;
        if (drop_frame_pulse)
            $fatal(1, "drop event was not one cycle");

        accept_allocation(1'b0, 28'd100, 0);
        submit_commit(1'b0, 28'd100, 32'd68, 32'd17, 1'b0, 1'b1);
        #1ns;
        if (!drop_frame_pulse || drop_slot_id !== 1'b0 || !fault_pulse ||
            read_desc_valid)
            $fatal(1, "oversized frame was not fault-dropped while the other slot read");
        @(posedge clk);

        complete_read(1'b1, 1'b0);
        submit_commit(1'b1, 28'd200, 32'd4, 32'd1, 1'b0, 1'b1);
        #1ns;
        if (!fault_pulse || read_desc_valid)
            $fatal(1, "commit from a free slot did not fail closed");
        @(posedge clk);

        accept_allocation(1'b0, 28'd100, 0);
        submit_commit(1'b0, 28'd101, 32'd4, 32'd1, 1'b0, 1'b1);
        #1ns;
        if (!fault_pulse || !drop_frame_pulse || drop_slot_id !== 1'b0)
            $fatal(1, "wrong start token did not fault-drop its writing slot");
        @(posedge clk);

        accept_allocation(1'b1, 28'd200, 0);
        submit_commit(1'b1, 28'd200, 32'd4, 32'd1, 1'b0, 1'b1);
        wait (read_desc_valid);
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (write_alloc_valid || read_desc_valid || drop_frame_pulse || fault_pulse)
            $fatal(1, "runtime reset did not clear slot table outputs");
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        accept_allocation(1'b0, 28'd100, 0);
        accept_allocation(1'b1, 28'd200, 0);
        submit_commit(1'b0, 28'd100, 32'd16, 32'd4, 1'b0, 1'b1);
        accept_read_descriptor(1'b0, 28'd100, 32'd16, 32'd4, 0);

        @(negedge clk);
        commit_slot_id = 1'b1;
        commit_start_addr = 28'd200;
        commit_bytes = 32'd20;
        commit_records = 32'd5;
        commit_protocol_error = 1'b0;
        commit_committed = 1'b1;
        commit_valid = 1'b1;
        read_done_slot_id = 1'b0;
        read_done_pulse = 1'b1;
        #1ns;
        if (!commit_ready)
            $fatal(1, "overlapped second-slot commit was backpressured");
        @(posedge clk);
        #1ns;
        commit_valid = 1'b0;
        read_done_pulse = 1'b0;
        if (fault_pulse || drop_frame_pulse)
            $fatal(1, "legal overlapped commit/completion produced an error");
        accept_read_descriptor(1'b1, 28'd200, 32'd20, 32'd5, 0);
        accept_allocation(1'b0, 28'd100, 0);

        $display("INFO: double-slot allocation, queueing, overlapped release, faults, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
