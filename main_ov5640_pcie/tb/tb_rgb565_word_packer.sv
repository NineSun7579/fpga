`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_word_packer.sv
 * @brief 首个 128-bit RGB565 打包行为测试。
 *
 * @details
 * 通过公开输入输出端口检查 8 个像素的顺序、完整 byte-enable 以及首帧首行
 * 事件。该测试不依赖打包器内部寄存器，也不覆盖 DDR3、PCIe、CDC 或板级输入。
 */
module tb_rgb565_word_packer;

    localparam time CLK_HALF_PERIOD = 5ns;

    logic rst_n = 1'b0;
    logic clk = 1'b0;
    logic in_valid = 1'b0;
    logic [15:0] in_data = 16'h0000;
    logic in_frame_start = 1'b0;
    logic in_line_start = 1'b0;
    logic in_line_end = 1'b0;
    logic in_frame_end = 1'b0;
    logic in_protocol_error = 1'b0;

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

    rgb565_word_packer u_dut (
        .rst_n              (rst_n),
        .clk                (clk),
        .in_valid           (in_valid),
        .in_data            (in_data),
        .in_frame_start     (in_frame_start),
        .in_line_start      (in_line_start),
        .in_line_end        (in_line_end),
        .in_frame_end       (in_frame_end),
        .in_protocol_error  (in_protocol_error),
        .word_valid         (word_valid),
        .word_data          (word_data),
        .word_keep          (word_keep),
        .word_frame_start   (word_frame_start),
        .word_line_start    (word_line_start),
        .word_line_end      (word_line_end),
        .word_frame_end     (word_frame_end),
        .word_protocol_error(word_protocol_error)
    );

    always #CLK_HALF_PERIOD clk = ~clk;

    // 监视公开输出，避免测试与实现内部状态耦合。
    always @(posedge clk) begin
        #1ns;
        if (word_valid) begin
            case (observed_words)
                0: begin
                    if (word_data !== 128'h00880077006600550044003300220011) begin
                        $fatal(1, "Packed full word mismatch: %h", word_data);
                    end
                    if (word_keep !== 16'hffff) begin
                        $fatal(1, "Packed full word keep mismatch: %h", word_keep);
                    end
                    if (!word_frame_start || !word_line_start) begin
                        $fatal(1, "Start events missing on first packed word");
                    end
                    if (!word_line_end) begin
                        $fatal(1, "Full line end missing on first packed word");
                    end
                end
                1: begin
                    if (word_data !== 128'h00000000000000000000030302020101) begin
                        $fatal(1, "Packed partial word mismatch: %h", word_data);
                    end
                    if (word_keep !== 16'h003f || !word_line_start || !word_line_end) begin
                        $fatal(1, "Packed partial line boundary mismatch: keep=%h start=%b end=%b",
                            word_keep, word_line_start, word_line_end);
                    end
                end
                default: $fatal(1, "Observed unexpected packed word %0d", observed_words);
            endcase
            observed_words = observed_words + 1;
        end
        if (word_frame_end) begin
            if (word_valid || word_keep !== 16'h0000) begin
                $fatal(1, "Frame-end control event carried unexpected payload");
            end
            observed_frame_ends = observed_frame_ends + 1;
        end
        if (word_protocol_error) begin
            if (word_valid || word_keep !== 16'h0000) begin
                $fatal(1, "Protocol-error control event carried unexpected payload");
            end
            observed_protocol_errors = observed_protocol_errors + 1;
        end
    end

    task automatic drive_pixel(
        input logic [15:0] value,
        input logic frame_start_value,
        input logic line_start_value
    );
        begin
            in_valid       = 1'b1;
            in_data        = value;
            in_frame_start = frame_start_value;
            in_line_start  = line_start_value;
            @(posedge clk);
        end
    endtask

    // 有界 watchdog 防止缺失输出时仿真无限等待。
    initial begin
        #20us;
        $fatal(1, "RGB565 word packer test timeout");
    end

    initial begin
        observed_words = 0;
        observed_frame_ends = 0;
        observed_protocol_errors = 0;
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        drive_pixel(16'h0011, 1'b1, 1'b1);
        drive_pixel(16'h0022, 1'b0, 1'b0);
        drive_pixel(16'h0033, 1'b0, 1'b0);
        drive_pixel(16'h0044, 1'b0, 1'b0);
        drive_pixel(16'h0055, 1'b0, 1'b0);
        drive_pixel(16'h0066, 1'b0, 1'b0);
        drive_pixel(16'h0077, 1'b0, 1'b0);
        drive_pixel(16'h0088, 1'b0, 1'b0);

        in_valid       = 1'b0;
        in_data        = 16'h0000;
        in_frame_start = 1'b0;
        in_line_start  = 1'b0;
        in_line_end    = 1'b1;
        @(posedge clk);
        in_line_end    = 1'b0;
        repeat (2) @(posedge clk);

        drive_pixel(16'h0101, 1'b0, 1'b1);
        drive_pixel(16'h0202, 1'b0, 1'b0);
        drive_pixel(16'h0303, 1'b0, 1'b0);
        in_valid    = 1'b0;
        in_line_end = 1'b1;
        @(posedge clk);
        in_line_end = 1'b0;
        repeat (2) @(posedge clk);

        in_frame_end = 1'b1;
        @(posedge clk);
        in_frame_end = 1'b0;
        repeat (1) @(posedge clk);

        in_protocol_error = 1'b1;
        @(posedge clk);
        in_protocol_error = 1'b0;
        repeat (1) @(posedge clk);

        if (observed_words != 2) begin
            $fatal(1, "Packed word count mismatch: observed=%0d expected=2", observed_words);
        end
        if (observed_frame_ends != 1 || observed_protocol_errors != 1) begin
            $fatal(1, "Control event count mismatch: frame_end=%0d protocol_error=%0d",
                observed_frame_ends, observed_protocol_errors);
        end

        $display("INFO: RGB565 128-bit full-word packing verified");
        $display("INFO: RGB565 128-bit partial line packing verified");
        $display("INFO: RGB565 word control events verified");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
