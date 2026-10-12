// Isolated V5 adapter: bitwise increment avoids a shared conditional-add CE chain.
module motion_stream_adapter_tc05_test #(
    parameter integer WIDTH = 640, HEIGHT = 480,
    parameter SAMPLE_STEP = 4,
    parameter BLOCK_SAMPLES_X = 10, BLOCK_SAMPLES_Y = 10,
    parameter PIXEL_THRESHOLD = 16, BLOCK_THRESHOLD = 8
) (
    input wire clk, rst_n,
    input wire [15:0] pixel_rgb565,
    input wire pixel_valid, vsync,
    output reg [319:0] motion_record
);
    localparam integer TOTAL = WIDTH * HEIGHT;
    localparam SC = (WIDTH + SAMPLE_STEP - 1) / SAMPLE_STEP;
    localparam SR = (HEIGHT + SAMPLE_STEP - 1) / SAMPLE_STEP;
    localparam BC = (SC + BLOCK_SAMPLES_X - 1) / BLOCK_SAMPLES_X;
    localparam BR = (SR + BLOCK_SAMPLES_Y - 1) / BLOCK_SAMPLES_Y;
    reg vs_q, acquired;
    wire rise = vsync && !vs_q;
    reg [17:0] events [0:15];
    reg [31:0] event_sequences [0:15];
    reg [3:0] wr_ptr, rd_ptr;
    reg [4:0] queued;
    reg head_started, active, end_pending, tail_seen, tail_bad;
    reg [2:0] marker_idle;
    wire boundary_busy = marker_idle != 0;
    reg [$clog2(TOTAL+1)-1:0] pixels;
    reg [31:0] source_sequence, active_sequence, publish_sequence;
    reg overflow_reset;
    reg [31:0] overflow_count;
    reg error_pending, publish_error;
    reg [31:0] short_frame_count;
    wire push = (acquired || rise) && (rise || pixel_valid);
    wire have = queued != 0;
    wire [17:0] head = events[rd_ptr];
    wire start = have && head[17] && !head_started && !boundary_busy;
    wire excess = have && !start && !boundary_busy && head[16] &&
                  !active && tail_seen && !tail_bad;
    wire pop = have && !boundary_busy && (!start || !head[16]);
    wire overflow = push && queued == 16 && !pop;
    wire fire = have && !start && !boundary_busy && head[16] && active &&
                !overflow && !overflow_reset;
    // Every bit has its own XOR toggle, rather than a common increment CE.
    // Clear priority is exactly the original reset/overflow/start priority.
    genvar pb;
    generate for (pb=0; pb<$clog2(TOTAL+1); pb=pb+1) begin : g_pixels
        wire carry;
        if (pb == 0) assign carry = 1'b1;
        else assign carry = &pixels[pb-1:0];
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) pixels[pb] <= 1'b0;
            else pixels[pb] <= (pixels[pb] ^ (fire && carry)) &
                               !(overflow || overflow_reset || start);
        end
    end endgenerate
    reg core_start, core_end, core_valid;
    reg [15:0] core_rgb;
    wire strobe, comparison_valid, bbox_valid;
    wire [BC*BR-1:0] bitmap;
    wire [$clog2(BC*BR+1)-1:0] blocks;
    wire [$clog2(SC*SR+1)-1:0] samples;
    wire [((BC > 1) ? $clog2(BC) : 1)-1:0] minx, maxx;
    wire [((BR > 1) ? $clog2(BR) : 1)-1:0] miny, maxy;
    wire [191:0] bitmap_word = bitmap;
    wire [15:0] sample_word = samples;
    wire [7:0] block_word = blocks;
    wire [3:0] minx_word = minx, maxx_word = maxx;
    wire [3:0] miny_word = miny, maxy_word = maxy;
    block_motion_detector_tc05 #(
        .WIDTH(WIDTH), .HEIGHT(HEIGHT), .SAMPLE_STEP(SAMPLE_STEP),
        .BLOCK_SAMPLES_X(BLOCK_SAMPLES_X), .BLOCK_SAMPLES_Y(BLOCK_SAMPLES_Y),
        .PIXEL_THRESHOLD(PIXEL_THRESHOLD), .BLOCK_THRESHOLD(BLOCK_THRESHOLD)
    ) u_detector (
        .clk(clk), .rst_n(rst_n && !overflow_reset), .frame_start(core_start),
        .frame_end(core_end), .pixel_valid(core_valid), .pixel_rgb565(core_rgb),
        .result_strobe(strobe), .result_valid(comparison_valid),
        .block_bitmap(bitmap), .changed_blocks(blocks), .changed_samples(samples),
        .bbox_valid(bbox_valid), .bbox_min_x(minx), .bbox_max_x(maxx),
        .bbox_min_y(miny), .bbox_max_y(maxy), .frame_sequence()
    );
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vs_q <= 0; acquired <= 0; wr_ptr <= 0; rd_ptr <= 0; queued <= 0;
            head_started <= 0; active <= 0; end_pending <= 0;
            marker_idle <= 0;
            core_start <= 0; core_end <= 0; core_valid <= 0; core_rgb <= 0;
            tail_seen <= 0; tail_bad <= 0;
            source_sequence <= 0; active_sequence <= 0; publish_sequence <= 0;
            overflow_reset <= 0; overflow_count <= 0;
            error_pending <= 0; publish_error <= 0; short_frame_count <= 0;
            motion_record <= 0;
        end else begin
            vs_q <= vsync;
            if (rise) source_sequence <= source_sequence + 1'b1;
            overflow_reset <= overflow;
            if (overflow || overflow_reset) begin
                acquired <= 0; wr_ptr <= 0; rd_ptr <= 0; queued <= 0;
                head_started <= 0; active <= 0; end_pending <= 0;
                marker_idle <= 0;
                core_start <= 0; core_end <= 0; core_valid <= 0; core_rgb <= 0;
                tail_seen <= 0; tail_bad <= 0;
                error_pending <= 1;
                if (overflow) overflow_count <= overflow_count + 1'b1;
            end else begin
                core_start <= start || excess;
                core_end <= end_pending;
                core_valid <= fire;
                core_rgb <= head[15:0];
                if (boundary_busy) marker_idle <= marker_idle - 1'b1;
                if (rise) acquired <= 1;
                if (push) begin
                    events[wr_ptr] <= {rise, pixel_valid, pixel_rgb565};
                    event_sequences[wr_ptr] <= rise ? source_sequence + 1'b1 : source_sequence;
                    wr_ptr <= wr_ptr + 1'b1;
                end
                case ({push,pop})
                    2'b10: queued <= queued + 1'b1;
                    2'b01: queued <= queued - 1'b1;
                    default: queued <= queued;
                endcase
                if (pop) begin rd_ptr <= rd_ptr + 1'b1; head_started <= 0; end
                if (start) begin
                    if (head[16]) head_started <= 1;
                    if (active) begin
                        error_pending <= 1;
                        short_frame_count <= short_frame_count + 1'b1;
                    end
                    active_sequence <= event_sequences[rd_ptr];
                    active <= 1; tail_seen <= 0; tail_bad <= 0;
                end
                if (fire) begin
                    if (pixels == TOTAL-1) begin
                        active <= 0; end_pending <= 1; marker_idle <= 4;
                        publish_sequence <= active_sequence;
                        publish_error <= error_pending;
                        error_pending <= 0;
                    end
                end
                if (end_pending) end_pending <= 0;
                if (have && !start && !boundary_busy && head[16] && !active) begin
                    tail_seen <= 1;
                    if (excess) begin tail_bad <= 1; error_pending <= 1; end
                end
                if (strobe) motion_record <= {
                    bitmap_word, 16'b0, maxy_word, miny_word, maxx_word, minx_word,
                    8'b0, sample_word, block_word,
                    29'b0, publish_error, bbox_valid, comparison_valid, publish_sequence
                };
            end
        end
    end
endmodule
