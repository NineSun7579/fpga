`timescale 1ns/1ps
module six_batch_tb;
reg clk=0, rst=1;
always #5 clk=~clk;
integer cycle=0;
always @(posedge clk) cycle<=cycle+1;
reg [31:0] base=0, bytes=0;
reg start=0, capacity=0;
wire [31:0] araddr;
wire [3:0] arlen, arid;
wire [2:0] arsize;
wire [1:0] arburst;
wire arvalid, arready, rready;
wire [127:0] rdata;
wire rvalid, rlast;
wire [1:0] rresp;
wire [3:0] rid;
wire mmio = base>=32'h40020000 && base<=32'h40020120;
wire ar_gate=cycle%3!=0, r_gate=cycle%4!=0;
wire a_arready,a_rvalid,a_rlast;
wire [127:0] a_rdata;
wire [1:0] a_rresp;
wire [6:0] a_rid;
reg d_valid=0;
reg [4:0] d_left=0;
integer d_index=0;
assign arready=ar_gate && (mmio ? a_arready : !d_valid);
assign rvalid=r_gate && (mmio ? a_rvalid : d_valid);
assign rlast=mmio ? a_rlast : d_left==1;
assign rdata=mmio ? a_rdata : {96'd0,32'hc0000000+d_index};
assign rresp=mmio ? a_rresp : 2'd0;
assign rid=mmio ? a_rid[3:0] : 4'd0;
pcie_fifo dut(.button_rst_n(!rst),.axi_clk(clk),.axi_rst(rst),
 .axi_araddr(araddr),.axi_arlen(arlen),.axi_arid(arid),.axi_arsize(arsize),
 .axi_arburst(arburst),.axi_arvalid(arvalid),.axi_arready(arready),
 .axi_rdata(rdata),.axi_rvalid(rvalid),.axi_rlast(rlast),.axi_rresp(rresp),
 .axi_rid(rid),.axi_rready(rready),.axi_awready(1'b0),.axi_wready(1'b0),
 .axi_bid(4'd0),.axi_bresp(2'd0),.axi_bvalid(1'b0));
delivery_top_adapter adapter(.clk(clk),.rst(rst),
 .camera_prev_base(192'd0),
 .camera_bank0({32'h01c00000,32'h01800000,32'h01400000,32'h01000000,32'h00c00000,32'h00800000}),
 .camera_bank1({32'h01e00000,32'h01a00000,32'h01600000,32'h01200000,32'h00e00000,32'h00a00000}),
 .camera_sequence(192'd0),.camera_published(12'd0),
 .camera_writer_idle(6'h3f),.camera_dma_idle(6'h3f),.camera_pending(6'd0),
 .camera_flush(6'd0),.camera_cmd_valid(6'd0),.camera_awvalid(6'd0),
 .camera_wvalid(6'd0),.camera_abort(6'd0),
 .s_axi_arid({3'd0,arid}),.s_axi_araddr(araddr),.s_axi_arlen({4'd0,arlen}),
 .s_axi_arsize(arsize),.s_axi_arburst(arburst),.s_axi_arlock(1'b0),
 .s_axi_arcache(4'd2),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arregion(4'd0),
 .s_axi_arvalid(arvalid && mmio && ar_gate),.s_axi_arready(a_arready),
 .s_axi_rid(a_rid),.s_axi_rdata(a_rdata),.s_axi_rresp(a_rresp),
 .s_axi_rlast(a_rlast),.s_axi_rvalid(a_rvalid),.s_axi_rready(rready && mmio && r_gate),
 .s_axi_awid(7'd0),.s_axi_awaddr(32'd0),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),
 .s_axi_awburst(2'd1),.s_axi_awlock(1'b0),.s_axi_awcache(4'd0),
 .s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awregion(4'd0),.s_axi_awvalid(1'b0),
 .s_axi_wdata(128'd0),.s_axi_wstrb(16'd0),.s_axi_wlast(1'b1),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .m_axi_arready(1'b0),.m_axi_rdata(128'd0),.m_axi_rresp(2'd0),
 .m_axi_rlast(1'b0),.m_axi_rvalid(1'b0),.m_axi_awready(1'b0),
 .m_axi_wready(1'b0),.m_axi_bresp(2'd0),.m_axi_bvalid(1'b0));
integer addresses=0, received=0, enqueued=0, beats_expected=0;
integer next_address=0, ar_stalls=0, r_stalls=0, capacity_stalls=0;
reg [31:0] stalled_addr;
reg [3:0] stalled_len;
reg was_stalled=0;
function [31:0] expected_reg(input integer index);
begin
 case(index)
 0:expected_reg=32'h444c5632;
 4:expected_reg=32'h0a000000;
 6:expected_reg=1228800;
 8:expected_reg=614400;
 10:expected_reg=15;
 12:expected_reg=4;
 15:expected_reg=63;
 16:expected_reg=32'h01800000;
 17:expected_reg=32'h01a00000;
 default:expected_reg=0;
 endcase
end
endfunction
always @(posedge clk) begin
 if(rst) begin d_valid<=0; d_left<=0; d_index<=0; was_stalled<=0; end
 else begin
  if(was_stalled && (araddr!==stalled_addr || arlen!==stalled_len || !arvalid))
   $fatal(1,"AR changed under backpressure");
  was_stalled<=arvalid && !arready;
  stalled_addr<=araddr; stalled_len<=arlen;
  if(arvalid && !arready) ar_stalls=ar_stalls+1;
  if((mmio?a_rvalid:d_valid) && !r_gate) r_stalls=r_stalls+1;
  if(capacity && dut.read_started) capacity_stalls=capacity_stalls+1;
  if(arvalid && arready) begin
   if(araddr!==next_address || arsize!=4 || arburst!=1) $fatal(1,"AR address/size/burst mismatch");
   if(mmio && arlen!=0) $fatal(1,"register burst not single beat");
   if(!mmio && arlen != ((beats_expected-received>=16)?15:beats_expected-received-1))
    $fatal(1,"DDR burst length changed");
   next_address=next_address+16*(arlen+1);
   addresses=addresses+1;
   if(!mmio) begin d_valid<=1; d_left<=arlen+1; end
  end
  if(rvalid && rready) begin
   if(rresp!=0 || rid!=0) $fatal(1,"read response error/id");
   if(mmio && (rdata!=={96'd0,expected_reg((base-32'h40020000)/16+received)} || !rlast))
    $fatal(1,"snapshot register %0d actual=%h expected=%h",received,rdata,expected_reg(received));
   if(!mmio && rdata!=={96'd0,32'hc0000000+received}) $fatal(1,"DDR payload order");
   received=received+1;
   if(!mmio) begin d_index<=d_index+1; d_left<=d_left-1; if(d_left==1) d_valid<=0; end
  end
  if(dut.fifo_tx_wr_en) begin
   if(mmio && dut.fifo_tx_wr_data!=={96'd0,expected_reg((base-32'h40020000)/16+enqueued)}) $fatal(1,"FIFO snapshot order");
   if(!mmio && dut.fifo_tx_wr_data!=={96'd0,32'hc0000000+enqueued}) $fatal(1,"FIFO DDR order");
   enqueued=enqueued+1;
  end
 end
end
always @(negedge clk) capacity=(cycle%37>=30);
task run_read(input [31:0] address, input integer count);
integer watchdog;
begin
 rst=1; start=0; base=address; bytes=count;
 repeat(5) @(negedge clk);
 addresses=0; received=0; enqueued=0; next_address=address;
 beats_expected=(count+15)/16;
 rst=0;
 repeat(5) @(negedge clk);
 start=1;
 watchdog=0;
 while(enqueued<beats_expected && watchdog<2000000) begin @(negedge clk); watchdog=watchdog+1; end
 repeat(10) @(negedge clk);
 if(enqueued!=beats_expected || received!=beats_expected || dut.read_beats_remain!=0 || dut.r_state!=0)
  $fatal(1,"payload count/retirement count=%0d received=%0d enqueued=%0d remaining=%0d state=%0d",count,received,enqueued,dut.read_beats_remain,dut.r_state);
 if(mmio && addresses!=beats_expected) $fatal(1,"snapshot address count");
 if(!mmio && addresses!=(beats_expected+15)/16) $fatal(1,"DDR address count");
 $display("ENGINE_PASS base=%h bytes=%0d beats=%0d addresses=%0d FIFO_writes=%0d",address,count,received,addresses,enqueued);
end
endtask
initial begin
 force dut.fifo_pcie_clk=clk;
 force dut.fifo_pcie_rst=rst;
 force dut.fpga_ddr3_addr=base;
 force dut.fpga_ddr3_length=bytes;
 force dut.fpga_ddr3_total_length=bytes;
 force dut.mwr_tx_busy=start;
 force dut.mrd_rx_busy=0;
 force dut.fpga_tx_clk_en=0;
 force dut.fpga_rx_clk_en=0;
 force dut.fifo_rx_empty=1;
 force dut.fifo_rx_water_level=0;
 force dut.fifo_tx_almost_full=capacity;
 force dut.fifo_tx_empty=1;
 force dut.fifo_tx_water_level=0;
 run_read(32'h40020000,304);
 run_read(32'h40020120,16);
 run_read(32'h40020130,304);
 run_read(32'h00800000,16);
 run_read(32'h00800000,17);
 run_read(32'h00800000,32);
 run_read(32'h00800000,255);
 run_read(32'h00800000,256);
 run_read(32'h00800000,257);
 run_read(32'h00800000,304);
 run_read(32'h0a280000,153600);
 run_read(32'h00800000,614400);
 run_read(32'h00800000,614416);
 run_read(32'h0a000000,1228800);
 if(ar_stalls==0 || r_stalls==0 || capacity_stalls==0) $fatal(1,"backpressure not exercised");
 $display("SIX_BATCH_ENGINE_PASS ar_stalls=%0d r_stalls=%0d capacity_stalls=%0d",ar_stalls,r_stalls,capacity_stalls);
 $finish;
end
endmodule
