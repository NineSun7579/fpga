`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_dvp_rgb565_pipeline.sv
 * @brief Self-checking capture-to-grayscale behavior test.
 *
 * @details
 * The test drives a small two-line DVP frame through the public camera pins
 * and checks processed RGB565 data, coordinates, event preservation, and the
 * odd-byte protocol error. It does not verify sensor configuration, board
 * timing, CDC/FIFO, DDR3, or PCIe behavior.
 *
 * @par Test contract
 * - The expected grayscale pixels are black, red, green, and blue samples.
 * - Output events remain aligned with the processed pixels.
 * - An HREF window containing one byte reports one protocol error.
 */
module tb_ov5640_dvp_rgb565_pipeline;

    localparam time PCLK_HALF_PERIOD = 5ns;
    localparam int unsigned PIXEL_COUNT = 4;

    logic rst_n = 1'b0;
    logic cam_pclk = 1'b0;
    logic cam_vsync = 1'b0;
    logic cam_href = 1'b0;
    logic [7:0] cam_data = 8'h00;

    logic pixel_valid;
    logic [15:0] pixel_data;
    logic frame_start;
    logic line_start;
    logic line_end;
    logic frame_end;
    logic [15:0] pixel_x;
    logic [15:0] pixel_y;
    logic protocol_error;

    logic [15:0] expected_data [0:PIXEL_COUNT - 1];
    logic [15:0] expected_x [0:PIXEL_COUNT - 1];
    logic [15:0] expected_y [0:PIXEL_COUNT - 1];
    int unsigned observed_pixels;
    int unsigned observed_line_starts;
    int unsigned observed_line_ends;
    int unsigned observed_frame_starts;
    int unsigned observed_frame_ends;
    int unsigned observed_errors;

    ov5640_dvp_rgb565_pipeline u_dut (
        .rst_n          (rst_n),
        .cam_pclk       (cam_pclk),
        .cam_vsync      (cam_vsync),
        .cam_href       (cam_href),
        .cam_data       (cam_data),
        .pixel_valid    (pixel_valid),
        .pixel_data     (pixel_data),
        .frame_start    (frame_start),
        .line_start     (line_start),
        .line_end       (line_end),
        .frame_end      (frame_end),
        .pixel_x        (pixel_x),
        .pixel_y        (pixel_y),
        .protocol_error (protocol_error)
    );

    always #PCLK_HALF_PERIOD cam_pclk = ~cam_pclk;

    // Intent: Check the public processed stream rather than implementation state.
    always @(posedge cam_pclk) begin
        #1ns;
        if (pixel_valid) begin
            if (observed_pixels >= PIXEL_COUNT) begin
                $fatal(1, "Observed more processed pixels than expected");
            end
            if (pixel_data !== expected_data[observed_pixels] ||
                pixel_x !== expected_x[observed_pixels] ||
                pixel_y !== expected_y[observed_pixels]) begin
                $fatal(1,
                    "Processed pixel %0d mismatch: data=%h x=%0d y=%0d expected=%h x=%0d y=%0d",
                    observed_pixels,
                    pixel_data,
                    pixel_x,
                    pixel_y,
                    expected_data[observed_pixels],
                    expected_x[observed_pixels],
                    expected_y[observed_pixels]);
            end
            if ((observed_pixels == 0) && !frame_start) begin
                $fatal(1, "Processed first pixel did not assert frame_start");
            end
            if ((observed_pixels == 0 || observed_pixels == 2) && !line_start) begin
                $fatal(1, "Processed first pixel of line %0d did not assert line_start", pixel_y);
            end
            if (observed_pixels != 0 && frame_start) begin
                $fatal(1, "Processed frame_start asserted more than once");
            end
            if (observed_pixels != 0 && observed_pixels != 2 && line_start) begin
                $fatal(1, "Processed line_start asserted on a non-first pixel");
            end
            observed_pixels = observed_pixels + 1;
        end
        if (line_start) begin
            observed_line_starts = observed_line_starts + 1;
        end
        if (line_end) begin
            observed_line_ends = observed_line_ends + 1;
        end
        if (frame_start) begin
            observed_frame_starts = observed_frame_starts + 1;
        end
        if (frame_end) begin
            observed_frame_ends = observed_frame_ends + 1;
        end
        if (protocol_error) begin
            observed_errors = observed_errors + 1;
        end
    end

    task automatic drive_byte(input logic [7:0] value);
        begin
            cam_data = value;
            @(posedge cam_pclk);
        end
    endtask

    task automatic drive_line(
        input logic [15:0] pixel0,
        input logic [15:0] pixel1
    );
        begin
            cam_href = 1'b1;
            drive_byte(pixel0[15:8]);
            drive_byte(pixel0[7:0]);
            drive_byte(pixel1[15:8]);
            drive_byte(pixel1[7:0]);
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

    // A bounded watchdog prevents a broken pipeline from hanging CI.
    initial begin
        #20us;
        $fatal(1, "OV5640 capture pipeline test timeout");
    end

    initial begin
        expected_data[0] = 16'h0000;
        expected_data[1] = 16'h4a69;
        expected_data[2] = 16'h94b2;
        expected_data[3] = 16'h18e3;
        expected_x[0] = 0;
        expected_x[1] = 1;
        expected_x[2] = 0;
        expected_x[3] = 1;
        expected_y[0] = 0;
        expected_y[1] = 0;
        expected_y[2] = 1;
        expected_y[3] = 1;
        observed_pixels = 0;
        observed_line_starts = 0;
        observed_line_ends = 0;
        observed_frame_starts = 0;
        observed_frame_ends = 0;
        observed_errors = 0;

        repeat (2) @(posedge cam_pclk);
        rst_n = 1'b1;
        @(posedge cam_pclk);

        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        @(posedge cam_pclk);

        drive_line(16'h0000, 16'hf800);
        drive_line(16'h07e0, 16'h001f);

        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        drive_odd_byte_line(8'hde);
        repeat (3) @(posedge cam_pclk);

        if (observed_pixels != PIXEL_COUNT) begin
            $fatal(1, "Processed pixel count mismatch: observed=%0d expected=%0d",
                observed_pixels, PIXEL_COUNT);
        end
        if (observed_line_starts != 2 || observed_line_ends != 2) begin
            $fatal(1, "Processed line boundary mismatch: starts=%0d ends=%0d",
                observed_line_starts, observed_line_ends);
        end
        if (observed_frame_starts != 1 || observed_frame_ends != 1) begin
            $fatal(1, "Processed frame boundary mismatch: starts=%0d ends=%0d",
                observed_frame_starts, observed_frame_ends);
        end
        if (observed_errors != 1) begin
            $fatal(1, "Processed odd-byte error mismatch: observed=%0d expected=1",
                observed_errors);
        end

        $display("INFO: OV5640 capture-to-grayscale pipeline verified");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
