`timescale 1ns/1ps
module tb_cam34_geometry;
reg clk=0,rst=1,arvalid=0;reg[31:0]araddr=0;wire arready,rvalid;wire[31:0]rdata;
always #5 clk=~clk;
ov5640_reg #(.BASE_ADDR(32'h20000400),.FRAME_W(320),.FRAME_H(240),.FRAME_BYTES(153600)) regs(.clk(clk),.rst(rst),.s_axi_awvalid('0),.s_axi_awready(),.s_axi_awaddr('0),.s_axi_wvalid('0),.s_axi_wready(),.s_axi_wdata('0),.s_axi_wstrb('0),.s_axi_bvalid(),.s_axi_bready('0),.s_axi_bresp(),.s_axi_arvalid(arvalid),.s_axi_arready(arready),.s_axi_araddr(araddr),.s_axi_rvalid(rvalid),.s_axi_rready(1'b1),.s_axi_rdata(rdata),.s_axi_rresp(),.cam_addr_1(),.cam_addr_2(),.xdma_ack(),.cam_en(),.dly_step(),.dbg_cdc_input('0),.dbg_cdc_output('0),.dbg_cdc_drop('0),.dbg_cdc_seq('0),.dbg_fault_snapshot('0),.dbg_reject_counts('0),.dbg_input_pixels('0),.dbg_vsync_widths('0),.dbg_cam_words('0),.dbg_vsyncs('0),.dbg_hsyncs('0),.dbg_href_raw('0),.dbg_vsync_raw('0),.dbg_beat_cnt('0),.dbg_beat_last('0),.dbg_cmd_cnt('0),.dbg_axi_sticky('0),.dbg_axi_stat('0),.dbg_b_cnt('0),.dbg_aw_cnt('0),.dbg_w_cnt('0),.dbg_axi_cnt('0),.dbg_zdin('0),.dbg_zout('0),.dbg_axi_num('0),.dbg_state('0),.dbg_last_cnt('0),.dbg_wd_cnt('0),.dbg_xdma_req('0),.dbg_i2c_status('0),.dbg_pclk_cnt('0),.dbg_sys_status('0),.dbg_clk_status('0),.pt_req_toggle(),.pt_addr(),.pt_wdata(),.pt_rw(),.pt_rdata('0),.pt_ack('0),.pt_done_toggle('0));
task read(input[31:0]addr,input[31:0]expected);
 begin @(negedge clk);araddr=addr;arvalid=1;while(!arready)@(negedge clk);@(negedge clk);arvalid=0;
 while(!rvalid)@(negedge clk);if(rdata!==expected)$fatal(1,"geometry register %h expected=%h got=%h",addr,expected,rdata);
 $display("[PASS] register=%h value=%h",addr,rdata);@(negedge clk);
 end
endtask
initial begin repeat(5)@(negedge clk);rst=0;
 read(32'h20000540,32'h43333432);read(32'h20000550,32'h00f00140);
 read(32'h20000560,32'd153600);read(32'h20000570,32'd640);
 $display("CAM34_GEOMETRY_PASS");$finish;end
initial begin #10000;$fatal(1,"timeout");end
endmodule
