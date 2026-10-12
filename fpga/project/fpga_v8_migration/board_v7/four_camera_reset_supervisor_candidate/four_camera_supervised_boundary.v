// Reviewable minimal FOUR camera connection, not a replacement production top.
// Existing parent must expose the real binding's three source status signals.
module four_camera_supervised_boundary #(
 parameter STARTUP_LIMIT=134217728, CLOCK_LIMIT=4096
)(
 input video_clk, config_epoch_reset, config_cold_request,
 input [3:0] cam_clk, i2c_start_en, cam_init_done, ov_rst_n,
 input video_reset,
 input [63:0] source_data,
 input [3:0] source_valid, source_hsync, source_vsync,
 input [3:0] capture_abort_req, writer_abort,
 output [63:0] video_data,
 output [3:0] video_valid, video_hsync, video_vsync,
 output [3:0] boundary_fault, transport_abort, fir_clear,
 output camera_session_fault, admission_enable, cold_system_reset, authorization_used,
 output [3:0] source_started
);
 four_camera_reset_supervisor #(.STARTUP_LIMIT(STARTUP_LIMIT),.CLOCK_LIMIT(CLOCK_LIMIT)) supervisor(
   .clk(video_clk),.epoch_reset(config_epoch_reset),.cold_request(config_cold_request),
   .source_clk(cam_clk),.i2c_start_en(i2c_start_en),.cam_init_done(cam_init_done),.ov_rst_n(ov_rst_n),
   .video_reset(video_reset),.boundary_fault(boundary_fault),
   .capture_abort_req(capture_abort_req),.writer_abort(writer_abort),
   .cold_system_reset(cold_system_reset),.source_started(source_started),.authorization_used(authorization_used),
   .transport_abort(transport_abort),.camera_session_fault(camera_session_fault),.admission_enable(admission_enable));
 wire [3:0] cdc_valid,cdc_vsync;
 assign video_valid=cdc_valid & {4{admission_enable}};
 assign video_vsync=cdc_vsync & {4{admission_enable}};
 assign fir_clear=boundary_fault | transport_abort | {4{!admission_enable}};
 genvar i;
 generate for(i=0;i<4;i=i+1) begin: cameras
   cdc_recovery boundary(
     .system_reset(cold_system_reset),.cam_clk(cam_clk[i]),.cam_rst(!i2c_start_en[i]),
     .video_clk(video_clk),.video_rst(video_reset),
     .s_data(source_data[i*16+:16]),.s_valid(source_valid[i]),.s_hsync(source_hsync[i]),.s_vsync(source_vsync[i]),
     .video_data(video_data[i*16+:16]),.video_valid(cdc_valid[i]),.video_hsync(video_hsync[i]),.video_vsync(cdc_vsync[i]),
     .boundary_fault(boundary_fault[i]));
 end endgenerate
 // transport_abort -> all four ddr_recovery.transport_abort.
 // Each wrapper dma_abort_req -> its unchanged TC04 writer.abort_req.
 // Each writer data_in_abort -> wrapper.dma_abort AND writer_abort[i].
 // Each wrapper dma_abort_req -> capture_abort_req[i] (registered feedback).
 // admission_enable qualifies capture/host NEW requests only, never AXI replies.
 // No writer/pipe/arb/adapter reset output. No drain/retirement acknowledgement.
endmodule
