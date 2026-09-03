`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_dvp_rgb565_word_pipeline.sv
 * @brief OV5640 DVP 到 128-bit 图像字的集成行为测试。
 *
 * @details
 * 通过公开 DVP 输入驱动两行小帧，检查采集、灰度处理和 128-bit 打包之间的
 * 数据布局、行尾补零、帧尾控制事件与协议错误传播。测试不覆盖板级时钟、
 * SCCB、CDC、DDR3、PCIe TLP 或主机协议。
 */
module tb_ov5640_dvp_rgb565_word_pipeline;

    localparam time PCLK_HALF_PERIOD = 5ns;

    logic rst_n = 1'b0;
    logic cam_pclk = 1'b0;
    logic cam_vsync = 1'b0;
    logic cam_href = 1'b0;
    logic [7:0] cam_data = 8'h00;

    logic word_valid;
    logic [127:0] word_data;
    logic [15:0] word_keep;
    logic word_frame_start;
    logic word_line_start;
    logic word_line_end;
    logic word_frame_end;
    logic word_protocol_error;
    int unsigned observed_words;
    int unsigned observed_frame_ends;
    int unsigned observed_protocol_errors;

    ov5640_dvp_rgb565_word_pipeline u_dut (
        .rst_n              (rst_n),
        .cam_pclk           (cam_pclk),
        .cam_vsync          (cam_vsync),
        .cam_href           (cam_href),
        .cam_data           (cam_data),
        .word_valid         (word_valid),
        .word_data          (word_data),
        .word_keep          (word_keep),
        .word_frame_start   (word_frame_start),
        .word_line_start    (word_line_start),
        .word_line_end      (word_line_end),
        .word_frame_end     (word_frame_end),
        .word_protocol_error(word_protocol_error)
    );

    always #PCLK_HALF_PERIOD cam_pclk = ~cam_pclk;

    // 只检查公开输出，保持集成测试不依赖子模块内部状态。
    always @(posedge cam_pclk) begin
        #1ns;
        if (word_valid) begin
            case (observed_words)
                0: begin
                    if (word_data !== 128'h18e394b24a69000018e394b24a690000 ||
                        word_keep !== 16'hffff) begin
                        $fatal(1, "Integrated full word mismatch: data=%h keep=%h",
                            word_data, word_keep);
                    end
                    if (!word_frame_start || !word_line_start || !word_line_end) begin
                        $fatal(1, "Integrated first-word boundary mismatch");
                    end
                end
                1: begin
                    if (word_data !== 128'h0000000000000000000018e394b24a69 ||
                        word_keep !== 16'h003f) begin
                        $fatal(1, "Integrated partial word mismatch: data=%h keep=%h",
                            word_data, word_keep);
                    end
                    if (!word_line_start || !word_line_end || word_frame_start) begin
                        $fatal(1, "Integrated second-line boundary mismatch");
                    end
                end
                default: $fatal(1, "Observed unexpected integrated word %0d", observed_words);
            endcase
            observed_words = observed_words + 1;
        end
        if (word_frame_end) begin
            if (word_valid || word_keep !== 16'h0000) begin
                $fatal(1, "Integrated frame-end control event carried payload");
            end
            observed_frame_ends = observed_frame_ends + 1;
        end
        if (word_protocol_error) begin
            if (word_valid || word_keep !== 16'h0000) begin
                $fatal(1, "Integrated protocol-error control event carried payload");
            end
            observed_protocol_errors = observed_protocol_errors + 1;
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

    task automatic drive_line(input logic [15:0] pixel0,
                              input logic [15:0] pixel1,
                              input logic [15:0] pixel2,
                              input logic [15:0] pixel3,
                              input logic [15:0] pixel4,
                              input logic [15:0] pixel5,
                              input logic [15:0] pixel6,
                              input logic [15:0] pixel7);
        begin
            cam_href = 1'b1;
            drive_pixel(pixel0);
            drive_pixel(pixel1);
            drive_pixel(pixel2);
            drive_pixel(pixel3);
            drive_pixel(pixel4);
            drive_pixel(pixel5);
            drive_pixel(pixel6);
            drive_pixel(pixel7);
            cam_href = 1'b0;
            @(posedge cam_pclk);
        end
    endtask

    task automatic drive_short_line(input logic [15:0] pixel0,
                                    input logic [15:0] pixel1,
                                    input logic [15:0] pixel2);
        begin
            cam_href = 1'b1;
            drive_pixel(pixel0);
            drive_pixel(pixel1);
            drive_pixel(pixel2);
            cam_href = 1'b0;
            @(posedge cam_pclk);
        end
    endtask

    task automatic drive_odd_byte_line(input logic [7:0] value);
        begin
            cam_href = 1'b1;
            drive_byte(value);
            cam_href = 1'b0;
            @(posedge cam_pclk);
        end
    endtask

    // 有界 watchdog 防止集成链路缺失边界事件时无限等待。
    initial begin
        #30us;
        $fatal(1, "OV5640 word pipeline test timeout");
    end

    initial begin
        observed_words = 0;
        observed_frame_ends = 0;
        observed_protocol_errors = 0;

        repeat (2) @(posedge cam_pclk);
        rst_n = 1'b1;
        @(posedge cam_pclk);

        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        @(posedge cam_pclk);

        drive_line(16'h0000, 16'hf800, 16'h07e0, 16'h001f,
                   16'h0000, 16'hf800, 16'h07e0, 16'h001f);
        drive_short_line(16'hf800, 16'h07e0, 16'h001f);

        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        drive_odd_byte_line(8'hde);
        repeat (4) @(posedge cam_pclk);

        if (observed_words != 2 || observed_frame_ends != 1 ||
            observed_protocol_errors != 1) begin
            $fatal(1, "Integrated result count mismatch: words=%0d frame_end=%0d errors=%0d",
                observed_words, observed_frame_ends, observed_protocol_errors);
        end

        $display("INFO: OV5640 DVP to RGB565 128-bit word pipeline verified");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
