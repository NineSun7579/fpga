    // Source contract: valid pixels have VSYNC low; falling edge may carry data.
    reg vs_seen, transport_fault;
    wire edge_token = s_vsync != vs_seen;
    wire event_token = s_valid || edge_token;
    wire meta_full,meta_empty;
    wire [2:0] token;
    wire pixel_full;
    wire violation = s_valid && s_vsync;
    wire full = pixel_full || meta_full || transport_fault || violation;
    wire put = event_token && !full;
    wire wr_en = put && s_valid;
    always @(posedge cam_clk or posedge cam_rst) begin
      if(cam_rst) begin vs_seen<=0;transport_fault<=0;end
      else begin
        vs_seen<=s_vsync;
        if(event_token && full) transport_fault<=1;
      end
    end
    (* async_reg="true" *) reg [1:0] fault_sync;
    reg [1:0] hsync_sync;
    reg video_valid_r,vs_level,marker_done;
    reg [2:0] guard_cycles;
    wire empty;
    wire [DATA_WIDTH-1:0] dout;
    wire can_take = !meta_empty && !fault_sync[1] && guard_cycles==0;
    wire rd_en = can_take && token[1] && (!token[2] || marker_done) && !empty;
    // Do not raise VSYNC while a prior synchronous FIFO read is retiring.
    wire take_marker = can_take && token[2] && !marker_done && !video_valid_r;
    cdc_order_meta metadata(.wc(cam_clk),.wr(cam_rst),.put(put),
      .din({edge_token,s_valid,s_vsync}),.full(meta_full),.rc(video_clk),.rr(video_rst),
      .pop(rd_en||(take_marker&&!token[1])),.head(token),.empty(meta_empty));
    ov5640_cdc_fifo ov5640_cdc_fifo (
      .wr_clk(cam_clk),.wr_rst(cam_rst),.wr_en(wr_en),.wr_data(s_data),
      .wr_full(pixel_full),.rd_clk(video_clk),.rd_rst(video_rst),
      .rd_en(rd_en),.rd_data(dout),.rd_empty(empty),.almost_full(),.almost_empty());
    always @(posedge video_clk or posedge video_rst) begin
      if(video_rst) begin
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
    assign video_data=dout;
    assign video_valid=video_valid_r;
    assign video_vsync=vs_level;
    assign video_hsync=hsync_sync[1];
