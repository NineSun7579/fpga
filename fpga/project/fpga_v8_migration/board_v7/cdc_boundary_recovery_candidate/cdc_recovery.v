// Isolated TC04 camera candidate. Pixel FIFO and video-domain behavior are TC03.
module cdc_recovery #(
    parameter DATA_WIDTH = 16,
    parameter DEVICE = "PG"
) (
    output reg [31:0] dbg_cdc_input, dbg_cdc_output, dbg_cdc_drop, dbg_cdc_seq,
    output boundary_fault,
    input system_reset,
    input cam_clk, cam_rst,
    input [DATA_WIDTH-1:0] s_data,
    input s_valid, s_hsync, s_vsync,
    input video_clk, video_rst,
    output [DATA_WIDTH-1:0] video_data,
    output video_valid, video_hsync, video_vsync
);
    // Source contract: valid pixels have VSYNC low; falling edge may carry data.
    reg vs_seen, transport_fault;
    wire edge_token = s_vsync != vs_seen;
    wire event_token = s_valid || edge_token;
    wire meta_full,meta_empty;
    wire [2:0] token;
    wire pixel_full;
    wire violation = s_valid && s_vsync;
    wire full = (s_valid && pixel_full) || meta_full || transport_fault || violation;
    // NEW input system_reset means reset of the entire DMA/DDR session.
    // cam_rst | video_rst is NOT sufficient authorization to restart DMA.
    wire request_reset = cam_rst | video_rst;
    reg reset_fault;
    always @(posedge video_clk or posedge request_reset or posedge system_reset)
      if(system_reset) reset_fault <= 0;
      else if(request_reset) reset_fault <= 1;
    wire isolate = system_reset | request_reset | reset_fault | transport_fault;
    (* async_reg="true" *) reg [2:0] cam_release, video_release;
    always @(posedge cam_clk or posedge isolate)
      if(isolate) cam_release<=0; else cam_release<={cam_release[1:0],1'b1};
    always @(posedge video_clk or posedge isolate)
      if(isolate) video_release<=0; else video_release<={video_release[1:0],1'b1};
    wire cam_clear = !cam_release[2];
    wire video_clear = !video_release[2];
    (* async_reg="true" *) reg [1:0] video_ready_cam, cam_ready_video;
    always @(posedge cam_clk or posedge isolate)
      if(isolate) video_ready_cam<=0; else video_ready_cam<={video_ready_cam[0],video_release[2]};
    always @(posedge video_clk or posedge isolate)
      if(isolate) cam_ready_video<=0; else cam_ready_video<={cam_ready_video[0],cam_release[2]};
    reg armed, saw_low;
    always @(posedge cam_clk or posedge cam_clear)
      if(cam_clear) begin armed<=0; saw_low<=0; end
      else if(video_ready_cam[1]) begin
        if(!s_vsync) saw_low<=1;
        if(saw_low && edge_token && s_vsync) armed<=1;
      end
    wire source_ready = video_ready_cam[1] && !cam_clear && !isolate;
    wire accept_epoch = armed || (saw_low && edge_token && s_vsync);

    wire put = event_token && !full && source_ready && accept_epoch;
    wire wr_en = put && s_valid;
    always @(posedge cam_clk or posedge system_reset) begin
      if(system_reset) transport_fault<=0;
      else if(source_ready && accept_epoch && event_token && full) transport_fault<=1;
    end
    always @(posedge cam_clk or posedge cam_clear) begin
      if(cam_clear) begin vs_seen<=0;end
      else begin
        vs_seen<=s_vsync;

      end
    end
    (* async_reg="true" *) reg [1:0] fault_sync;
    reg [1:0] hsync_sync;
    reg video_valid_r,vs_level,marker_done;
    reg [2:0] guard_cycles;
    wire empty;
    wire [DATA_WIDTH-1:0] dout;
    wire can_take = !meta_empty && !fault_sync[1] && !isolate && !video_clear && cam_ready_video[1] && guard_cycles==0;
    wire rd_en = can_take && token[1] && (!token[2] || marker_done) && !empty;
    // Do not raise VSYNC while a prior synchronous FIFO read is retiring.
    wire take_marker = can_take && token[2] && !marker_done && !video_valid_r;
    cdc_order_meta metadata(.wc(cam_clk),.wr(cam_clear),.put(put),
      .din({edge_token,s_valid,s_vsync}),.full(meta_full),.rc(video_clk),.rr(video_clear),
      .pop(rd_en||(take_marker&&!token[1])),.head(token),.empty(meta_empty));
    ov5640_cdc_fifo ov5640_cdc_fifo (
      .wr_clk(cam_clk),.wr_rst(cam_clear),.wr_en(wr_en),.wr_data(s_data),
      .wr_full(pixel_full),.rd_clk(video_clk),.rd_rst(video_clear),
      .rd_en(rd_en),.rd_data(dout),.rd_empty(empty),.almost_full(),.almost_empty());
    always @(posedge video_clk or posedge video_clear) begin
      if(video_clear) begin
        fault_sync<=0;hsync_sync<=0;video_valid_r<=0;vs_level<=0;guard_cycles<=0;marker_done<=0;
      end else begin
        fault_sync<={fault_sync[0],transport_fault};
        hsync_sync<={hsync_sync[0],s_hsync};
        video_valid_r<=rd_en;
        if(rd_en) marker_done<=0;
        if(guard_cycles!=0) guard_cycles<=guard_cycles-1'b1;
        if(take_marker) begin
          vs_level<=token[0];
          marker_done<=token[1];
          if(token[0]) guard_cycles<=3;
        end
      end
    end
    assign boundary_fault=reset_fault | transport_fault | request_reset;
    assign video_data=dout;
    assign video_valid=video_valid_r && !isolate && !video_clear;
    assign video_vsync=vs_level && !isolate && !video_clear;
    assign video_hsync=hsync_sync[1];
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
            dbg_cdc_output <= out_snapshot;
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

            end
        end
    end
endmodule
