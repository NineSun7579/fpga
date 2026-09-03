`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_ddr3_pcie_loopback.sv
 * @brief 验证 OV5640 DVP 到 DDR3 记录模型再到 PCIe MWR 请求的行为级往返。
 *
 * @details
 * 测试使用公开模块接口串接摄像头采集、灰度/打包、CDC staging、DDR3
 * 单 beat 写记录和 PCIe MWR 请求路径。DDR3 模型将规范化地址 token 映射
 * 为数组索引，写入完成后按帧序读回，不解释真实控制器的地址单位或读口时序。
 *
 * @warning
 * 本测试不实例化厂商 DDR3/PCIe IP，不证明 FPGA 管脚、DDR3 初始化、PCIe
 * 链路、TLP byte enable 或主机内存写入已经通过。
 */
module tb_ov5640_ddr3_pcie_loopback;
    localparam integer NORMAL_FRAME_RECORDS = 3;

    logic in_rst_n = 1'b0;
    logic out_rst_n = 1'b0;
    logic cam_pclk = 1'b0;
    logic ddr_clk = 1'b0;
    logic cam_vsync = 1'b0;
    logic cam_href = 1'b0;
    logic [7:0] cam_data = 8'd0;

    logic staging_valid;
    logic staging_ready;
    logic [31:0] staging_data;
    logic [3:0] staging_keep;
    logic staging_last;
    logic [4:0] staging_user;
    logic source_overflow;

    logic ddr_write_valid;
    logic ddr_write_ready = 1'b1;
    logic [27:0] ddr_write_addr;
    logic [3:0] ddr_write_awlen;
    logic [127:0] ddr_write_data;
    logic [15:0] ddr_write_strb;
    logic ddr_write_last;
    logic ddr_write_frame_end;
    logic ddr_write_protocol_error;

    logic pcie_in_valid = 1'b0;
    logic pcie_in_ready;
    logic [31:0] pcie_in_data = 32'd0;
    logic [3:0] pcie_in_keep = 4'd0;
    logic pcie_in_last = 1'b0;
    logic pcie_in_frame_end = 1'b0;
    logic pcie_in_protocol_error = 1'b0;
    logic mwr32_req;
    logic mwr32_req_ack = 1'b0;
    logic [9:0] req_length;
    logic [63:0] req_addr;
    logic [31:0] req_data;
    logic [3:0] req_keep;
    logic cross_4kb_boundary;
    logic req_last;
    logic req_frame_end;
    logic req_protocol_error;
    logic pcie_busy;

    logic [31:0] ddr_model_data [0:255];
    logic [3:0] ddr_model_keep [0:255];
    logic ddr_model_last [0:255];
    logic ddr_model_frame_end [0:255];
    logic ddr_model_protocol_error [0:255];
    logic [63:0] pcie_observed_addr [0:255];
    integer ddr_write_count = 0;
    logic frame_written = 1'b0;

    ov5640_dvp_rgb565_cdc_staging_pipeline #(.FIFO_ADDR_WIDTH(3)) u_capture (
        .in_rst_n(in_rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href(cam_href), .cam_data(cam_data), .out_rst_n(out_rst_n),
        .out_clk(ddr_clk), .out_valid(staging_valid), .out_ready(staging_ready),
        .out_data(staging_data), .out_keep(staging_keep), .out_last(staging_last),
        .out_user(staging_user), .source_overflow(source_overflow)
    );

    rgb565_axis4_ddr3_write_descriptor #(.BASE_ADDR(28'd0), .ADDR_STEP(28'd1)) u_ddr_writer (
        .rst_n(out_rst_n), .clk(ddr_clk), .in_valid(staging_valid), .in_ready(staging_ready),
        .in_data(staging_data), .in_keep(staging_keep), .in_last(staging_last),
        .in_frame_end(staging_user[3]), .in_protocol_error(staging_user[4]),
        .write_valid(ddr_write_valid), .write_ready(ddr_write_ready),
        .write_addr(ddr_write_addr), .write_awlen(ddr_write_awlen),
        .write_data(ddr_write_data), .write_strb(ddr_write_strb),
        .write_last(ddr_write_last), .write_frame_end(ddr_write_frame_end),
        .write_protocol_error(ddr_write_protocol_error)
    );

    rgb565_axis4_pcie_mwr_path #(.BASE_ADDR(64'h0000_0000_0000_0ffc)) u_pcie_path (
        .rst_n(out_rst_n), .clk(ddr_clk), .in_valid(pcie_in_valid), .in_ready(pcie_in_ready),
        .in_data(pcie_in_data), .in_keep(pcie_in_keep), .in_last(pcie_in_last),
        .in_frame_end(pcie_in_frame_end), .in_protocol_error(pcie_in_protocol_error),
        .mwr32_req(mwr32_req), .mwr32_req_ack(mwr32_req_ack), .req_length(req_length),
        .req_addr(req_addr), .req_data(req_data), .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary), .req_last(req_last),
        .req_frame_end(req_frame_end), .req_protocol_error(req_protocol_error),
        .busy(pcie_busy)
    );

    always #5ns cam_pclk = ~cam_pclk;
    always #7ns ddr_clk = ~ddr_clk;
    initial begin
        #40us;
        $fatal(1, "OV5640 DDR3 PCIe loopback timeout");
    end

    // Intent: capture every accepted normalized DDR3 write into the model.
    // Invariant: the model keeps the descriptor fields needed for exact readback.
    // Assumption: this test uses BASE_ADDR=0 and ADDR_STEP=1 as model indices only.
    always @(posedge ddr_clk) begin
        if (out_rst_n && ddr_write_valid && ddr_write_ready) begin
            if (ddr_write_addr > 28'd255)
                $fatal(1, "DDR3 model address out of range: %0d", ddr_write_addr);
            ddr_model_data[ddr_write_addr] <= ddr_write_data[31:0];
            ddr_model_keep[ddr_write_addr] <= ddr_write_strb[3:0];
            ddr_model_last[ddr_write_addr] <= ddr_write_last;
            ddr_model_frame_end[ddr_write_addr] <= ddr_write_frame_end;
            ddr_model_protocol_error[ddr_write_addr] <= ddr_write_protocol_error;
            ddr_write_count = ddr_write_count + 1;
            if (ddr_write_frame_end)
                frame_written = 1'b1;
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

    function automatic logic [2:0] popcount4(input logic [3:0] value);
        begin
            popcount4 = {2'b0, value[0]} + {2'b0, value[1]} +
                        {2'b0, value[2]} + {2'b0, value[3]};
        end
    endfunction

    task automatic drive_frame(input integer pixel_count, input logic [15:0] base_pixel);
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
            in_rst_n = 1'b0;
            out_rst_n = 1'b0;
            cam_vsync = 1'b0;
            cam_href = 1'b0;
            pcie_in_valid = 1'b0;
            mwr32_req_ack = 1'b0;
            repeat (2) @(posedge cam_pclk);
            repeat (2) @(posedge ddr_clk);
            ddr_write_count = 0;
            frame_written = 1'b0;
            in_rst_n = 1'b1;
            out_rst_n = 1'b1;
        end
    endtask

    task automatic send_pcie_record(input integer index,
                                    input logic [63:0] expected_addr);
        begin
            while (!pcie_in_ready)
                @(posedge ddr_clk);
            @(negedge ddr_clk);
            pcie_in_data = ddr_model_data[index];
            pcie_in_keep = ddr_model_keep[index];
            pcie_in_last = ddr_model_last[index];
            pcie_in_frame_end = ddr_model_frame_end[index];
            pcie_in_protocol_error = ddr_model_protocol_error[index];
            pcie_in_valid = 1'b1;
            @(posedge ddr_clk);
            #1ns;
            pcie_in_valid = 1'b0;
            // Descriptor and bridge are two sequential holding stages.
            @(posedge ddr_clk);
            #1ns;
            if (!mwr32_req || !pcie_busy || req_length !== 10'd0 ||
                req_addr !== expected_addr ||
                req_data !== ddr_model_data[index] || req_keep !== ddr_model_keep[index] ||
                req_last !== ddr_model_last[index] ||
                req_frame_end !== ddr_model_frame_end[index] ||
                req_protocol_error !== ddr_model_protocol_error[index])
                $fatal(1, "PCIe readback request mismatch at index %0d: addr=%h exp=%h data=%h exp=%h keep=%h exp=%h last=%b exp=%b frame=%b exp=%b err=%b exp=%b boundary=%b",
                       index, req_addr,
                       expected_addr,
                       req_data, ddr_model_data[index], req_keep, ddr_model_keep[index],
                       req_last, ddr_model_last[index], req_frame_end,
                       ddr_model_frame_end[index], req_protocol_error,
                       ddr_model_protocol_error[index], cross_4kb_boundary);
            if (cross_4kb_boundary)
                $fatal(1, "readback request unexpectedly crosses 4 KB boundary at index %0d", index);
            pcie_observed_addr[index] = req_addr;
            mwr32_req_ack = 1'b1;
            @(posedge ddr_clk);
            #1ns;
            mwr32_req_ack = 1'b0;
            if (pcie_busy || mwr32_req)
                $fatal(1, "PCIe request did not release at index %0d", index);
        end
    endtask

    initial begin
        logic [63:0] expected_pcie_addr;
        integer pressure_record_count;
        integer recovery_start_index;
        integer abort_record_count;
        integer abort_record_index;

        repeat (2) @(posedge cam_pclk);
        in_rst_n = 1'b1;
        repeat (2) @(posedge ddr_clk);
        out_rst_n = 1'b1;

        // Three pixels produce two payload records and one frame-end control record.
        @(posedge cam_pclk);
        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        @(posedge cam_pclk);
        cam_href = 1'b1;
        drive_pixel(16'hf800);
        drive_pixel(16'h07e0);
        drive_pixel(16'h001f);
        cam_href = 1'b0;
        @(posedge cam_pclk);
        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;

        wait (frame_written);
        repeat (2) @(posedge ddr_clk);
        if (ddr_write_count != NORMAL_FRAME_RECORDS || source_overflow)
            $fatal(1, "DDR3 write phase mismatch: writes=%0d overflow=%b",
                   ddr_write_count, source_overflow);
        if (ddr_model_keep[0] !== 4'hf || ddr_model_keep[1] !== 4'h3 ||
            ddr_model_keep[2] !== 4'h0 || !ddr_model_frame_end[2])
            $fatal(1, "DDR3 model payload or frame-end records mismatch");

        expected_pcie_addr = 64'h0000_0000_0000_0ffc;
        for (integer index = 0; index < NORMAL_FRAME_RECORDS; index = index + 1) begin
            send_pcie_record(index, expected_pcie_addr);
            expected_pcie_addr = expected_pcie_addr + popcount4(ddr_model_keep[index]);
        end

        $display("INFO: OV5640 DVP frame wrote %0d normalized DDR3 records", ddr_write_count);
        $display("INFO: DDR3 model readback reached PCIe MWR at 0x0ffc, 0x1000, 0x1002");

        // 阻塞 DDR 写端制造 camera-side overflow，再验证中止记录和下一帧恢复。
        reset_pipeline();
        ddr_write_ready = 1'b0;
        drive_frame(64, 16'h4000);
        repeat (20) @(posedge cam_pclk);
        if (!source_overflow)
            $fatal(1, "loopback pressure did not trigger source overflow");

        ddr_write_ready = 1'b1;
        wait (frame_written);
        wait (!staging_valid && !ddr_write_valid);
        repeat (4) @(posedge ddr_clk);
        pressure_record_count = ddr_write_count;
        abort_record_count = 0;
        abort_record_index = -1;
        for (integer index = 0; index < pressure_record_count; index = index + 1) begin
            if (ddr_model_protocol_error[index]) begin
                abort_record_count = abort_record_count + 1;
                abort_record_index = index;
                if (ddr_model_keep[index] !== 4'h0 || !ddr_model_last[index] ||
                    !ddr_model_frame_end[index])
                    $fatal(1, "DDR3 model abort record fields mismatch at index %0d", index);
            end
        end
        if (pressure_record_count < 2 || abort_record_count != 1 ||
            abort_record_index != pressure_record_count - 1)
            $fatal(1, "DDR3 model abort ordering mismatch: records=%0d aborts=%0d index=%0d",
                   pressure_record_count, abort_record_count, abort_record_index);

        recovery_start_index = ddr_write_count;
        frame_written = 1'b0;
        drive_frame(1, 16'hf800);
        wait (ddr_write_count >= recovery_start_index + 2);
        repeat (4) @(posedge ddr_clk);
        if (ddr_model_keep[recovery_start_index] !== 4'h3 ||
            ddr_model_protocol_error[recovery_start_index] ||
            ddr_model_keep[recovery_start_index + 1] !== 4'h0 ||
            !ddr_model_frame_end[recovery_start_index + 1] ||
            ddr_model_protocol_error[recovery_start_index + 1])
            $fatal(1, "DDR3 model next-frame recovery records mismatch");

        expected_pcie_addr = 64'h0000_0000_0000_0ffc;
        for (integer index = 0; index < ddr_write_count; index = index + 1) begin
            send_pcie_record(index, expected_pcie_addr);
            expected_pcie_addr = expected_pcie_addr + popcount4(ddr_model_keep[index]);
        end
        if (pcie_observed_addr[abort_record_index] !==
            pcie_observed_addr[recovery_start_index])
            $fatal(1, "empty abort record unexpectedly advanced PCIe address");

        $display("INFO: pressure frame wrote %0d records with one abort at index %0d",
                 pressure_record_count, abort_record_index);
        $display("INFO: abort and recovered payload reused PCIe address %h",
                 pcie_observed_addr[abort_record_index]);
        $display("TEST PASS");
        $finish;
    end
endmodule
`default_nettype wire
