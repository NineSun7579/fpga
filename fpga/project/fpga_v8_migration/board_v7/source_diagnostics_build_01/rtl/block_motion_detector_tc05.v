// TC05: register state-only history eligibility with next-state lookahead.
// Current frame markers/valid still gate the same-edge read-first history write.
// Compare/update/publish and bbox logic are unchanged from TC03.
module block_motion_detector_tc05 #(
    parameter integer WIDTH=640, HEIGHT=480,
    parameter SAMPLE_STEP=4, BLOCK_SAMPLES_X=10, BLOCK_SAMPLES_Y=10,
    parameter PIXEL_THRESHOLD=16, BLOCK_THRESHOLD=8,
    parameter SAMPLE_COLS=(WIDTH+SAMPLE_STEP-1)/SAMPLE_STEP,
    parameter SAMPLE_ROWS=(HEIGHT+SAMPLE_STEP-1)/SAMPLE_STEP,
    parameter BLOCK_COLS=(SAMPLE_COLS+BLOCK_SAMPLES_X-1)/BLOCK_SAMPLES_X,
    parameter BLOCK_ROWS=(SAMPLE_ROWS+BLOCK_SAMPLES_Y-1)/BLOCK_SAMPLES_Y
) (
    input wire clk, rst_n, frame_start, frame_end, pixel_valid,
    input wire [15:0] pixel_rgb565,
    output reg result_strobe, result_valid,
    output reg [BLOCK_COLS*BLOCK_ROWS-1:0] block_bitmap,
    output reg [$clog2(BLOCK_COLS*BLOCK_ROWS+1)-1:0] changed_blocks,
    output reg [$clog2(SAMPLE_COLS*SAMPLE_ROWS+1)-1:0] changed_samples,
    output reg bbox_valid,
    output reg [((BLOCK_COLS>1)?$clog2(BLOCK_COLS):1)-1:0] bbox_min_x, bbox_max_x,
    output reg [((BLOCK_ROWS>1)?$clog2(BLOCK_ROWS):1)-1:0] bbox_min_y, bbox_max_y,
    output reg [31:0] frame_sequence
);
    localparam integer TOTAL_PIXELS=WIDTH*HEIGHT;
    localparam TOTAL_SAMPLES=SAMPLE_COLS*SAMPLE_ROWS;
    localparam TOTAL_BLOCKS=BLOCK_COLS*BLOCK_ROWS;
    localparam X_BITS=(WIDTH>1)?$clog2(WIDTH):1;
    localparam Y_BITS=(HEIGHT>1)?$clog2(HEIGHT):1;
    localparam ADDR_BITS=(TOTAL_SAMPLES>1)?$clog2(TOTAL_SAMPLES):1;
    localparam BLOCK_BITS=(TOTAL_BLOCKS>1)?$clog2(TOTAL_BLOCKS):1;
    localparam BX_BITS=(BLOCK_COLS>1)?$clog2(BLOCK_COLS):1;
    localparam BY_BITS=(BLOCK_ROWS>1)?$clog2(BLOCK_ROWS):1;
    localparam COUNT_BITS=$clog2(BLOCK_THRESHOLD+1);
    reg active, reference_valid;
    reg [$clog2(TOTAL_PIXELS+1)-1:0] pixel_count;
    reg [X_BITS-1:0] x;
    reg [Y_BITS-1:0] y;
    reg [ADDR_BITS-1:0] sample_address;
    wire accept_pixel=active && pixel_valid && !frame_start && !frame_end &&
                      (pixel_count<TOTAL_PIXELS);
    // Invariant after every edge (including reset):
    // history_eligible == active && pixel_count<TOTAL_PIXELS &&
    //                     x%SAMPLE_STEP==0 && y%SAMPLE_STEP==0.
    // Stall holds eligibility. Start wins over end and restores (0,0).
    // Advancing the final pixel clears eligibility even when y saturates.
    reg history_eligible;
    wire [X_BITS-1:0] next_x=(x==WIDTH-1)?{X_BITS{1'b0}}:x+1'b1;
    wire [Y_BITS-1:0] next_y=(x==WIDTH-1 && y!=HEIGHT-1)?y+1'b1:y;
    wire accept_sample=history_eligible && pixel_valid && !frame_start && !frame_end;
    wire [BX_BITS-1:0] sample_bx=(x/SAMPLE_STEP)/BLOCK_SAMPLES_X;
    wire [BY_BITS-1:0] sample_by=(y/SAMPLE_STEP)/BLOCK_SAMPLES_Y;
    wire [BLOCK_BITS-1:0] sample_block=sample_by*BLOCK_COLS+sample_bx;
    wire [7:0] red={pixel_rgb565[15:11],pixel_rgb565[15:13]};
    wire [7:0] green={pixel_rgb565[10:5],pixel_rgb565[10:9]};
    wire [7:0] blue={pixel_rgb565[4:0],pixel_rgb565[4:2]};
    wire [9:0] luma_sum={2'b0,red}+{1'b0,green,1'b0}+{2'b0,blue};
    wire [7:0] luma=luma_sum[9:2];
    reg [7:0] history [0:TOTAL_SAMPLES-1];
    reg [7:0] history_q;
    always @(posedge clk) begin
        if (rst_n && accept_sample) begin
            history_q<=history[sample_address];
            history[sample_address]<=luma;
        end
    end
    reg compare_pending, compare_enabled;
    reg [7:0] current_q;
    reg [BLOCK_BITS-1:0] block_q;
    reg [BX_BITS-1:0] bx_q;
    reg [BY_BITS-1:0] by_q;
    wire [7:0] difference=(current_q>=history_q)?current_q-history_q:history_q-current_q;
    reg [COUNT_BITS-1:0] block_hits [0:TOTAL_BLOCKS-1];
    reg [TOTAL_BLOCKS-1:0] bitmap_work;
    reg [$clog2(TOTAL_BLOCKS+1)-1:0] blocks_work;
    reg [$clog2(TOTAL_SAMPLES+1)-1:0] samples_work;
    reg bbox_work_valid;
    reg [BX_BITS-1:0] min_x_work, max_x_work;
    reg [BY_BITS-1:0] min_y_work, max_y_work;
    reg update_pending, changed_q;
    reg [TOTAL_BLOCKS-1:0] select_q;
    reg [BX_BITS-1:0] update_bx;
    reg [BY_BITS-1:0] update_by;
    reg end_pending, publish_pending, publish_comparison_valid;
    reg clear_after_publish;
    wire clear_work=(frame_start && !end_pending) ||
                    (publish_pending && clear_after_publish);
    // Forward the local increment, preserving back-to-back SAMPLE_STEP=1 hits.
    reg [TOTAL_BLOCKS-1:0] mark_q;
    wire [TOTAL_BLOCKS-1:0] mark_block;
    genvar b;
    generate for (b=0;b<TOTAL_BLOCKS;b=b+1) begin : local_hit
        wire increment_now=update_pending && changed_q && select_q[b] &&
                           (block_hits[b]<BLOCK_THRESHOLD);
        wire at_next_threshold=clear_work ? (BLOCK_THRESHOLD==1) :
            ((block_hits[b]==BLOCK_THRESHOLD-1 && !increment_now) ||
             (BLOCK_THRESHOLD>1 && block_hits[b]==BLOCK_THRESHOLD-2 && increment_now));
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) mark_q[b]<=0;
            else mark_q[b]<=at_next_threshold;
        end
        assign mark_block[b]=update_pending && changed_q && select_q[b] && mark_q[b];
    end endgenerate
    wire mark_any=|mark_block;
    wire [BLOCK_ROWS-1:0] row_min_qual, row_max_qual;
    wire [BLOCK_COLS-1:0] col_min_qual, col_max_qual;
    genvar r,c;
    generate for (r=0;r<BLOCK_ROWS;r=r+1) begin : bbox_row
        localparam [BY_BITS-1:0] ROW=r;
        wire row_mark=|mark_block[r*BLOCK_COLS +: BLOCK_COLS];
        assign row_min_qual[r]=row_mark && (!bbox_work_valid || ROW<min_y_work);
        assign row_max_qual[r]=row_mark && (!bbox_work_valid || ROW>max_y_work);
    end
    for (c=0;c<BLOCK_COLS;c=c+1) begin : bbox_col
        localparam [BX_BITS-1:0] COL=c;
        wire [BLOCK_ROWS-1:0] column_marks;
        for (r=0;r<BLOCK_ROWS;r=r+1) begin : collect
            assign column_marks[r]=mark_block[r*BLOCK_COLS+c];
        end
        wire col_mark=|column_marks;
        assign col_min_qual[c]=col_mark && (!bbox_work_valid || COL<min_x_work);
        assign col_max_qual[c]=col_mark && (!bbox_work_valid || COL>max_x_work);
    end endgenerate
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            history_eligible<=0;
            active<=0; reference_valid<=0; pixel_count<=0; x<=0; y<=0;
            sample_address<=0; compare_pending<=0; compare_enabled<=0;
            current_q<=0; block_q<=0; bx_q<=0; by_q<=0;
            update_pending<=0; changed_q<=0; select_q<=0; update_bx<=0; update_by<=0;
            end_pending<=0; publish_pending<=0; clear_after_publish<=0;
            publish_comparison_valid<=0;
            bitmap_work<=0; blocks_work<=0; samples_work<=0; bbox_work_valid<=0;
            min_x_work<=0; max_x_work<=0; min_y_work<=0; max_y_work<=0;
            result_strobe<=0; result_valid<=0; block_bitmap<=0;
            changed_blocks<=0; changed_samples<=0; bbox_valid<=0;
            bbox_min_x<=0; bbox_max_x<=0; bbox_min_y<=0; bbox_max_y<=0;
            frame_sequence<=0;
            for (i=0;i<TOTAL_BLOCKS;i=i+1) block_hits[i]<=0;
        end else begin
            if (frame_start) history_eligible<=1;
            else if (frame_end && active) history_eligible<=0;
            else if (accept_pixel)
                history_eligible<=(pixel_count<TOTAL_PIXELS-1) &&
                    ((next_x%SAMPLE_STEP)==0) && ((next_y%SAMPLE_STEP)==0);
            result_strobe<=0;
            result_valid<=0;
            end_pending<=0;
            publish_pending<=end_pending;
            update_pending<=compare_pending;
            changed_q<=compare_enabled && (difference>=PIXEL_THRESHOLD);
            for (i=0;i<TOTAL_BLOCKS;i=i+1) select_q[i]<=(block_q==i);
            update_bx<=bx_q;
            update_by<=by_q;
            compare_pending<=accept_sample;
            if (accept_sample) begin
                current_q<=luma; block_q<=sample_block;
                bx_q<=sample_bx; by_q<=sample_by; compare_enabled<=reference_valid;
            end
            if (publish_pending) begin
                result_strobe<=1; result_valid<=publish_comparison_valid;
                block_bitmap<=bitmap_work; changed_blocks<=blocks_work;
                changed_samples<=samples_work; bbox_valid<=bbox_work_valid;
                bbox_min_x<=min_x_work; bbox_max_x<=max_x_work;
                bbox_min_y<=min_y_work; bbox_max_y<=max_y_work;
                frame_sequence<=frame_sequence+1'b1;
            end
            if (frame_start) begin
                if (active) reference_valid<=0;
                active<=1; pixel_count<=0; x<=0; y<=0; sample_address<=0;
                compare_pending<=0; update_pending<=0;
                clear_after_publish<=end_pending;
            end
            if (clear_work) begin
                clear_after_publish<=0;
                bitmap_work<=0; blocks_work<=0; samples_work<=0; bbox_work_valid<=0;
                min_x_work<=0; max_x_work<=0; min_y_work<=0; max_y_work<=0;
                for (i=0;i<TOTAL_BLOCKS;i=i+1) block_hits[i]<=0;
            end else begin
                if (update_pending && changed_q) begin
                    samples_work<=samples_work+1'b1;
                    for (i=0;i<TOTAL_BLOCKS;i=i+1) begin
                        if (select_q[i] && block_hits[i]<BLOCK_THRESHOLD)
                            block_hits[i]<=block_hits[i]+1'b1;
                        if (mark_block[i]) bitmap_work[i]<=1'b1;
                    end
                    if (mark_any) begin
                        blocks_work<=blocks_work+1'b1;
                        bbox_work_valid<=1;
                    end
                    // select_q is one-hot for an accepted sample. Thus a marked
                    // row/column has exactly update_by/update_bx as its coordinate.
                    if (|col_min_qual) min_x_work<=update_bx;
                    if (|col_max_qual) max_x_work<=update_bx;
                    if (|row_min_qual) min_y_work<=update_by;
                    if (|row_max_qual) max_y_work<=update_by;
                end
            end
            if (!frame_start) begin
                if (accept_pixel) begin
                    pixel_count<=pixel_count+1'b1;
                    if (x==WIDTH-1) begin
                        x<=0;
                        if (y!=HEIGHT-1) y<=y+1'b1;
                    end else x<=x+1'b1;
                    if (accept_sample && sample_address!=TOTAL_SAMPLES-1)
                        sample_address<=sample_address+1'b1;
                end
                if (frame_end && active) begin
                    active<=0;
                    if (pixel_count==TOTAL_PIXELS) begin
                        end_pending<=1;
                        publish_comparison_valid<=reference_valid;
                        reference_valid<=1;
                    end else reference_valid<=0;
                end
            end
        end
    end
endmodule
