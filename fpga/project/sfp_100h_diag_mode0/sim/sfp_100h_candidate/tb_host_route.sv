`timescale 1ns/1ps
module tb_cdc_host_map;
reg clk=0; always #5 clk=~clk;
reg rst=1, valid=0, ready=1;
reg [31:0] host_addr=0;
localparam AXI_DATA_SIZE=4;
// Exact pcie_fifo ingress expression, including assignment truncation.
wire [31:0] aligned_addr = {(host_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}};
wire arready, rvalid, rlast; wire [127:0] rdata;
wire [31:0] la, ld; wire lv, lr, lrv, lrr;
axi_to_axi_lite bridge(.axi_clk(clk),.axi_rst(rst),
 .s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_arid(4'd0),.s_axi_araddr(aligned_addr),.s_axi_arlen(8'd0),
 .s_axi_arsize(3'd4),.s_axi_arburst(2'b01),.s_axi_arvalid(valid),.s_axi_arready(arready),
 .s_axi_rvalid(rvalid),.s_axi_rready(ready),.s_axi_rdata(rdata),.s_axi_rlast(rlast),
 .m_axil_araddr(la),.m_axil_arvalid(lv),.m_axil_arready(lr),
 .m_axil_rvalid(lrv),.m_axil_rready(lrr),.m_axil_rdata(ld),.m_axil_rresp(2'b00));
wire [31:0] ca[0:3], cd[0:3];
wire [3:0] cv, cr, crv, crr;
ovreg_axil_decode decode(.clk(clk),.rst(rst),
 .s_awvalid(1'b0),.s_wvalid(1'b0),.s_bready(1'b1),
 .s_araddr(la),.s_arvalid(lv),.s_arready(lr),
 .s_rdata(ld),.s_rvalid(lrv),.s_rready(lrr),
 .m0_araddr(ca[0]),.m0_arvalid(cv[0]),.m0_arready(cr[0]),.m0_rdata(cd[0]),.m0_rvalid(crv[0]),.m0_rready(crr[0]),.m0_rresp(2'b00),
 .m1_araddr(ca[1]),.m1_arvalid(cv[1]),.m1_arready(cr[1]),.m1_rdata(cd[1]),.m1_rvalid(crv[1]),.m1_rready(crr[1]),.m1_rresp(2'b00),
 .m2_araddr(ca[2]),.m2_arvalid(cv[2]),.m2_arready(cr[2]),.m2_rdata(cd[2]),.m2_rvalid(crv[2]),.m2_rready(crr[2]),.m2_rresp(2'b00),
 .m3_araddr(ca[3]),.m3_arvalid(cv[3]),.m3_arready(cr[3]),.m3_rdata(cd[3]),.m3_rvalid(crv[3]),.m3_rready(crr[3]),.m3_rresp(2'b00));
ov5640_reg #(.BASE_ADDR(32'h20000000)) cam0(
 .clk(clk),.rst(rst),.s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_araddr(ca[0]),.s_axi_arvalid(cv[0]),.s_axi_arready(cr[0]),
 .s_axi_rdata(cd[0]),.s_axi_rvalid(crv[0]),.s_axi_rready(crr[0]),
 .dbg_cdc_input(32'd307200),.dbg_cdc_output(32'd1290240),
 .dbg_cdc_drop(32'd7),.dbg_cdc_seq(32'd123),
 .dbg_fault_snapshot(32'h80006123),.dbg_pclk_cnt(32'h12345678));
ov5640_reg #(.BASE_ADDR(32'h20000200)) cam1(
 .clk(clk),.rst(rst),.s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_araddr(ca[2]),.s_axi_arvalid(cv[2]),.s_axi_arready(cr[2]),
 .s_axi_rdata(cd[2]),.s_axi_rvalid(crv[2]),.s_axi_rready(crr[2]),
 .dbg_cdc_input(32'd307201),.dbg_cdc_output(32'd1290241),
 .dbg_cdc_drop(32'd8),.dbg_cdc_seq(32'd124),
 .dbg_fault_snapshot(32'h80006123),.dbg_pclk_cnt(32'h12345678));
ov5640_reg #(.BASE_ADDR(32'h20000400)) cam2(
 .clk(clk),.rst(rst),.s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_araddr(ca[3]),.s_axi_arvalid(cv[3]),.s_axi_arready(cr[3]),
 .s_axi_rdata(cd[3]),.s_axi_rvalid(crv[3]),.s_axi_rready(crr[3]),
 .dbg_cdc_input(32'd307202),.dbg_cdc_output(32'd1290242),
 .dbg_cdc_drop(32'd9),.dbg_cdc_seq(32'd125),
 .dbg_fault_snapshot(32'h80006123),.dbg_pclk_cnt(32'h12345678));
// PREP sentinel confirms all its implemented offsets retain routing.
assign cr[1]=cv[1];
reg prep_valid=0;
always @(posedge clk) begin
 if(rst) prep_valid<=0;
 else if(cv[1] && cr[1]) prep_valid<=1;
 else if(crr[1]) prep_valid<=0;
end
assign crv[1]=prep_valid;
assign cd[1]=32'hfacefeed;
task check(input [31:0] addr, input [31:0] expected);
begin
 @(negedge clk);host_addr=addr;valid=1;ready=0;
 do @(posedge clk); while(!arready);
 @(negedge clk);valid=0;host_addr=32'h20000100;
 wait(rvalid); #1;
 repeat(3) begin
  if(rdata !== {96'd0,expected} || !rlast || !rvalid)
   $fatal(1,"host address %h returned %h expected %h",addr,rdata,expected);
  @(negedge clk);
 end
 ready=1;repeat(3)@(negedge clk);
end endtask
integer cam;
initial begin
 repeat(4)@(negedge clk);rst=0;
 for(cam=0;cam<3;cam=cam+1) begin
  check(32'h20000190+cam*'h200,307200+cam);
  check(32'h200001a0+cam*'h200,1290240+cam);
  check(32'h200001b0+cam*'h200,7+cam);
  check(32'h200001c0+cam*'h200,123+cam);
  // Reproduce the old broken accesses: 04/08/0c alias ACK, 14 aliases PCLK.
  check(32'h20000004+cam*'h200,32'h80006123);
  check(32'h20000008+cam*'h200,32'h80006123);
  check(32'h2000000c+cam*'h200,32'h80006123);
  check(32'h20000014+cam*'h200,32'h12345678);
 end
 check(32'h20000100,32'hfacefeed);
 check(32'h20000110,32'hfacefeed);
 check(32'h20000120,32'hfacefeed);
 check(32'h20000130,32'hfacefeed);
 check(32'h20000140,32'hfacefeed);
 check(32'h20000150,32'hfacefeed);
 check(32'h20000160,32'hfacefeed);
 check(32'h20000170,32'hfacefeed);
 check(32'h20000180,32'hfacefeed);
 check(32'h20000300,32'hfacefeed);
 check(32'h20000310,32'hfacefeed);
 check(32'h20000320,32'hfacefeed);
 check(32'h20000330,32'hfacefeed);
 check(32'h20000340,32'hfacefeed);
 check(32'h20000350,32'hfacefeed);
 check(32'h20000360,32'hfacefeed);
 check(32'h20000370,32'hfacefeed);
 check(32'h20000380,32'hfacefeed);
// Existing CAM3 SCCB reads remain accessible and reset to zero.
 check(32'h20000510,0);check(32'h20000520,0);
 $display("PASS HOST MAP three cameras, old alignment aliases, PREP/SCCB routing, R backpressure and zero extension");
 $finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
