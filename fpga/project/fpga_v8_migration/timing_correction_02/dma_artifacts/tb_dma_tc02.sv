`timescale 1ns/1ps
module tb_dma_tc02; parameter integer WAIT=1;
reg  clk=0;
reg  rst=0;
reg  cmd_valid=0;
reg [31:0] cmd_addr=0;
reg [31:0] cmd_len=0;
reg [4 - 1:0] cmd_id=0;
wire  old_cmd_ready, new_cmd_ready;
reg [15:0] data_in_available=0;
reg  abort_req=0;
wire  old_data_in_abort, new_data_in_abort;
reg [128 - 1:0] data_in=0;
reg [16 - 1:0] data_in_keep=0;
reg  data_in_valid=0;
wire  old_data_in_last, new_data_in_last;
wire  old_data_in_ready, new_data_in_ready;
wire [4 - 1:0] old_m_axi_awid, new_m_axi_awid;
wire [31:0] old_m_axi_awaddr, new_m_axi_awaddr;
wire [7:0] old_m_axi_awlen, new_m_axi_awlen;
wire [2:0] old_m_axi_awsize, new_m_axi_awsize;
wire [1:0] old_m_axi_awburst, new_m_axi_awburst;
wire  old_m_axi_awlock, new_m_axi_awlock;
wire [3:0] old_m_axi_awcache, new_m_axi_awcache;
wire [2:0] old_m_axi_awprot, new_m_axi_awprot;
wire  old_m_axi_awvalid, new_m_axi_awvalid;
reg  m_axi_awready=0;
wire [128 - 1:0] old_m_axi_wdata, new_m_axi_wdata;
wire [16 - 1:0] old_m_axi_wstrb, new_m_axi_wstrb;
wire  old_m_axi_wlast, new_m_axi_wlast;
wire  old_m_axi_wvalid, new_m_axi_wvalid;
reg  m_axi_wready=0;
reg [4 - 1:0] m_axi_bid=0;
reg [1:0] m_axi_bresp=0;
reg  m_axi_bvalid=0;
wire  old_m_axi_bready, new_m_axi_bready;
axi_dma_write #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(16)) old_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(old_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(old_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(old_data_in_last),.data_in_ready(old_data_in_ready),.m_axi_awid(old_m_axi_awid),.m_axi_awaddr(old_m_axi_awaddr),.m_axi_awlen(old_m_axi_awlen),.m_axi_awsize(old_m_axi_awsize),.m_axi_awburst(old_m_axi_awburst),.m_axi_awlock(old_m_axi_awlock),.m_axi_awcache(old_m_axi_awcache),.m_axi_awprot(old_m_axi_awprot),.m_axi_awvalid(old_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(old_m_axi_wdata),.m_axi_wstrb(old_m_axi_wstrb),.m_axi_wlast(old_m_axi_wlast),.m_axi_wvalid(old_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(old_m_axi_bready));
axi_dma_write_tc02 #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(16)) new_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(new_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(new_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(new_data_in_last),.data_in_ready(new_data_in_ready),.m_axi_awid(new_m_axi_awid),.m_axi_awaddr(new_m_axi_awaddr),.m_axi_awlen(new_m_axi_awlen),.m_axi_awsize(new_m_axi_awsize),.m_axi_awburst(new_m_axi_awburst),.m_axi_awlock(new_m_axi_awlock),.m_axi_awcache(new_m_axi_awcache),.m_axi_awprot(new_m_axi_awprot),.m_axi_awvalid(new_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(new_m_axi_wdata),.m_axi_wstrb(new_m_axi_wstrb),.m_axi_wlast(new_m_axi_wlast),.m_axi_wvalid(new_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(new_m_axi_bready));
always #4 clk=~clk;
always @(negedge clk) if(!rst) begin
m_axi_awready=$urandom_range(0,1);m_axi_wready=$urandom_range(0,1);
data_in_valid=$urandom_range(0,1); data_in_available=32;
end
always @(posedge clk) begin
if(rst) m_axi_bvalid<=0; else if(old_m_axi_wvalid && m_axi_wready && old_m_axi_wlast) m_axi_bvalid<=1; else if(m_axi_bvalid && old_m_axi_bready) m_axi_bvalid<=0;
#1; if({old_cmd_ready,old_data_in_abort,old_data_in_last,old_data_in_ready,old_m_axi_awid,old_m_axi_awaddr,old_m_axi_awlen,old_m_axi_awsize,old_m_axi_awburst,old_m_axi_awlock,old_m_axi_awcache,old_m_axi_awprot,old_m_axi_awvalid,old_m_axi_wdata,old_m_axi_wstrb,old_m_axi_wlast,old_m_axi_wvalid,old_m_axi_bready} !== {new_cmd_ready,new_data_in_abort,new_data_in_last,new_data_in_ready,new_m_axi_awid,new_m_axi_awaddr,new_m_axi_awlen,new_m_axi_awsize,new_m_axi_awburst,new_m_axi_awlock,new_m_axi_awcache,new_m_axi_awprot,new_m_axi_awvalid,new_m_axi_wdata,new_m_axi_wstrb,new_m_axi_wlast,new_m_axi_wvalid,new_m_axi_bready}) $fatal(1,"public output mismatch");
if(old_dut.len !== {3'b0,new_dut.len}) $fatal(1,"beat count mismatch");
end
integer i,j;reg [31:0] size;
initial begin
data_in_keep=16'hffff;data_in=128'h123456;
for(i=0;i<80;i=i+1) begin
case(i) 0:size=0;1:size=1;2:size=15;3:size=16;4:size=17;5:size=4092;6:size=4096;7:size=32'hffffffff;8:size=32'hfffffff0;9:size=32'h80000001; default:size=$urandom;endcase
rst=1;cmd_valid=0;abort_req=0;repeat(4) @(negedge clk);rst=0;
wait(old_cmd_ready);@(negedge clk);cmd_len=size;cmd_addr=32'h01800ff0;cmd_valid=1;
@(negedge clk);cmd_valid=0;
for(j=0;j<400;j=j+1) begin @(negedge clk);if(j==200) abort_req=1;end
end
$display("DMA_TC02_PASS cases=80");$finish;end
initial begin #1000000;$fatal(1,"timeout");end
endmodule