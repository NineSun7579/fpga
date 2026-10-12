// Sideband RGB565 detector. See project/sim/motion/README.md for timing.
module block_motion_detector #(
    parameter integer WIDTH = 640,
    parameter integer HEIGHT = 480,
    parameter SAMPLE_STEP = 4,
    parameter BLOCK_SAMPLES_X = 10,
    parameter BLOCK_SAMPLES_Y = 10,
    parameter PIXEL_THRESHOLD = 16,
    parameter BLOCK_THRESHOLD = 8,
    // Derived geometry parameters: do not override independently.
    parameter SAMPLE_COLS = (WIDTH + SAMPLE_STEP - 1) / SAMPLE_STEP,
    parameter SAMPLE_ROWS = (HEIGHT + SAMPLE_STEP - 1) / SAMPLE_STEP,
    parameter BLOCK_COLS = (SAMPLE_COLS + BLOCK_SAMPLES_X - 1) / BLOCK_SAMPLES_X,
    parameter BLOCK_ROWS = (SAMPLE_ROWS + BLOCK_SAMPLES_Y - 1) / BLOCK_SAMPLES_Y
) (
    input wire clk,
    input wire rst_n,
    input wire frame_start,
    input wire frame_end,
    input wire pixel_valid,
    input wire [15:0] pixel_rgb565,
    output reg result_strobe,
    output reg result_valid,
    output reg [BLOCK_COLS*BLOCK_ROWS-1:0] block_bitmap,
    output reg [$clog2(BLOCK_COLS*BLOCK_ROWS+1)-1:0] changed_blocks,
    output reg [$clog2(SAMPLE_COLS*SAMPLE_ROWS+1)-1:0] changed_samples,
    output reg bbox_valid,
    output reg [((BLOCK_COLS > 1) ? $clog2(BLOCK_COLS) : 1)-1:0] bbox_min_x,
    output reg [((BLOCK_COLS > 1) ? $clog2(BLOCK_COLS) : 1)-1:0] bbox_max_x,
    output reg [((BLOCK_ROWS > 1) ? $clog2(BLOCK_ROWS) : 1)-1:0] bbox_min_y,
    output reg [((BLOCK_ROWS > 1) ? $clog2(BLOCK_ROWS) : 1)-1:0] bbox_max_y,
    output reg [31:0] frame_sequence
);
    localparam integer TOTAL_PIXELS = WIDTH * HEIGHT;
    localparam TOTAL_SAMPLES = SAMPLE_COLS * SAMPLE_ROWS;
    localparam TOTAL_BLOCKS = BLOCK_COLS * BLOCK_ROWS;
    localparam X_BITS = (WIDTH > 1) ? $clog2(WIDTH) : 1;
    localparam Y_BITS = (HEIGHT > 1) ? $clog2(HEIGHT) : 1;
    localparam ADDR_BITS = (TOTAL_SAMPLES > 1) ? $clog2(TOTAL_SAMPLES) : 1;
    localparam BLOCK_BITS = (TOTAL_BLOCKS > 1) ? $clog2(TOTAL_BLOCKS) : 1;
    localparam BX_BITS = (BLOCK_COLS > 1) ? $clog2(BLOCK_COLS) : 1;
    localparam BY_BITS = (BLOCK_ROWS > 1) ? $clog2(BLOCK_ROWS) : 1;
    localparam COUNT_BITS = $clog2(BLOCK_THRESHOLD + 1);

    reg active, reference_valid;
    reg [$clog2(TOTAL_PIXELS+1)-1:0] pixel_count;
    reg [X_BITS-1:0] x;
    reg [Y_BITS-1:0] y;
    reg [ADDR_BITS-1:0] sample_address;
    wire accept_pixel = active && pixel_valid && !frame_start && !frame_end &&
                        (pixel_count < TOTAL_PIXELS);
    wire accept_sample = accept_pixel && ((x % SAMPLE_STEP) == 0) &&
                         ((y % SAMPLE_STEP) == 0);
    wire [BX_BITS-1:0] sample_bx = (x / SAMPLE_STEP) / BLOCK_SAMPLES_X;
    wire [BY_BITS-1:0] sample_by = (y / SAMPLE_STEP) / BLOCK_SAMPLES_Y;
    wire [BLOCK_BITS-1:0] sample_block = sample_by * BLOCK_COLS + sample_bx;

    wire [7:0] red = {pixel_rgb565[15:11], pixel_rgb565[15:13]};
    wire [7:0] green = {pixel_rgb565[10:5], pixel_rgb565[10:9]};
    wire [7:0] blue = {pixel_rgb565[4:0], pixel_rgb565[4:2]};
    wire [9:0] luma_sum = {2'b0, red} + {1'b0, green, 1'b0} + {2'b0, blue};
    wire [7:0] luma = luma_sum[9:2];

    // No reset/clear of this array or read register: synchronous read-first
    // single-port RAM template. Each sampled address is touched once/frame.
    reg [7:0] history [0:TOTAL_SAMPLES-1];
    reg [7:0] history_q;
    always @(posedge clk) begin
        if (rst_n && accept_sample) begin
            history_q <= history[sample_address];
            history[sample_address] <= luma;
        end
    end

    reg compare_pending, compare_enabled;
    reg [7:0] current_q;
    reg [BLOCK_BITS-1:0] block_q;
    reg [BX_BITS-1:0] bx_q;
    reg [BY_BITS-1:0] by_q;
    wire [7:0] difference = (current_q >= history_q) ?
                            current_q - history_q : history_q - current_q;
    reg [COUNT_BITS-1:0] block_hits [0:TOTAL_BLOCKS-1];
    reg [TOTAL_BLOCKS-1:0] bitmap_work;
    reg [$clog2(TOTAL_BLOCKS+1)-1:0] blocks_work;
    reg [$clog2(TOTAL_SAMPLES+1)-1:0] samples_work;
    reg bbox_work_valid;
    reg [BX_BITS-1:0] min_x_work, max_x_work;
    reg [BY_BITS-1:0] min_y_work, max_y_work;
    reg publish_pending, publish_comparison_valid;
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 0;
            reference_valid <= 0;
            pixel_count <= 0;
            x <= 0;
            y <= 0;
            sample_address <= 0;
            compare_pending <= 0;
            compare_enabled <= 0;
            current_q <= 0;
            block_q <= 0;
            bx_q <= 0;
            by_q <= 0;
            publish_pending <= 0;
            publish_comparison_valid <= 0;
            bitmap_work <= 0;
            blocks_work <= 0;
            samples_work <= 0;
            bbox_work_valid <= 0;
            min_x_work <= 0;
            max_x_work <= 0;
            min_y_work <= 0;
            max_y_work <= 0;
            result_strobe <= 0;
            result_valid <= 0;
            block_bitmap <= 0;
            changed_blocks <= 0;
            changed_samples <= 0;
            bbox_valid <= 0;
            bbox_min_x <= 0;
            bbox_max_x <= 0;
            bbox_min_y <= 0;
            bbox_max_y <= 0;
            frame_sequence <= 0;
            for (i = 0; i < TOTAL_BLOCKS; i = i + 1)
                block_hits[i] <= 0;
        end else begin
            result_strobe <= 0;
            result_valid <= 0;
            publish_pending <= 0;
            compare_pending <= accept_sample;
            if (accept_sample) begin
                current_q <= luma;
                block_q <= sample_block;
                bx_q <= sample_bx;
                by_q <= sample_by;
                compare_enabled <= reference_valid;
            end

            // Runs independently of start: a new start may coincide with
            // publication, which reads the old work registers before clearing.
            if (publish_pending) begin
                result_strobe <= 1;
                result_valid <= publish_comparison_valid;
                block_bitmap <= bitmap_work;
                changed_blocks <= blocks_work;
                changed_samples <= samples_work;
                bbox_valid <= bbox_work_valid;
                bbox_min_x <= min_x_work;
                bbox_max_x <= max_x_work;
                bbox_min_y <= min_y_work;
                bbox_max_y <= max_y_work;
                frame_sequence <= frame_sequence + 1'b1;
            end

            if (frame_start) begin
                // A restart without end may have overwritten part of history.
                if (active)
                    reference_valid <= 0;
                active <= 1;
                pixel_count <= 0;
                x <= 0;
                y <= 0;
                sample_address <= 0;
                compare_pending <= 0;
                bitmap_work <= 0;
                blocks_work <= 0;
                samples_work <= 0;
                bbox_work_valid <= 0;
                min_x_work <= 0;
                max_x_work <= 0;
                min_y_work <= 0;
                max_y_work <= 0;
                for (i = 0; i < TOTAL_BLOCKS; i = i + 1)
                    block_hits[i] <= 0;
            end else begin
                if (compare_pending && compare_enabled && difference >= PIXEL_THRESHOLD) begin
                    samples_work <= samples_work + 1'b1;
                    if (block_hits[block_q] < BLOCK_THRESHOLD) begin
                        block_hits[block_q] <= block_hits[block_q] + 1'b1;
                        if (block_hits[block_q] == BLOCK_THRESHOLD - 1) begin
                            bitmap_work[block_q] <= 1'b1;
                            blocks_work <= blocks_work + 1'b1;
                            bbox_work_valid <= 1;
                            if (!bbox_work_valid || bx_q < min_x_work) min_x_work <= bx_q;
                            if (!bbox_work_valid || bx_q > max_x_work) max_x_work <= bx_q;
                            if (!bbox_work_valid || by_q < min_y_work) min_y_work <= by_q;
                            if (!bbox_work_valid || by_q > max_y_work) max_y_work <= by_q;
                        end
                    end
                end
                if (accept_pixel) begin
                    pixel_count <= pixel_count + 1'b1;
                    if (x == WIDTH - 1) begin
                        x <= 0;
                        if (y != HEIGHT - 1) y <= y + 1'b1;
                    end else x <= x + 1'b1;
                    if (accept_sample && sample_address != TOTAL_SAMPLES - 1)
                        sample_address <= sample_address + 1'b1;
                end
                if (frame_end && active) begin
                    active <= 0;
                    if (pixel_count == TOTAL_PIXELS) begin
                        publish_pending <= 1;
                        publish_comparison_valid <= reference_valid;
                        reference_valid <= 1;
                    end else reference_valid <= 0;
                end
            end
        end
    end
endmodule
