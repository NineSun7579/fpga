// Isolated TC04 camera candidate. Pixel FIFO and video-domain behavior are TC03.
module ov5640_cdc_tc04 #(
    parameter DATA_WIDTH = 24,
    parameter DEVICE = "PG"
) (
    output reg [31:0] dbg_cdc_input, dbg_cdc_output, dbg_cdc_drop, dbg_cdc_seq,
    input cam_clk, cam_rst,
    input [DATA_WIDTH-1:0] s_data,
    input s_valid, s_hsync, s_vsync,
    input video_clk, video_rst,
    output [DATA_WIDTH-1:0] video_data,
    output video_valid, video_hsync, video_vsync
);
    reg [1:0] vsync_sync, hsync_sync;
    always @(posedge video_clk) begin
        if (video_rst) begin
            vsync_sync <= 0;
            hsync_sync <= 0;
        end else begin
            vsync_sync <= {vsync_sync[0], s_vsync};
            hsync_sync <= {hsync_sync[0], s_hsync};
        end
    end
    assign video_hsync = hsync_sync[1];
    assign video_vsync = vsync_sync[1];
    wire empty, full, wr_en, rd_en;
    wire [DATA_WIDTH-1:0] dout;
    assign wr_en = !full & s_valid;
    assign rd_en = !empty;
    assign video_data = dout;
    reg video_valid_r;
    always @(posedge video_clk) begin
        if (video_rst) video_valid_r <= 0;
        else video_valid_r <= rd_en;
    end
    assign video_valid = video_valid_r;
    ov5640_cdc_fifo ov5640_cdc_fifo (
        .wr_clk(cam_clk), .wr_rst(cam_rst), .wr_en(wr_en), .wr_data(s_data),
        .wr_full(full), .rd_clk(video_clk), .rd_en(rd_en), .rd_data(dout),
        .rd_empty(empty), .rd_rst(video_rst), .almost_full(), .almost_empty()
    );
    reg src_vs_q, src_toggle;
    reg [31:0] src_count, src_drop, src_seq;
    reg [95:0] src_snapshot;
    wire src_frame_start = s_vsync && !src_vs_q;
    wire drop_increment = s_valid && full;
    // Invariant after every edge: prefix[n] == &counter[n*4-1:0].
    // Predict the next all-ones prefix directly from OLD state:
    // increment -> old prefix == ...1110; hold -> old prefix == ...1111.
    // Thus the late valid/full event never traverses a wide carry reduction
    // on the way to a high counter slice. No delayed counter or saturation.
    reg [7:1] count_prefix, drop_prefix;
    genvar stat_slice;
    generate for (stat_slice=0; stat_slice<8; stat_slice=stat_slice+1) begin : gen_src_stats
        wire count_carry, drop_carry;
        if (stat_slice==0) begin : gen_low
            assign count_carry = s_valid;
            assign drop_carry = drop_increment;
        end else begin : gen_high
            assign count_carry = s_valid && count_prefix[stat_slice];
            assign drop_carry = drop_increment && drop_prefix[stat_slice];
            always @(posedge cam_clk or posedge cam_rst) begin
                if (cam_rst) begin
                    count_prefix[stat_slice] <= 0;
                    drop_prefix[stat_slice] <= 0;
                end else if (src_frame_start) begin
                    // New count is only 0 or 1, so every >=4-bit prefix is false.
                    count_prefix[stat_slice] <= 0;
                    drop_prefix[stat_slice] <= 0;
                end else begin
                    count_prefix[stat_slice] <= (&src_count[stat_slice*4-1:1]) && (src_count[0] ^ s_valid);
                    drop_prefix[stat_slice] <= (&src_drop[stat_slice*4-1:1]) && (src_drop[0] ^ drop_increment);
                end
            end
        end
        always @(posedge cam_clk or posedge cam_rst) begin
            if (cam_rst) begin
                src_count[stat_slice*4 +: 4] <= 0;
                src_drop[stat_slice*4 +: 4] <= 0;
            end else if (src_frame_start) begin
                if (stat_slice==0) begin
                    src_count[stat_slice*4 +: 4] <= {3'd0,s_valid};
                    src_drop[stat_slice*4 +: 4] <= {3'd0,drop_increment};
                end else begin
                    src_count[stat_slice*4 +: 4] <= 0;
                    src_drop[stat_slice*4 +: 4] <= 0;
                end
            end else begin
                if (count_carry) src_count[stat_slice*4 +: 4] <= src_count[stat_slice*4 +: 4]+4'd1;
                if (drop_carry) src_drop[stat_slice*4 +: 4] <= src_drop[stat_slice*4 +: 4]+4'd1;
            end
        end
    end endgenerate
    always @(posedge cam_clk or posedge cam_rst) begin
        if (cam_rst) begin
            src_vs_q <= 0;
            src_toggle <= 0;
            src_seq <= 0;
            src_snapshot <= 0;
        end else begin
            src_vs_q <= s_vsync;
            if (src_frame_start) begin
                src_snapshot <= {src_seq+32'd1,src_drop,src_count};
                src_toggle <= ~src_toggle;
                src_seq <= src_seq+1'b1;
            end
        end
    end
    reg [95:0] snapshot_s1, snapshot_s2;
    reg [2:0] toggle_sync;
    reg toggle_seen, out_vs_q;
    reg [31:0] out_count, out_snapshot;
    always @(posedge video_clk) begin
        if (video_rst) begin
            snapshot_s1 <= 0;
            snapshot_s2 <= 0;
            toggle_sync <= 0;
            toggle_seen <= 0;
            out_vs_q <= 0;
            out_count <= 0;
            out_snapshot <= 0;
            dbg_cdc_input <= 0;
            dbg_cdc_output <= 0;
            dbg_cdc_drop <= 0;
            dbg_cdc_seq <= 0;
        end else begin
            snapshot_s1 <= src_snapshot;
            snapshot_s2 <= snapshot_s1;
            toggle_sync <= {toggle_sync[1:0],src_toggle};
            out_vs_q <= video_vsync;
            if (video_vsync && !out_vs_q) begin
                out_snapshot <= out_count;
                out_count <= {31'd0,video_valid};
            end else if (video_valid) out_count <= out_count+1'b1;
            if (toggle_sync[2] != toggle_seen) begin
                toggle_seen <= toggle_sync[2];
                dbg_cdc_input <= snapshot_s2[31:0];
                dbg_cdc_drop <= snapshot_s2[63:32];
                dbg_cdc_seq <= snapshot_s2[95:64];
                dbg_cdc_output <= out_snapshot;
            end
        end
    end
endmodule
