`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_dvp_rgb565_capture.sv
 * @brief Self-checking behavior test for the board-independent DVP capture.
 *
 * @details
 * The test presents one VSYNC frame marker followed by two HREF-qualified
 * lines. Each line contains three RGB565 pixels in high-byte-first order.
 * The public pixel stream, coordinates, frame/line starts, line ends, and
 * the next-frame boundary are checked. Sensor register programming and board
 * electrical timing are outside this test.
 *
 * @par Test contract
 * - A pixel is accepted on every second HREF-qualified byte.
 * - `frame_start` marks the first pixel after a VSYNC frame marker.
 * - `line_start` marks the first pixel of each HREF-qualified line.
 * - `line_end` is reported on the first clock after HREF deasserts.
 * - `frame_end` marks the next VSYNC frame marker after a frame was seen.
 *
 * @warning
 * The test intentionally uses a small frame so failures identify byte order
 * and boundary semantics without depending on a vendor simulation library.
 */
module tb_ov5640_dvp_rgb565_capture;

    localparam time PCLK_HALF_PERIOD = 5ns;
    localparam int unsigned PIXEL_COUNT = 6;

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
    int unsigned observed_line_ends;
    int unsigned observed_frame_ends;
    int unsigned observed_frame_starts;
    int unsigned observed_line_starts;
    int unsigned observed_errors;

    ov5640_dvp_rgb565_capture u_dut (
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

    // Intent: Check only public stream behavior; do not couple the test to RTL state.
    always @(posedge cam_pclk) begin
        #1ns;
        if (pixel_valid) begin
            if (observed_pixels >= PIXEL_COUNT) begin
                $fatal(1, "Observed more pixels than expected");
            end
            if (pixel_data !== expected_data[observed_pixels] ||
                pixel_x !== expected_x[observed_pixels] ||
                pixel_y !== expected_y[observed_pixels]) begin
                $fatal(1,
                    "Pixel %0d mismatch: data=%h x=%0d y=%0d expected=%h x=%0d y=%0d",
                    observed_pixels,
                    pixel_data,
                    pixel_x,
                    pixel_y,
                    expected_data[observed_pixels],
                    expected_x[observed_pixels],
                    expected_y[observed_pixels]);
            end
            if ((observed_pixels == 0) && !frame_start) begin
                $fatal(1, "First pixel did not assert frame_start");
            end
            if ((observed_pixels == 0 || observed_pixels == 3) && !line_start) begin
                $fatal(1, "First pixel of line %0d did not assert line_start", pixel_y);
            end
            if (observed_pixels != 0 && frame_start) begin
                $fatal(1, "frame_start asserted more than once");
            end
            if (observed_pixels != 0 && observed_pixels != 3 && line_start) begin
                $fatal(1, "line_start asserted on a non-first pixel");
            end
            observed_pixels = observed_pixels + 1;
        end
        if (line_end) begin
            observed_line_ends = observed_line_ends + 1;
        end
        if (frame_end) begin
            observed_frame_ends = observed_frame_ends + 1;
        end
        if (frame_start) begin
            observed_frame_starts = observed_frame_starts + 1;
        end
        if (line_start) begin
            observed_line_starts = observed_line_starts + 1;
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
        input logic [15:0] pixel1,
        input logic [15:0] pixel2
    );
        begin
            cam_href = 1'b1;
            drive_byte(pixel0[15:8]);
            drive_byte(pixel0[7:0]);
            drive_byte(pixel1[15:8]);
            drive_byte(pixel1[7:0]);
            drive_byte(pixel2[15:8]);
            drive_byte(pixel2[7:0]);
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

    // A bounded watchdog keeps a broken capture implementation from hanging CI.
    initial begin
        #20us;
        $fatal(1, "OV5640 DVP capture test timeout");
    end

    initial begin
        expected_data[0] = 16'h1234;
        expected_data[1] = 16'habcd;
        expected_data[2] = 16'h55aa;
        expected_data[3] = 16'h0f10;
        expected_data[4] = 16'hbeef;
        expected_data[5] = 16'hc001;
        expected_x[0] = 0;
        expected_x[1] = 1;
        expected_x[2] = 2;
        expected_x[3] = 0;
        expected_x[4] = 1;
        expected_x[5] = 2;
        expected_y[0] = 0;
        expected_y[1] = 0;
        expected_y[2] = 0;
        expected_y[3] = 1;
        expected_y[4] = 1;
        expected_y[5] = 1;

        observed_pixels = 0;
        observed_line_ends = 0;
        observed_frame_ends = 0;
        observed_frame_starts = 0;
        observed_line_starts = 0;
        observed_errors = 0;

        repeat (2) @(posedge cam_pclk);
        rst_n = 1'b1;
        @(posedge cam_pclk);

        // VSYNC is a frame boundary marker; HREF qualifies active line data.
        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;
        @(posedge cam_pclk);

        drive_line(16'h1234, 16'habcd, 16'h55aa);
        drive_line(16'h0f10, 16'hbeef, 16'hc001);

        // The next frame marker closes the frame just transmitted.
        cam_vsync = 1'b1;
        @(posedge cam_pclk);
        cam_vsync = 1'b0;

        // An incomplete RGB565 pair must be rejected at the HREF boundary.
        drive_odd_byte_line(8'hde);
        repeat (2) @(posedge cam_pclk);

        if (observed_pixels != PIXEL_COUNT) begin
            $fatal(1, "Pixel count mismatch: observed=%0d expected=%0d",
                observed_pixels, PIXEL_COUNT);
        end
        if (observed_line_ends != 2 || observed_line_starts != 2) begin
            $fatal(1, "Line boundary mismatch: starts=%0d ends=%0d",
                observed_line_starts, observed_line_ends);
        end
        if (observed_frame_starts != 1 || observed_frame_ends != 1) begin
            $fatal(1, "Frame boundary mismatch: starts=%0d ends=%0d",
                observed_frame_starts, observed_frame_ends);
        end
        if (observed_errors != 1) begin
            $fatal(1, "Odd-byte protocol error mismatch: observed=%0d expected=1",
                observed_errors);
        end

        $display("INFO: OV5640 DVP RGB565 capture behavior verified");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
