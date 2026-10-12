`timescale 1ns/1ps
module tb_review #(parameter realtime CAM_HALF=6, VID_HALF=8);
reg cam=0,vid=0,ven=1,cr=1,vr=1,sv=0,vs=0;
reg [15:0] data=0;
always #(CAM_HALF) cam=~cam;
always #(VID_HALF) if(ven) vid=~vid;
GTP_GRS GRS_INST(.GRS_N(1'b1));
wire [15:0] q; wire qv,qs,fault;
cdc_order_candidate #(.DATA_WIDTH(16)) dut(
 .cam_clk(cam),.cam_rst(cr),.video_clk(vid),.video_rst(vr),
 .s_data(data),.s_valid(sv),.s_vsync(vs),.s_hsync(1'b0),
 .video_data(q),.video_valid(qv),.video_vsync(qs),.video_hsync(),
 .boundary_fault(fault),.dbg_cdc_input(),.dbg_cdc_output(),.dbg_cdc_drop(),.dbg_cdc_seq());
integer errors=0,ni=0,no=0,simultaneous=0;
reg checking=1;
reg [15:0] expected[0:20000];
task check(input bit ok,input string msg);
 if(!ok) begin errors++;$display("FAIL %s",msg);end
endtask
always @(posedge cam) if(!cr && sv && dut.wr_en) begin
 expected[ni]=data;ni++;
 if(dut.rd_en) simultaneous++;
end
always @(posedge vid) if(!vr && qv) begin
 if(checking) check(no<ni && q===expected[no],"pixel order/conservation");
 no++;
end
task tick(input bit valid,input bit level,input [15:0] value);
 @(negedge cam);sv=valid;vs=level;data=value;
endtask
task reset_all;
 @(negedge cam);cr=1;vr=1;sv=0;vs=0;ven=1;
 repeat(30) @(negedge vid);
 ni=0;no=0;simultaneous=0;
 @(negedge cam);cr=0;vr=0;
endtask
integer i,before_reset;
initial begin
 reset_all();
 @(negedge vid);ven=0;
 for(i=0;i<1000;i++) tick(1,0,i);
 tick(0,0,0);ven=1;
 for(i=1000;i<11000;i++) begin tick(1,0,i);tick(0,0,0);end
 repeat(2000) @(negedge vid);
 check(ni==11000 && no==11000 && !fault,"near-full concurrent/wrap result");
 $display("REVIEW near_full_wrap accepted=%0d output=%0d concurrent_windows=%0d fault=%b",ni,no,simultaneous,fault);
 reset_all();
 for(i=0;i<64;i++) begin tick(1,0,16'h4000+i);tick(0,0,0);end
 repeat(200) @(negedge vid);
 check(no==64 && !fault,"pre unilateral-reset setup");
 checking=0;before_reset=no;
 @(negedge vid);vr=1;
 repeat(30) @(negedge vid);
 vr=0;
 repeat(200) @(negedge vid);
 check(no>before_reset && !fault,"expected unsupported video-only reset replay not reproduced");
 $display("REVIEW video_only_reset source=%0d before=%0d after=%0d fault=%b",ni,before_reset,no,fault);
 reset_all();checking=1;
 @(negedge vid);ven=0;
 for(i=0;i<1024;i++) tick(1,0,i);
 tick(0,0,0);
 check(dut.pixel_full && !dut.meta_full && !dut.transport_fault,"pixel-full setup");
 tick(0,1,0);tick(0,1,0);
 check(dut.transport_fault,"expected conservative marker rejection not reproduced");
 $display("REVIEW marker_at_pixel_full accepted=%0d meta_full=%b source_fault=%b",ni,dut.meta_full,dut.transport_fault);
 ven=1;
 $display("REVIEW_DONE errors=%0d",errors);
 if(errors) $fatal(1,"review expectations failed");
 $finish;
end
initial begin #1000000;$fatal(1,"timeout");end
endmodule
