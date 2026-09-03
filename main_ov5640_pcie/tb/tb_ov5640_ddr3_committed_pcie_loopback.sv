`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_ddr3_committed_pcie_loopback.sv
 * @brief 验证 OV5640 经 DDR3 记录模型、帧提交读调度到 PCIe MWR 的行为闭环。
 *
 * @details
 * DDR3 写模型与帧提交器在同一 valid/ready 边沿接受同一规范化记录。正常帧
 * 提交后，读调度器按首 token 和记录数向模型发命令，模型返回对应记录进入
 * PCIe MWR；带 overflow abort 的帧只产生作废事件，不生成读命令或 MWR。
 *
 * @warning
 * 模型 token 只是数组索引。本测试不实例化厂商 DDR3/PCIe IP，不证明真实
 * DDR3 地址、初始化、持久化、PCIe TLP/DMA、链路、主机内存或板级时序。
 */
module tb_ov5640_ddr3_committed_pcie_loopback;
    localparam logic [27:0] SLOT0_BASE_ADDR = 28'd0;
    localparam logic [27:0] SLOT1_BASE_ADDR = 28'd64;
    localparam logic [31:0] SLOT_RECORD_CAPACITY = 32'd32;

    logic        in_rst_n = 1'b0;
    logic        out_rst_n = 1'b0;
    logic        cam_pclk = 1'b0;
    logic        ddr_clk = 1'b0;
    logic        cam_vsync = 1'b0;
    logic        cam_href = 1'b0;
    logic [7:0]  cam_data = 8'd0;

    logic        source_overflow;

    logic        ddr_write_valid;
    logic        ddr_write_ready;
    logic        ddr_write_slot_id;
    logic [27:0] ddr_write_addr;
    logic [3:0]  ddr_write_awlen;
    logic [127:0] ddr_write_data;
    logic [15:0] ddr_write_strb;
    logic        ddr_write_last;
    logic        ddr_write_frame_end;
    logic        ddr_write_protocol_error;
    logic        ddr_model_enable = 1'b1;
    logic        ddr_read_enable = 1'b1;

    logic        read_cmd_valid;
    logic        read_cmd_ready;
    logic [27:0] read_cmd_addr;
    logic        model_read_valid;
    logic        model_read_ready;
    logic [31:0] model_read_data;
    logic [3:0]  model_read_keep;
    logic        model_read_last;
    logic        model_read_frame_end;
    logic        model_read_protocol_error;
    logic        drop_frame_pulse;
    logic        drop_slot_id;
    logic        frame_done_pulse;
    logic        frame_done_slot_id;
    logic        frame_fault_pulse;

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
    logic        pcie_busy;

    logic [31:0] ddr_model_data [0:255];
    logic [3:0]  ddr_model_keep [0:255];
    logic        ddr_model_last [0:255];
    logic        ddr_model_frame_end [0:255];
    logic        ddr_model_protocol_error [0:255];
    logic [27:0] observed_read_cmd_addr [0:255];
    logic [27:0] observed_write_addr [0:255];
    logic        observed_write_slot [0:255];
    logic        observed_done_slot [0:15];
    integer      ddr_write_count = 0;
    integer      frame_write_count = 0;
    integer      read_cmd_count = 0;
    integer      drop_count = 0;
    integer      frame_done_count = 0;
    integer      frame_fault_count = 0;

    ov5640_dvp_rgb565_ddr3_pcie_pipeline #(
        .FIFO_ADDR_WIDTH(3),
        .TOKEN_ADDR_STEP(28'd1),
        .SLOT0_BASE_ADDR(SLOT0_BASE_ADDR),
        .SLOT1_BASE_ADDR(SLOT1_BASE_ADDR),
        .SLOT_RECORD_CAPACITY(SLOT_RECORD_CAPACITY),
        .PCIE_BASE_ADDR(64'h0000_0000_0000_2000)
    ) dut (
        .in_rst_n(in_rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href(cam_href), .cam_data(cam_data), .io_rst_n(out_rst_n),
        .io_clk(ddr_clk), .source_overflow(source_overflow),
        .ddr_write_valid(ddr_write_valid),
        .ddr_write_ready(ddr_write_ready),
        .ddr_write_slot_id(ddr_write_slot_id),
        .ddr_write_addr(ddr_write_addr), .ddr_write_awlen(ddr_write_awlen),
        .ddr_write_data(ddr_write_data), .ddr_write_strb(ddr_write_strb),
        .ddr_write_last(ddr_write_last),
        .ddr_write_frame_end(ddr_write_frame_end),
        .ddr_write_protocol_error(ddr_write_protocol_error),
        .ddr_read_cmd_valid(read_cmd_valid),
        .ddr_read_cmd_ready(read_cmd_ready),
        .ddr_read_cmd_addr(read_cmd_addr), .ddr_read_valid(model_read_valid),
        .ddr_read_ready(model_read_ready), .ddr_read_data(model_read_data),
        .ddr_read_keep(model_read_keep), .ddr_read_last(model_read_last),
        .ddr_read_frame_end(model_read_frame_end),
        .ddr_read_protocol_error(model_read_protocol_error),
        .drop_frame_pulse(drop_frame_pulse),
        .drop_slot_id(drop_slot_id),
        .frame_done_pulse(frame_done_pulse),
        .frame_done_slot_id(frame_done_slot_id),
        .frame_fault_pulse(frame_fault_pulse), .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack), .req_length(req_length),
        .req_addr(req_addr), .req_data(req_data), .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary), .req_last(req_last),
        .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error), .pcie_busy(pcie_busy)
    );

    always_comb begin
        ddr_write_ready = ddr_model_enable;
        read_cmd_ready = ddr_read_enable && !model_read_valid;
    end

    always #5ns cam_pclk = ~cam_pclk;
    always #7ns ddr_clk = ~ddr_clk;

    initial begin
        #60us;
        $fatal(1, "committed OV5640 DDR3 PCIe loopback timeout");
    end

    /**
     * Intent: Model atomic DDR write persistence and frame-commit observation.
     * Invariant: Every accepted write is stored once at its opaque token before
     *            that token can be requested by the read scheduler.
     */
    always_ff @(posedge ddr_clk or negedge out_rst_n) begin
        if (!out_rst_n) begin
            ddr_write_count <= 0;
            frame_write_count <= 0;
        end else if (ddr_write_valid && ddr_write_ready) begin
            if (ddr_write_addr > 28'd255)
                $fatal(1, "DDR3 model write token out of range: %0d", ddr_write_addr);
            ddr_model_data[ddr_write_addr] <= ddr_write_data[31:0];
            ddr_model_keep[ddr_write_addr] <= ddr_write_strb[3:0];
            ddr_model_last[ddr_write_addr] <= ddr_write_last;
            ddr_model_frame_end[ddr_write_addr] <= ddr_write_frame_end;
            ddr_model_protocol_error[ddr_write_addr] <= ddr_write_protocol_error;
            observed_write_addr[ddr_write_count] <= ddr_write_addr;
            observed_write_slot[ddr_write_count] <= ddr_write_slot_id;
            ddr_write_count <= ddr_write_count + 1;
            if (ddr_write_frame_end)
                frame_write_count <= frame_write_count + 1;
        end
    end

    /**
     * Intent: Return exactly one held model record for each accepted read command.
     * Invariant: The model has at most one response outstanding and does not return
     *            data for a token that the scheduler did not request.
     */
    always_ff @(posedge ddr_clk or negedge out_rst_n) begin
        if (!out_rst_n) begin
            model_read_valid <= 1'b0;
            model_read_data <= 32'd0;
            model_read_keep <= 4'd0;
            model_read_last <= 1'b0;
            model_read_frame_end <= 1'b0;
            model_read_protocol_error <= 1'b0;
            read_cmd_count <= 0;
        end else begin
            if (model_read_valid && model_read_ready)
                model_read_valid <= 1'b0;

            if (read_cmd_valid && read_cmd_ready) begin
                if (read_cmd_addr > 28'd255)
                    $fatal(1, "DDR3 model read token out of range: %0d", read_cmd_addr);
                observed_read_cmd_addr[read_cmd_count] <= read_cmd_addr;
                read_cmd_count <= read_cmd_count + 1;
                model_read_valid <= 1'b1;
                model_read_data <= ddr_model_data[read_cmd_addr];
                model_read_keep <= ddr_model_keep[read_cmd_addr];
                model_read_last <= ddr_model_last[read_cmd_addr];
                model_read_frame_end <= ddr_model_frame_end[read_cmd_addr];
                model_read_protocol_error <= ddr_model_protocol_error[read_cmd_addr];
            end
        end
    end

    always_ff @(posedge ddr_clk or negedge out_rst_n) begin
        if (!out_rst_n) begin
            drop_count <= 0;
            frame_done_count <= 0;
            frame_fault_count <= 0;
        end else begin
            if (drop_frame_pulse)
                drop_count <= drop_count + 1;
            if (frame_done_pulse) begin
                observed_done_slot[frame_done_count] <= frame_done_slot_id;
                frame_done_count <= frame_done_count + 1;
            end
            if (frame_fault_pulse)
                frame_fault_count <= frame_fault_count + 1;
        end
    end

    task automatic drive_byte(input logic [7:0] value);
        begin
            cam_data = value;
            @(posedge cam_pclk);
        end
    endtask

    task automatic drive_pixel(input logic [15:0] value);
        begin
            drive_byte(value[15:8]);
            drive_byte(value[7:0]);
        end
    endtask

    task automatic drive_frame(input integer pixel_count,
                               input logic [15:0] base_pixel);
        begin
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
            @(negedge cam_pclk);
            cam_href = 1'b1;
            for (integer index = 0; index < pixel_count; index = index + 1)
                drive_pixel(base_pixel + index);
            @(negedge cam_pclk);
            cam_href = 1'b0;
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
        end
    endtask

    task automatic reset_pipeline;
        begin
            @(negedge cam_pclk);
            in_rst_n = 1'b0;
            out_rst_n = 1'b0;
            cam_vsync = 1'b0;
            cam_href = 1'b0;
            ddr_model_enable = 1'b1;
            ddr_read_enable = 1'b1;
            mwr32_req_ack = 1'b0;
            repeat (3) @(posedge cam_pclk);
            repeat (3) @(posedge ddr_clk);
            @(negedge cam_pclk);
            in_rst_n = 1'b1;
            @(negedge ddr_clk);
            out_rst_n = 1'b1;
        end
    endtask

    task automatic accept_mwr(input integer model_index,
                              input logic [63:0] expected_addr,
                              input integer hold_cycles);
        logic [9:0] held_length;
        logic [63:0] held_addr;
        logic [31:0] held_data;
        logic [3:0] held_keep;
        logic held_last;
        logic held_frame_end;
        logic held_error;
        begin
            if (ddr_model_keep[model_index] == 4'h0)
                $fatal(1, "MWR task received an empty control record at model index %0d",
                       model_index);
            wait (mwr32_req);
            #1ns;
            if (!pcie_busy || req_length !== 10'd1 || req_addr !== expected_addr ||
                req_data !== ddr_model_data[model_index] ||
                req_keep !== ddr_model_keep[model_index] ||
                req_last !== ddr_model_last[model_index] ||
                req_frame_end !== ddr_model_frame_end[model_index] ||
                req_protocol_error !== ddr_model_protocol_error[model_index] ||
                cross_4kb_boundary)
                $fatal(1, "committed MWR mismatch at model index %0d", model_index);

            held_length = req_length;
            held_addr = req_addr;
            held_data = req_data;
            held_keep = req_keep;
            held_last = req_last;
            held_frame_end = req_frame_end;
            held_error = req_protocol_error;
            repeat (hold_cycles) begin
                @(posedge ddr_clk);
                #1ns;
                if (!mwr32_req || req_length !== held_length || req_addr !== held_addr ||
                    req_data !== held_data || req_keep !== held_keep ||
                    req_last !== held_last || req_frame_end !== held_frame_end ||
                    req_protocol_error !== held_error)
                    $fatal(1, "MWR fields changed while ACK was delayed");
            end

            @(negedge ddr_clk);
            mwr32_req_ack = 1'b1;
            @(posedge ddr_clk);
            #1ns;
            mwr32_req_ack = 1'b0;
        end
    endtask

    // Intent: Observe scheduler completion for an empty frame-control response.
    // Invariant: The response consumes one DDR read command but emits no MWR.
    task automatic consume_control_record(input integer model_index,
                                          input integer command_index,
                                          input integer expected_done_count,
                                          input logic expected_done_slot);
        begin
            if (ddr_model_keep[model_index] != 4'h0)
                $fatal(1, "control task received payload bytes at model index %0d",
                       model_index);
            wait (frame_done_count == expected_done_count);
            #1ns;
            if (read_cmd_count < command_index + 1 ||
                observed_read_cmd_addr[command_index] !== model_index ||
                observed_done_slot[expected_done_count - 1] !== expected_done_slot ||
                mwr32_req || pcie_busy)
                $fatal(1, "empty control record did not complete locally at model index %0d",
                       model_index);
        end
    endtask

    initial begin
        integer pressure_record_count;

        reset_pipeline();
        ddr_read_enable = 1'b0;
        drive_frame(3, 16'h1000);
        wait (frame_write_count == 1);
        drive_frame(2, 16'h2000);
        wait (frame_write_count == 2);
        wait (!ddr_write_valid);
        repeat (3) @(posedge ddr_clk);
        #1ns;
        if (ddr_write_count != 5 || read_cmd_count != 0 || drop_count != 0 ||
            observed_write_slot[0] !== 1'b0 || observed_write_addr[0] !== 28'd0 ||
            observed_write_addr[1] !== 28'd1 || observed_write_addr[2] !== 28'd2 ||
            observed_write_slot[3] !== 1'b1 || observed_write_addr[3] !== 28'd64 ||
            observed_write_addr[4] !== 28'd65)
            $fatal(1, "two frames were not written into distinct queued slots");

        ddr_read_enable = 1'b1;
        accept_mwr(0, 64'h0000_0000_0000_2000, 2);
        accept_mwr(1, 64'h0000_0000_0000_2004, 0);
        consume_control_record(2, 2, 1, 1'b0);
        accept_mwr(64, 64'h0000_0000_0000_2006, 1);
        consume_control_record(65, 4, 2, 1'b1);
        repeat (3) @(posedge ddr_clk);
        #1ns;
        if (read_cmd_count != 5 || drop_count != 0 || frame_done_count != 2 ||
            frame_fault_count != 0 || observed_done_slot[0] !== 1'b0 ||
            observed_done_slot[1] !== 1'b1 ||
            observed_read_cmd_addr[0] !== 28'd0 ||
            observed_read_cmd_addr[1] !== 28'd1 ||
            observed_read_cmd_addr[2] !== 28'd2 ||
            observed_read_cmd_addr[3] !== 28'd64 ||
            observed_read_cmd_addr[4] !== 28'd65)
            $fatal(1, "queued double-slot readout accounting mismatch");

        drive_frame(1, 16'h3000);
        wait (frame_write_count == 3);
        accept_mwr(0, 64'h0000_0000_0000_200a, 1);
        consume_control_record(1, 6, 3, 1'b0);
        repeat (3) @(posedge ddr_clk);
        #1ns;
        if (ddr_write_count != 7 || observed_write_slot[5] !== 1'b0 ||
            observed_write_addr[5] !== 28'd0 || observed_write_addr[6] !== 28'd1 ||
            read_cmd_count != 7 || observed_read_cmd_addr[5] !== 28'd0 ||
            observed_read_cmd_addr[6] !== 28'd1 || frame_done_count != 3 ||
            observed_done_slot[2] !== 1'b0 || frame_fault_count != 0)
            $fatal(1, "released slot was not reused by the third frame");

        $display("INFO: two OV5640 frames queued in slots 0/1 and read in order");
        $display("INFO: slot 0 was reused after its first frame left DDR storage");

        reset_pipeline();
        ddr_model_enable = 1'b0;
        drive_frame(64, 16'h4000);
        repeat (20) @(posedge cam_pclk);
        if (!source_overflow)
            $fatal(1, "pressure frame did not trigger source overflow");

        ddr_model_enable = 1'b1;
        wait (frame_write_count == 1);
        wait (!ddr_write_valid);
        wait (drop_count == 1);
        repeat (3) @(posedge ddr_clk);
        pressure_record_count = ddr_write_count;
        if (pressure_record_count < 2 ||
            !ddr_model_protocol_error[pressure_record_count - 1] ||
            ddr_model_keep[pressure_record_count - 1] !== 4'h0 ||
            !ddr_model_frame_end[pressure_record_count - 1] ||
            drop_slot_id !== 1'b0 || read_cmd_count != 0 || mwr32_req || pcie_busy)
            $fatal(1, "invalid pressure frame was not dropped before DDR readout");

        drive_frame(2, 16'hf800);
        wait (frame_write_count == 2);
        accept_mwr(64, 64'h0000_0000_0000_2000, 2);
        consume_control_record(65, 1, 1, 1'b1);
        repeat (3) @(posedge ddr_clk);
        #1ns;
        if (read_cmd_count != 2 ||
            observed_read_cmd_addr[0] !== 28'd64 ||
            observed_read_cmd_addr[1] !== 28'd65 ||
            drop_count != 1 || frame_done_count != 1 ||
            observed_done_slot[0] !== 1'b1 || frame_fault_count != 0 ||
            req_protocol_error)
            $fatal(1, "post-drop recovery frame scheduling mismatch");

        $display("INFO: pressure frame wrote %0d records, produced one drop and zero reads",
                 pressure_record_count);
        $display("INFO: recovery frame used slot 1 tokens 64/65 and reached PCIe");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
