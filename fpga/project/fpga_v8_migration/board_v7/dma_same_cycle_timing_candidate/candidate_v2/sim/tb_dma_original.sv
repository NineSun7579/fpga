`timescale 1ns/1ps
module tb_dma_tc02; parameter integer WAIT=1, WIDTH=128, BURST=16;
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
reg [WIDTH - 1:0] data_in=0;
reg [WIDTH/8 - 1:0] data_in_keep=0;
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
wire [WIDTH - 1:0] old_m_axi_wdata, new_m_axi_wdata;
wire [WIDTH/8 - 1:0] old_m_axi_wstrb, new_m_axi_wstrb;
wire  old_m_axi_wlast, new_m_axi_wlast;
wire  old_m_axi_wvalid, new_m_axi_wvalid;
reg  m_axi_wready=0;
reg [4 - 1:0] m_axi_bid=0;
reg [1:0] m_axi_bresp=0;
reg  m_axi_bvalid=0;
wire  old_m_axi_bready, new_m_axi_bready;
axi_dma_write_dma_sc_v2_reference #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(BURST),.DATA_WIDTH(WIDTH)) old_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(old_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(old_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(old_data_in_last),.data_in_ready(old_data_in_ready),.m_axi_awid(old_m_axi_awid),.m_axi_awaddr(old_m_axi_awaddr),.m_axi_awlen(old_m_axi_awlen),.m_axi_awsize(old_m_axi_awsize),.m_axi_awburst(old_m_axi_awburst),.m_axi_awlock(old_m_axi_awlock),.m_axi_awcache(old_m_axi_awcache),.m_axi_awprot(old_m_axi_awprot),.m_axi_awvalid(old_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(old_m_axi_wdata),.m_axi_wstrb(old_m_axi_wstrb),.m_axi_wlast(old_m_axi_wlast),.m_axi_wvalid(old_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(old_m_axi_bready));
axi_dma_write_dma_sc_v2 #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(BURST),.DATA_WIDTH(WIDTH)) new_dut(.clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),.cmd_id(cmd_id),.cmd_ready(new_cmd_ready),.data_in_available(data_in_available),.abort_req(abort_req),.data_in_abort(new_data_in_abort),.data_in(data_in),.data_in_keep(data_in_keep),.data_in_valid(data_in_valid),.data_in_last(new_data_in_last),.data_in_ready(new_data_in_ready),.m_axi_awid(new_m_axi_awid),.m_axi_awaddr(new_m_axi_awaddr),.m_axi_awlen(new_m_axi_awlen),.m_axi_awsize(new_m_axi_awsize),.m_axi_awburst(new_m_axi_awburst),.m_axi_awlock(new_m_axi_awlock),.m_axi_awcache(new_m_axi_awcache),.m_axi_awprot(new_m_axi_awprot),.m_axi_awvalid(new_m_axi_awvalid),.m_axi_awready(m_axi_awready),.m_axi_wdata(new_m_axi_wdata),.m_axi_wstrb(new_m_axi_wstrb),.m_axi_wlast(new_m_axi_wlast),.m_axi_wvalid(new_m_axi_wvalid),.m_axi_wready(m_axi_wready),.m_axi_bid(m_axi_bid),.m_axi_bresp(m_axi_bresp),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(new_m_axi_bready));
integer aw_count=0,w_count=0,lastw_count=0,b_count=0,berr_count=0,abort_count=0,reset_cycles=0,aw_stalls=0,w_stalls=0;
always @(posedge clk) begin
    if(rst) reset_cycles=reset_cycles+1;
    else begin
        if(old_m_axi_awvalid && m_axi_awready) aw_count=aw_count+1;
        if(old_m_axi_wvalid && m_axi_wready) begin w_count=w_count+1; if(old_m_axi_wlast) lastw_count=lastw_count+1; end
        if(old_m_axi_bready && m_axi_bvalid) begin b_count=b_count+1; if(m_axi_bresp[1]) berr_count=berr_count+1; end
        if(old_data_in_abort) abort_count=abort_count+1;
        if(old_m_axi_awvalid && !m_axi_awready) aw_stalls=aw_stalls+1;
        if(old_m_axi_wvalid && !m_axi_wready) w_stalls=w_stalls+1;
    end
end
always #4 clk=~clk;
always @(negedge clk) if(!rst) begin
m_axi_awready=$urandom_range(0,1);m_axi_wready=$urandom_range(0,1);
data_in_valid=$urandom_range(0,1); data_in_available=32;
end
always @(posedge clk) begin
if(rst) m_axi_bvalid<=0; else if(old_m_axi_wvalid && m_axi_wready && old_m_axi_wlast) m_axi_bvalid<=1; else if(m_axi_bvalid && old_m_axi_bready) m_axi_bvalid<=0;
#1; if({old_cmd_ready,old_data_in_abort,old_data_in_last,old_data_in_ready,old_m_axi_awid,old_m_axi_awaddr,old_m_axi_awlen,old_m_axi_awsize,old_m_axi_awburst,old_m_axi_awlock,old_m_axi_awcache,old_m_axi_awprot,old_m_axi_awvalid,old_m_axi_wdata,old_m_axi_wstrb,old_m_axi_wlast,old_m_axi_wvalid,old_m_axi_bready} !== {new_cmd_ready,new_data_in_abort,new_data_in_last,new_data_in_ready,new_m_axi_awid,new_m_axi_awaddr,new_m_axi_awlen,new_m_axi_awsize,new_m_axi_awburst,new_m_axi_awlock,new_m_axi_awcache,new_m_axi_awprot,new_m_axi_awvalid,new_m_axi_wdata,new_m_axi_wstrb,new_m_axi_wlast,new_m_axi_wvalid,new_m_axi_bready}) $fatal(1,"public output mismatch");
if({old_dut.len,old_dut.addr,old_dut.trans,old_dut.burst_trans,old_dut.act_burst_len,old_dut.wd_cnt,old_dut.abort_r,old_dut.available_q,old_dut.w_done,old_dut.burst_len,old_dut.max_burst_len,old_dut.source_burst_ready,old_dut.waiting_source,old_dut.wd_clear,old_dut.wd_step,old_dut.w_progress,old_dut.failed,old_dut.abort_done,old_dut.t_m_axi_wvalid,old_dut.t_m_axi_wready,old_dut.t_m_axi_wdata,old_dut.t_m_axi_wstrb,old_dut.t_m_axi_wlast} !== {new_dut.len,new_dut.addr,new_dut.trans,new_dut.burst_trans,new_dut.act_burst_len,new_dut.wd_cnt,new_dut.abort_r,new_dut.available_q,new_dut.w_done,new_dut.burst_len,new_dut.max_burst_len,new_dut.source_burst_ready,new_dut.waiting_source,new_dut.wd_clear,new_dut.wd_step,new_dut.w_progress,new_dut.failed,new_dut.abort_done,new_dut.t_m_axi_wvalid,new_dut.t_m_axi_wready,new_dut.t_m_axi_wdata,new_dut.t_m_axi_wstrb,new_dut.t_m_axi_wlast}) $fatal(1,"full internal mismatch");
end
integer i,j;reg [31:0] size;
initial begin
data_in_keep=16'hffff;data_in=128'h123456;
for(i=0;i<80;i=i+1) begin
case(i) 0:size=0;1:size=1;2:size=15;3:size=16;4:size=17;5:size=4092;6:size=4096;7:size=32'hffffffff;8:size=32'hfffffff0;9:size=32'h80000001; 10:size=31;11:size=32;12:size=33;13:size=255;14:size=256;15:size=257;16:size=4080;17:size=4081;18:size=4095;19:size=4097;default:size=$urandom;endcase
rst=1;cmd_valid=0;abort_req=0;repeat(4) @(negedge clk);rst=0;
wait(old_cmd_ready);@(negedge clk);cmd_len=size;cmd_addr=32'h01800000 + ((i%8)==0 ? 0 : (i%8)==1 ? 16 : (i%8)==2 ? 2048 : (i%8)==3 ? 3840 : (i%8)==4 ? 4080 : (i%8)==5 ? 4096 : (i%8)==6 ? 8192 : 32'hfff0);cmd_valid=1;
@(negedge clk);cmd_valid=0;
for(j=0;j<400;j=j+1) begin @(negedge clk);if(j==200) abort_req=1;end
end
$display("BUS_COUNTS aw=%0d w=%0d lastw=%0d b=%0d berr=%0d abort=%0d resetcycles=%0d awstalls=%0d wstalls=%0d",aw_count,w_count,lastw_count,b_count,berr_count,abort_count,reset_cycles,aw_stalls,w_stalls);$display("DMA_TC02_PASS cases=80");$finish;end
initial begin #1000000;$fatal(1,"timeout");end
endmodule