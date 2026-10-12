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
