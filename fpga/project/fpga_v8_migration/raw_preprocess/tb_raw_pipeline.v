`timescale 1ns/1ps
module tb_raw_pipeline;
    parameter integer WIDTH = 640;
    parameter integer HEIGHT = 480;
    parameter integer OUT_HEIGHT = 640;
    parameter integer TOP_ROWS = 80;
    parameter integer FILL_VALUE = 114;
    parameter integer FRAMES = 3;
    localparam SOURCE_PIXELS = WIDTH * HEIGHT;
    localparam OUTPUT_PIXELS = WIDTH * OUT_HEIGHT;
    localparam WORDS = (OUTPUT_PIXELS * 3 + 15) / 16;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst_n = 1'b0;
    reg start_valid = 1'b0;
    wire start_ready, busy, done, frame_error, config_error;
    reg [15:0] s_data = 16'd0;
    reg s_valid = 1'b0;
    wire s_ready;
    reg s_last = 1'b0;
    wire [23:0] rgb_data;
    wire rgb_valid, rgb_ready, rgb_last;
    wire [127:0] packed_data;
    wire [15:0] packed_keep;
    wire packed_valid, packed_last;
    reg packed_ready = 1'b0;
    reg [15:0] sources [0:SOURCE_PIXELS*FRAMES-1];
    reg [23:0] pixels [0:OUTPUT_PIXELS*FRAMES-1];
    reg [127:0] words [0:WORDS*FRAMES-1];
    reg [15:0] keeps [0:WORDS*FRAMES-1];
    integer frame_index = 0;
    integer source_count = 0;
    integer driven_index = -1;
    integer pixel_count = 0;
    integer word_count = 0;
    integer cycles = 0;
    integer start_cycle = 0;
    integer rgb_end_cycle = 0;
    integer packed_end_cycle = 0;
    integer done_count = 0;
    integer stalls = 0;
    integer source_run = 0;
    integer source_run_max = 0;
    integer pixel_run = 0;
    integer pixel_run_max = 0;
    integer marker_mode = 0;
    integer random_stalls = 1;
    integer final_stall = 0;
    integer hold_final = 0;
    integer timeout_count;
    integer output_file, stats_file;
    reg active = 1'b0;
    reg error_expected = 1'b0;
    reg final_forced = 1'b0;
    reg [31:0] random_state = 32'h5a174b39;
    reg rgb_stalled = 1'b0;
    reg packed_stalled = 1'b0;
    reg [23:0] held_rgb;
    reg held_rgb_last;
    reg [127:0] held_packed;
    reg [15:0] held_keep;
    reg held_packed_last;
    reg final_rgb_fire;

    fpga_v8_raw_letterbox #(.WIDTH(WIDTH), .HEIGHT(HEIGHT),
        .OUT_HEIGHT(OUT_HEIGHT), .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE)) dut (
        .clk(clk), .rst_n(rst_n), .start_valid(start_valid),
        .start_ready(start_ready), .busy(busy), .done(done),
        .frame_error(frame_error), .config_error(config_error),
        .s_data(s_data), .s_valid(s_valid), .s_ready(s_ready), .s_last(s_last),
        .m_data(rgb_data), .m_valid(rgb_valid), .m_ready(rgb_ready), .m_last(rgb_last));
    fpga_v8_rgb888_pack128 packer (
        .clk(clk), .rst_n(rst_n), .s_data(rgb_data), .s_valid(rgb_valid),
        .s_ready(rgb_ready), .s_last(rgb_last), .m_data(packed_data),
        .m_keep(packed_keep), .m_valid(packed_valid), .m_ready(packed_ready),
        .m_last(packed_last));

    task fail;
        input [511:0] reason;
        begin
            $display("FAIL pipeline frame=%0d cycle=%0d src=%0d pix=%0d word=%0d: %0s",
                frame_index, cycles, source_count, pixel_count, word_count, reason);
            $finish;
        end
    endtask
    function [31:0] next_random;
        input [31:0] value;
        reg [31:0] temp;
        begin
            temp = value ^ (value << 13);
            temp = temp ^ (temp >> 17);
            next_random = temp ^ (temp << 5);
        end
    endfunction

    // Legal source: valid/data/last are held until accepted. Inputs deliberately
    // vary while idle and after all expected RAW pixels have been accepted.
    always @(negedge clk) begin
        if (rst_n && active) begin
            random_state = next_random(random_state);
            if (source_count < SOURCE_PIXELS) begin
                if (!s_valid || driven_index != source_count) begin
                    s_valid = !random_stalls || (random_state[3:0] > 3);
                    s_data = sources[frame_index*SOURCE_PIXELS + source_count];
                    driven_index = source_count;
                    if (marker_mode == 1)
                        s_last = (source_count == 1);
                    else if (marker_mode == 2)
                        s_last = 1'b0;
                    else
                        s_last = (source_count == SOURCE_PIXELS - 1);
                end
            end else begin
                s_valid = (marker_mode == 2);
                s_last = 1'b1;
                s_data = 16'h464b;
            end
            packed_ready = !random_stalls || (random_state[7:4] > 4);
            if (final_stall && packed_valid && packed_last && !final_forced) begin
                final_forced = 1'b1;
                hold_final = 7;
            end
            if (hold_final > 0) begin
                packed_ready = 1'b0;
                hold_final = hold_final - 1;
            end
        end else if (!rst_n || !active) begin
            s_valid = 1'b0;
            packed_ready = 1'b1;
        end
    end

    always @(posedge clk) begin
        cycles = cycles + 1;
        final_rgb_fire = rst_n && rgb_valid && rgb_ready && rgb_last;
        if (rst_n) begin
            if (config_error) fail("Unexpected configuration error");
            if (busy && start_ready) fail("Command accepted while busy");
            if (rgb_stalled && (!rgb_valid || rgb_data !== held_rgb ||
                               rgb_last !== held_rgb_last))
                fail("RGB output changed under backpressure");
            if (packed_stalled && (!packed_valid || packed_data !== held_packed ||
                packed_keep !== held_keep || packed_last !== held_packed_last))
                fail("Packed output changed under backpressure");
            rgb_stalled = rgb_valid && !rgb_ready;
            held_rgb = rgb_data;
            held_rgb_last = rgb_last;
            packed_stalled = packed_valid && !packed_ready;
            held_packed = packed_data;
            held_keep = packed_keep;
            held_packed_last = packed_last;
            if (start_valid && start_ready) begin
                start_cycle = cycles;
                error_expected = 1'b0;
            end
            if (s_valid && s_ready) begin
                if (!active || source_count >= SOURCE_PIXELS)
                    fail("Surplus or idle source pixel consumed");
                if (pixel_count + (rgb_valid && rgb_ready) < WIDTH*TOP_ROWS)
                    fail("Source consumed during top padding");
                if (s_last != (source_count == SOURCE_PIXELS - 1))
                    error_expected = 1'b1;
                source_count = source_count + 1;
                source_run = source_run + 1;
                if (source_run > source_run_max) source_run_max = source_run;
            end else source_run = 0;
            if (rgb_valid && rgb_ready) begin
                if (!active || pixel_count >= OUTPUT_PIXELS)
                    fail("Ghost RGB pixel");
                if (rgb_data !== pixels[frame_index*OUTPUT_PIXELS + pixel_count])
                    fail("RGB pixel differs from Python golden");
                if (rgb_last != (pixel_count == OUTPUT_PIXELS - 1))
                    fail("RGB last at wrong position");
                pixel_count = pixel_count + 1;
                pixel_run = pixel_run + 1;
                if (pixel_run > pixel_run_max) pixel_run_max = pixel_run;
                if (rgb_last) rgb_end_cycle = cycles;
            end else pixel_run = 0;
            if (packed_valid && !packed_ready) stalls = stalls + 1;
            if (packed_valid && packed_ready) begin
                if (!active || word_count >= WORDS) fail("Ghost packed word");
                if (packed_data !== words[frame_index*WORDS + word_count] ||
                    packed_keep !== keeps[frame_index*WORDS + word_count])
                    fail("Packed data/keep differs from Python golden");
                if (packed_last != (word_count == WORDS - 1))
                    fail("Packed last at wrong word");
                $fwrite(output_file, "%032h %04h %0d %0d\n", packed_data,
                        packed_keep, packed_last, cycles);
                word_count = word_count + 1;
                if (packed_last) packed_end_cycle = cycles;
            end
            #1;
            if (done !== final_rgb_fire) fail("Done must pulse on final RGB consumption");
            if (done) begin
                done_count = done_count + 1;
                if (busy) fail("Busy remained set after final RGB consumption");
            end
            if (frame_error !== error_expected) fail("Frame error not sticky/correct");
        end else begin
            rgb_stalled = 1'b0;
            packed_stalled = 1'b0;
        end
    end

    initial begin
        timeout_count = $value$plusargs("MARKER_MODE=%d", marker_mode);
        timeout_count = $value$plusargs("STALLS=%d", random_stalls);
        timeout_count = $value$plusargs("FINAL_STALL=%d", final_stall);
        $readmemh("source.hex", sources);
        $readmemh("pixels.hex", pixels);
        $readmemh("words.hex", words);
        $readmemh("keeps.hex", keeps);
        output_file = $fopen("actual_words.txt", "w");
        stats_file = $fopen("cycles.txt", "w");
        repeat (4) @(negedge clk);
        rst_n = 1'b1;
        for (frame_index = 0; frame_index < FRAMES; frame_index = frame_index + 1) begin
            @(negedge clk);
            source_count = 0;
            driven_index = -1;
            pixel_count = 0;
            word_count = 0;
            source_run_max = 0;
            pixel_run_max = 0;
            source_run = 0;
            pixel_run = 0;
            stalls = 0;
            final_forced = 1'b0;
            active = 1'b1;
            start_valid = 1'b1;
            @(posedge clk);
            if (!start_ready) fail("Start not ready between frames");
            @(negedge clk);
            start_valid = 1'b0;
            timeout_count = 0;
            while (word_count < WORDS || done_count <= frame_index) begin
                @(negedge clk);
                timeout_count = timeout_count + 1;
                if (timeout_count > OUTPUT_PIXELS*20 + 500) fail("Timeout");
            end
            if (source_count != SOURCE_PIXELS || pixel_count != OUTPUT_PIXELS)
                fail("Frame count mismatch");
            if (frame_error != (marker_mode != 0)) fail("Wrong final error status");
            $fwrite(stats_file, "%0d %0d %0d %0d %0d %0d\n", frame_index,
                rgb_end_cycle - start_cycle, packed_end_cycle - start_cycle,
                source_run_max, pixel_run_max, stalls);
            $display("FRAME %0d RGB_CYCLES=%0d PACKED_CYCLES=%0d SOURCE_RUN=%0d PIXEL_RUN=%0d STALLS=%0d",
                frame_index, rgb_end_cycle-start_cycle, packed_end_cycle-start_cycle,
                source_run_max, pixel_run_max, stalls);
            active = 1'b0;
            repeat (3) @(negedge clk);
        end
        repeat (8) @(negedge clk);
        $fclose(output_file);
        $fclose(stats_file);
        $display("PASS tb_raw_pipeline");
        $finish;
    end
endmodule
