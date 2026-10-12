// Isolated candidate. epoch_reset is CONFIGURATION epoch reset ONLY.
// It is never button_rst, axi_rst, video_rst or a software recovery request.
module four_camera_reset_supervisor #(
 parameter QUALIFY_CYCLES=4,
 parameter STARTUP_LIMIT=134217728,
 parameter CLOCK_LIMIT=4096
)(
 input clk, epoch_reset, cold_request,
 input [3:0] source_clk,
 input [3:0] i2c_start_en, cam_init_done, ov_rst_n,
 input video_reset,
 input [3:0] boundary_fault, capture_abort_req, writer_abort,
 output cold_system_reset,
 output reg authorization_used,
 output reg [3:0] source_started,
 output camera_session_fault,
 output [3:0] transport_abort,
 output admission_enable,
 output reg [3:0] clock_fault,
 output reg startup_timeout
);
 wire [3:0] raw_ready=i2c_start_en & cam_init_done & ov_rst_n;
 wire [3:0] heartbeat;
 genvar g;
 generate for(g=0;g<4;g=g+1) begin: source_watch
   reg [3:0] divider;
   always @(posedge source_clk[g] or posedge epoch_reset)
     if(epoch_reset) divider<=0; else divider<=divider+1'b1;
   assign heartbeat[g]=divider[3];
 end endgenerate
 (* async_reg="true" *) reg [3:0] hb_meta,hb_sync,ready_meta,ready_sync;
 (* async_reg="true" *) reg [1:0] request_sync;
 reg [3:0] hb_last,clock_seen;
 reg request_seen,repeat_request;
 reg released,video_started;
 reg fault_sticky;
 integer qualify_count,startup_count;
 integer age[0:3];
 integer i;
 // Pulse capture is fail-closed: a short request cannot grant authorization.
 // These async event paths require device mapping/pulse-width signoff.
 always @(posedge cold_request or posedge epoch_reset)
   if(epoch_reset) begin request_seen<=0;repeat_request<=0;end
   else begin request_seen<=1;if(request_seen) repeat_request<=1;end
 wire urgent_fault=repeat_request |
     (|(source_started & ~raw_ready)) |
     (video_started & video_reset) |
     (released & (|boundary_fault));
 always @(posedge clk or posedge epoch_reset or posedge urgent_fault)
   if(epoch_reset) fault_sticky<=0;
   else if(urgent_fault) fault_sticky<=1;
   else if(startup_timeout || (|clock_fault) ||
           (|(source_started & (capture_abort_req | writer_abort))) ||
           (request_seen && !cold_request && !authorization_used)) fault_sticky<=1;
 assign camera_session_fault=fault_sticky | urgent_fault | startup_timeout | (|clock_fault);
 // Monotonic within the epoch. Fault NEVER raises this reset again.
 assign cold_system_reset=epoch_reset | !released;
 assign transport_abort={4{camera_session_fault}};
 assign admission_enable=released && !camera_session_fault && !epoch_reset;
 always @(posedge clk or posedge epoch_reset) begin
   if(epoch_reset) begin
     hb_meta<=0;hb_sync<=0;hb_last<=0;clock_seen<=0;
     ready_meta<=0;ready_sync<=0;request_sync<=0;
     authorization_used<=0;source_started<=0;released<=0;video_started<=0;
     qualify_count<=0;startup_count<=0;clock_fault<=0;startup_timeout<=0;
     for(i=0;i<4;i=i+1) age[i]<=0;
   end else begin
     hb_meta<=heartbeat;hb_sync<=hb_meta;hb_last<=hb_sync;
     ready_meta<=raw_ready;ready_sync<=ready_meta;
     request_sync<={request_sync[0],cold_request};
     if(!video_reset) video_started<=1;
     if(!authorization_used && !camera_session_fault) begin
       if(request_seen && request_sync[1] && cold_request) begin
         if(qualify_count==QUALIFY_CYCLES-1) authorization_used<=1;
         else qualify_count<=qualify_count+1;
       end else qualify_count<=0;
     end
     for(i=0;i<4;i=i+1) begin
       if(hb_sync[i]!=hb_last[i]) begin age[i]<=0;clock_seen[i]<=1;end
       else if(age[i]<CLOCK_LIMIT) age[i]<=age[i]+1;
       else if(source_started[i]) clock_fault[i]<=1;
       if(!camera_session_fault && authorization_used && ready_sync[i] && raw_ready[i] && clock_seen[i] && age[i]<CLOCK_LIMIT)
         source_started[i]<=1;
     end
     if(!released && !camera_session_fault) begin
       if(startup_count==STARTUP_LIMIT-1) startup_timeout<=1;
       else startup_count<=startup_count+1;
       if(authorization_used && (&source_started) && (&raw_ready) && !video_reset)
         released<=1;
     end
   end
 end
endmodule
