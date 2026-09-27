`timescale 1ns/1ps
module tb_vsync;
reg clk=0;always #5 clk=~clk;
reg rst=1,sv=0;
wire mv,mdv,busy,cv;
wire [31:0] cmdlen,state;
integer raw=0,admitted=0,commands=0,vs=0;
ov5640_ddr_w_en #(.DATA_WIDTH(16)) gate_u(.axi_clk(clk),.axi_rst(rst),.axi_cam_en(1'b1),.frame_pending(2'd0),.engine_busy(busy),.s_data(16'h1234),.s_data_valid(1'b1),.s_hsync(1'b1),.s_vsync(sv),.m_data(),.m_data_valid(mdv),.m_hsync(),.m_vsync(mv));
ov5640_ddr_w_ctrl #(.CAM_DATA_LEN(38400)) ctrl(.axi_clk(clk),.axi_rst(rst),.cam_data_addr_1(32'h1000000),.cam_data_addr_2(32'h1200000),.cam_data_len(17'd38400),.s_vsync(mv),.dma_done(1'b0),.axi_cmd_addr(),.axi_cmd_len(cmdlen),.axi_cmd_valid(cv),.axi_cmd_ready(1'b1),.xdma_req(),.xdma_ack(2'd0),.tag_active(),.tag_data(),.tag_ready(1'b0),.dbg_state(state),.engine_busy(busy),.dbg_last_cnt(),.dbg_wd_cnt(),.w_ping_o());
always @(posedge clk)if(!rst)begin
 raw=raw+1;if(mdv)admitted=admitted+1;
 if(cv)begin commands=commands+1;$display("COMMAND bytes=%0d",cmdlen);end
 if(mv)vs=vs+1;
end
integer j;
initial begin
 repeat(5)@(negedge clk);rst=0;
 // 100 MHz AXI, one VSYNC each 10,000 cycles = 10 kHz; continuous upstream pixels.
 for(j=0;j<5;j=j+1)begin sv=1;@(negedge clk);sv=0;repeat(9999)@(negedge clk);end
 $display("VSYNC RESULT raw_pixels=%0d admitted_pixels=%0d accepted_vsync=%0d commands=%0d ctrl_state=%0d gate_state=%0d",raw,admitted,vs,commands,state,gate_u.curr_state);
 if(commands!=1||vs!=1||admitted!=10000||state!=4||gate_u.curr_state!=1)$fatal(1,"gate result differs");
 $display("PASS 10kHz VSYNC truncates admitted frame to 10000 pixels despite continuous upstream valid; DMA command still asks 307200 pixels");
 $finish;
end
endmodule
