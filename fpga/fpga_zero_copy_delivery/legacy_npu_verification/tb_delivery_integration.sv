`timescale 1ns/1ps
module tb_delivery_integration;
wire [3:0] npu_out_axi_awid;
assign npu_out_axi_awid = 4'd0;
wire [31:0] npu_out_axi_awaddr;
assign npu_out_axi_awaddr = 32'd0;
wire [3:0] npu_out_axi_awlen;
assign npu_out_axi_awlen = 4'd0;
wire [2:0] npu_out_axi_awsize;
assign npu_out_axi_awsize = 3'd0;
wire [1:0] npu_out_axi_awburst;
assign npu_out_axi_awburst = 2'd0;
wire npu_out_axi_awlock;
assign npu_out_axi_awlock = 1'd0;
wire [3:0] npu_out_axi_awcache;
assign npu_out_axi_awcache = 4'd0;
wire [2:0] npu_out_axi_awprot;
assign npu_out_axi_awprot = 3'd0;
wire npu_out_axi_awvalid;
assign npu_out_axi_awvalid = 1'd0;
wire [127:0] npu_out_axi_wdata;
assign npu_out_axi_wdata = 128'd0;
wire [15:0] npu_out_axi_wstrb;
assign npu_out_axi_wstrb = 16'd0;
wire npu_out_axi_wlast;
assign npu_out_axi_wlast = 1'd0;
wire npu_out_axi_wvalid;
assign npu_out_axi_wvalid = 1'd0;
wire npu_out_axi_bready;
assign npu_out_axi_bready = 1'd1;
wire [3:0] npu_s0_axi_arid;
assign npu_s0_axi_arid = 4'd0;
wire [31:0] npu_s0_axi_araddr;
assign npu_s0_axi_araddr = 32'd0;
wire [3:0] npu_s0_axi_arlen;
assign npu_s0_axi_arlen = 4'd0;
wire [2:0] npu_s0_axi_arsize;
assign npu_s0_axi_arsize = 3'd0;
wire [1:0] npu_s0_axi_arburst;
assign npu_s0_axi_arburst = 2'd0;
wire npu_s0_axi_arlock;
assign npu_s0_axi_arlock = 1'd0;
wire [3:0] npu_s0_axi_arcache;
assign npu_s0_axi_arcache = 4'd0;
wire [2:0] npu_s0_axi_arprot;
assign npu_s0_axi_arprot = 3'd0;
wire npu_s0_axi_arvalid;
assign npu_s0_axi_arvalid = 1'd0;
wire npu_s0_axi_rready;
assign npu_s0_axi_rready = 1'd1;
wire [3:0] npu_s1_axi_arid;
assign npu_s1_axi_arid = 4'd0;
wire [31:0] npu_s1_axi_araddr;
assign npu_s1_axi_araddr = 32'd0;
wire [3:0] npu_s1_axi_arlen;
assign npu_s1_axi_arlen = 4'd0;
wire [2:0] npu_s1_axi_arsize;
assign npu_s1_axi_arsize = 3'd0;
wire [1:0] npu_s1_axi_arburst;
assign npu_s1_axi_arburst = 2'd0;
wire npu_s1_axi_arlock;
assign npu_s1_axi_arlock = 1'd0;
wire [3:0] npu_s1_axi_arcache;
assign npu_s1_axi_arcache = 4'd0;
wire [2:0] npu_s1_axi_arprot;
assign npu_s1_axi_arprot = 3'd0;
wire npu_s1_axi_arvalid;
assign npu_s1_axi_arvalid = 1'd0;
wire npu_s1_axi_rready;
assign npu_s1_axi_rready = 1'd1;
wire [3:0] npu_s2_axi_arid;
assign npu_s2_axi_arid = 4'd0;
wire [31:0] npu_s2_axi_araddr;
assign npu_s2_axi_araddr = 32'd0;
wire [3:0] npu_s2_axi_arlen;
assign npu_s2_axi_arlen = 4'd0;
wire [2:0] npu_s2_axi_arsize;
assign npu_s2_axi_arsize = 3'd0;
wire [1:0] npu_s2_axi_arburst;
assign npu_s2_axi_arburst = 2'd0;
wire npu_s2_axi_arlock;
assign npu_s2_axi_arlock = 1'd0;
wire [3:0] npu_s2_axi_arcache;
assign npu_s2_axi_arcache = 4'd0;
wire [2:0] npu_s2_axi_arprot;
assign npu_s2_axi_arprot = 3'd0;
wire npu_s2_axi_arvalid;
assign npu_s2_axi_arvalid = 1'd0;
wire npu_s2_axi_rready;
assign npu_s2_axi_rready = 1'd1;
    parameter W=4, H=3, OH=5, TOP=1, STALL=1, FAULT=0;
    localparam N=W*OH*3, WORDS=(N+15)/16, READS=(W*H+7)/8;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0, cmd_valid=0;
    wire cmd_ready,busy,done,error,config_error;
    reg [31:0] src=32'h1000,dst=32'h200000;
    wire [31:0] araddr,awaddr;
    wire [7:0] arlen,awlen;
    wire [2:0] arsize,awsize;
    wire [1:0] arburst,awburst;
    wire arvalid,rready,awvalid,wlast,wvalid,bready;
    reg arready=0,awready=0,wready=0,rvalid=0,rlast=1,bvalid=0;
    reg [127:0] rdata=0;
    reg [1:0] rresp=0,bresp=0;
    wire [127:0] wdata;
    wire [15:0] wstrb;

wire capture_hold;
reg [31:0] camera_state=4;
reg [1:0] published=0;
wire [31:0] prev_base=32'h01800000;
reg camera_cmd=0,camera_aw=0,camera_w=0;
wire [31:0] ep_araddr;
wire [7:0] ep_arlen;
wire [2:0] ep_arsize;
wire [1:0] ep_arburst;
wire ep_arvalid;
wire ep_arready;
wire [127:0] ep_rdata;
wire [1:0] ep_rresp;
wire ep_rlast;
wire ep_rvalid;
wire ep_rready;
wire [31:0] ep_awaddr;
wire [7:0] ep_awlen;
wire [2:0] ep_awsize;
wire [1:0] ep_awburst;
wire ep_awvalid;
wire ep_awready;
wire [127:0] ep_wdata;
wire [15:0] ep_wstrb;
wire ep_wlast;
wire ep_wvalid;
wire ep_wready;
wire [1:0] ep_bresp;
wire ep_bvalid;
wire ep_bready;
reg [6:0] host_awid;
reg [31:0] host_awaddr;
reg [7:0] host_awlen;
reg [2:0] host_awsize;
reg [1:0] host_awburst;
reg host_awlock;
reg [3:0] host_awcache;
reg [2:0] host_awprot;
reg [3:0] host_awqos;
reg [3:0] host_awregion;
reg host_awvalid;
wire host_awready;
reg [127:0] host_wdata;
reg [15:0] host_wstrb;
reg host_wlast;
reg host_wvalid;
wire host_wready;
wire [6:0] host_bid;
wire [1:0] host_bresp;
wire host_bvalid;
reg host_bready;
reg [6:0] host_arid;
reg [31:0] host_araddr;
reg [7:0] host_arlen;
reg [2:0] host_arsize;
reg [1:0] host_arburst;
reg host_arlock;
reg [3:0] host_arcache;
reg [2:0] host_arprot;
reg [3:0] host_arqos;
reg [3:0] host_arregion;
reg host_arvalid;
wire host_arready;
wire [6:0] host_rid;
wire [127:0] host_rdata;
wire [1:0] host_rresp;
wire host_rlast;
wire host_rvalid;
reg host_rready;
wire [6:0] mmio_awid;
wire [31:0] mmio_awaddr;
wire [7:0] mmio_awlen;
wire [2:0] mmio_awsize;
wire [1:0] mmio_awburst;
wire mmio_awlock;
wire [3:0] mmio_awcache;
wire [2:0] mmio_awprot;
wire [3:0] mmio_awqos;
wire [3:0] mmio_awregion;
wire mmio_awvalid;
wire mmio_awready;
wire [127:0] mmio_wdata;
wire [15:0] mmio_wstrb;
wire mmio_wlast;
wire mmio_wvalid;
wire mmio_wready;
wire [6:0] mmio_bid;
wire [1:0] mmio_bresp;
wire mmio_bvalid;
wire mmio_bready;
wire [6:0] mmio_arid;
wire [31:0] mmio_araddr;
wire [7:0] mmio_arlen;
wire [2:0] mmio_arsize;
wire [1:0] mmio_arburst;
wire mmio_arlock;
wire [3:0] mmio_arcache;
wire [2:0] mmio_arprot;
wire [3:0] mmio_arqos;
wire [3:0] mmio_arregion;
wire mmio_arvalid;
wire mmio_arready;
wire [6:0] mmio_rid;
wire [127:0] mmio_rdata;
wire [1:0] mmio_rresp;
wire mmio_rlast;
wire mmio_rvalid;
wire mmio_rready;
delivery_top_adapter #(.WIDTH(W),.HEIGHT(H),.OUT_HEIGHT(OH),.TOP_ROWS(TOP)) dut (
.clk(clk),.rst(!rst_n),.capture_hold(capture_hold),.camera_state(camera_state),
.camera_prev_base(prev_base),.camera_published(published),.camera_cmd_valid(camera_cmd),
.camera_awvalid(camera_aw),.camera_wvalid(camera_w),.camera_abort(1'b0),
.s_axi_awid(mmio_awid),
.s_axi_awaddr(mmio_awaddr),
.s_axi_awlen(mmio_awlen),
.s_axi_awsize(mmio_awsize),
.s_axi_awburst(mmio_awburst),
.s_axi_awlock(mmio_awlock),
.s_axi_awcache(mmio_awcache),
.s_axi_awprot(mmio_awprot),
.s_axi_awqos(mmio_awqos),
.s_axi_awregion(mmio_awregion),
.s_axi_awvalid(mmio_awvalid),
.s_axi_awready(mmio_awready),
.s_axi_wdata(mmio_wdata),
.s_axi_wstrb(mmio_wstrb),
.s_axi_wlast(mmio_wlast),
.s_axi_wvalid(mmio_wvalid),
.s_axi_wready(mmio_wready),
.s_axi_bid(mmio_bid),
.s_axi_bresp(mmio_bresp),
.s_axi_bvalid(mmio_bvalid),
.s_axi_bready(mmio_bready),
.s_axi_arid(mmio_arid),
.s_axi_araddr(mmio_araddr),
.s_axi_arlen(mmio_arlen),
.s_axi_arsize(mmio_arsize),
.s_axi_arburst(mmio_arburst),
.s_axi_arlock(mmio_arlock),
.s_axi_arcache(mmio_arcache),
.s_axi_arprot(mmio_arprot),
.s_axi_arqos(mmio_arqos),
.s_axi_arregion(mmio_arregion),
.s_axi_arvalid(mmio_arvalid),
.s_axi_arready(mmio_arready),
.s_axi_rid(mmio_rid),
.s_axi_rdata(mmio_rdata),
.s_axi_rresp(mmio_rresp),
.s_axi_rlast(mmio_rlast),
.s_axi_rvalid(mmio_rvalid),
.s_axi_rready(mmio_rready),
.m_axi_araddr(ep_araddr),
.m_axi_arlen(ep_arlen),
.m_axi_arsize(ep_arsize),
.m_axi_arburst(ep_arburst),
.m_axi_arvalid(ep_arvalid),
.m_axi_arready(ep_arready),
.m_axi_rdata(ep_rdata),
.m_axi_rresp(ep_rresp),
.m_axi_rlast(ep_rlast),
.m_axi_rvalid(ep_rvalid),
.m_axi_rready(ep_rready),
.m_axi_awaddr(ep_awaddr),
.m_axi_awlen(ep_awlen),
.m_axi_awsize(ep_awsize),
.m_axi_awburst(ep_awburst),
.m_axi_awvalid(ep_awvalid),
.m_axi_awready(ep_awready),
.m_axi_wdata(ep_wdata),
.m_axi_wstrb(ep_wstrb),
.m_axi_wlast(ep_wlast),
.m_axi_wvalid(ep_wvalid),
.m_axi_wready(ep_wready),
.m_axi_bresp(ep_bresp),
.m_axi_bvalid(ep_bvalid),
.m_axi_bready(ep_bready)
);
wire [3:0] slave_awid;
integer camera_writes[0:5];
wire [5:0] c_awready,c_wready;
reg [5:0] c_pending=0;
integer c;
always @(posedge clk) if(!rst_n) c_pending<=0; else for(c=0;c<6;c=c+1) begin
if(c_awready[c]) c_pending[c]<=1; if(c_wready[c] && c_pending[c]) c_pending[c]<=0; end
ddr_w_arb arb (.clk(clk),.rst(!rst_n),
.m0_awid(4'd0),
.m0_awaddr(32'h00100000),
.m0_awlen(8'd0),
.m0_awsize(3'd4),
.m0_awburst(2'd1),
.m0_awlock(1'b0),
.m0_awcache(4'd0),
.m0_awprot(3'd0),
.m0_awvalid(1'b1),
.m0_awready(c_awready[0]),
.m0_wdata(128'd1),
.m0_wstrb(16'hffff),
.m0_wlast(1'b1),
.m0_wvalid(c_pending[0]),
.m0_wready(c_wready[0]),
.m0_bid(),
.m0_bresp(),
.m0_bvalid(),
.m0_bready(1'b1),
.m1_awid(4'd1),
.m1_awaddr(32'h00100010),
.m1_awlen(8'd0),
.m1_awsize(3'd4),
.m1_awburst(2'd1),
.m1_awlock(1'b0),
.m1_awcache(4'd0),
.m1_awprot(3'd0),
.m1_awvalid(1'b1),
.m1_awready(c_awready[1]),
.m1_wdata(128'd2),
.m1_wstrb(16'hffff),
.m1_wlast(1'b1),
.m1_wvalid(c_pending[1]),
.m1_wready(c_wready[1]),
.m1_bid(),
.m1_bresp(),
.m1_bvalid(),
.m1_bready(1'b1),
.m2_awid(4'd2),
.m2_awaddr(32'h00100020),
.m2_awlen(8'd0),
.m2_awsize(3'd4),
.m2_awburst(2'd1),
.m2_awlock(1'b0),
.m2_awcache(4'd0),
.m2_awprot(3'd0),
.m2_awvalid(1'b1),
.m2_awready(c_awready[2]),
.m2_wdata(128'd3),
.m2_wstrb(16'hffff),
.m2_wlast(1'b1),
.m2_wvalid(c_pending[2]),
.m2_wready(c_wready[2]),
.m2_bid(),
.m2_bresp(),
.m2_bvalid(),
.m2_bready(1'b1),
.m3_awid(4'd3),
.m3_awaddr(32'h00100030),
.m3_awlen(8'd0),
.m3_awsize(3'd4),
.m3_awburst(2'd1),
.m3_awlock(1'b0),
.m3_awcache(4'd0),
.m3_awprot(3'd0),
.m3_awvalid(1'b1),
.m3_awready(c_awready[3]),
.m3_wdata(128'd4),
.m3_wstrb(16'hffff),
.m3_wlast(1'b1),
.m3_wvalid(c_pending[3]),
.m3_wready(c_wready[3]),
.m3_bid(),
.m3_bresp(),
.m3_bvalid(),
.m3_bready(1'b1),
.m4_awid(4'd4),
.m4_awaddr(32'h00100040),
.m4_awlen(8'd0),
.m4_awsize(3'd4),
.m4_awburst(2'd1),
.m4_awlock(1'b0),
.m4_awcache(4'd0),
.m4_awprot(3'd0),
.m4_awvalid(1'b1),
.m4_awready(c_awready[4]),
.m4_wdata(128'd5),
.m4_wstrb(16'hffff),
.m4_wlast(1'b1),
.m4_wvalid(c_pending[4]),
.m4_wready(c_wready[4]),
.m4_bid(),
.m4_bresp(),
.m4_bvalid(),
.m4_bready(1'b1),
.m5_awid(4'd5),
.m5_awaddr(32'h00100050),
.m5_awlen(8'd0),
.m5_awsize(3'd4),
.m5_awburst(2'd1),
.m5_awlock(1'b0),
.m5_awcache(4'd0),
.m5_awprot(3'd0),
.m5_awvalid(1'b1),
.m5_awready(c_awready[5]),
.m5_wdata(128'd6),
.m5_wstrb(16'hffff),
.m5_wlast(1'b1),
.m5_wvalid(c_pending[5]),
.m5_wready(c_wready[5]),
.m5_bid(),
.m5_bresp(),
.m5_bvalid(),
.m5_bready(1'b1),
.m6_awid(4'hd),
.m6_awaddr(ep_awaddr),
.m6_awlen(ep_awlen),
.m6_awsize(ep_awsize),
.m6_awburst(ep_awburst),
.m6_awlock(1'b0),
.m6_awcache(4'd0),
.m6_awprot(3'd0),
.m6_awvalid(ep_awvalid),
.m6_awready(ep_awready),
.m6_wdata(ep_wdata),
.m6_wstrb(ep_wstrb),
.m6_wlast(ep_wlast),
.m6_wvalid(ep_wvalid),
.m6_wready(ep_wready),
.m6_bid(),
.m6_bresp(ep_bresp),
.m6_bvalid(ep_bvalid),
.m6_bready(ep_bready),
.s_awid(slave_awid),
.s_awaddr(awaddr),
.s_awlen(awlen),
.s_awsize(awsize),
.s_awburst(awburst),
.s_awlock(),
.s_awcache(),
.s_awprot(),
.s_awvalid(awvalid),
.s_awready(awready),
.s_wdata(wdata),
.s_wstrb(wstrb),
.s_wlast(wlast),
.s_wvalid(wvalid),
.s_wready(wready),
.s_bid(4'd0),
.s_bresp(bresp),
.s_bvalid(bvalid),
.s_bready(bready)
);
axi_crossbar_7x3 #(.M00_CONNECT_READ(7'b1111101),.M00_CONNECT_WRITE(7'd0),
.M01_CONNECT_READ(7'd1),.M01_CONNECT_WRITE(7'd1),
.M02_CONNECT_READ(7'd1),.M02_CONNECT_WRITE(7'd1)) xbar (
.clk(clk),
.rst(!rst_n),
.s00_axi_awid(host_awid),
.s00_axi_awaddr(host_awaddr),
.s00_axi_awlen(host_awlen),
.s00_axi_awsize(host_awsize),
.s00_axi_awburst(host_awburst),
.s00_axi_awlock(host_awlock),
.s00_axi_awcache(host_awcache),
.s00_axi_awprot(host_awprot),
.s00_axi_awqos(host_awqos),
.s00_axi_awvalid(host_awvalid),
.s00_axi_awready(host_awready),
.s00_axi_wdata(host_wdata),
.s00_axi_wstrb(host_wstrb),
.s00_axi_wlast(host_wlast),
.s00_axi_wvalid(host_wvalid),
.s00_axi_wready(host_wready),
.s00_axi_bid(host_bid),
.s00_axi_bresp(host_bresp),
.s00_axi_bvalid(host_bvalid),
.s00_axi_bready(host_bready),
.s00_axi_arid(host_arid),
.s00_axi_araddr(host_araddr),
.s00_axi_arlen(host_arlen),
.s00_axi_arsize(host_arsize),
.s00_axi_arburst(host_arburst),
.s00_axi_arlock(host_arlock),
.s00_axi_arcache(host_arcache),
.s00_axi_arprot(host_arprot),
.s00_axi_arqos(host_arqos),
.s00_axi_arvalid(host_arvalid),
.s00_axi_arready(host_arready),
.s00_axi_rid(host_rid),
.s00_axi_rdata(host_rdata),
.s00_axi_rresp(host_rresp),
.s00_axi_rlast(host_rlast),
.s00_axi_rvalid(host_rvalid),
.s00_axi_rready(host_rready),
.s00_axi_awuser(),
.s00_axi_wuser(),
.s00_axi_buser(),
.s00_axi_aruser(),
.s00_axi_ruser(),
.s01_axi_awid(4'd0),
.s01_axi_awaddr(32'd0),
.s01_axi_awlen(8'd0),
.s01_axi_awsize(3'd0),
.s01_axi_awburst(2'd0),
.s01_axi_awlock(1'd0),
.s01_axi_awcache(4'd0),
.s01_axi_awprot(3'd0),
.s01_axi_awqos(4'd0),
.s01_axi_awvalid(1'd0),
.s01_axi_awready(),
.s01_axi_wdata(128'd0),
.s01_axi_wstrb(16'd0),
.s01_axi_wlast(1'd0),
.s01_axi_wvalid(1'd0),
.s01_axi_wready(),
.s01_axi_bid(),
.s01_axi_bresp(),
.s01_axi_bvalid(),
.s01_axi_bready(1'd0),
.s01_axi_arid(4'd0),
.s01_axi_araddr(32'd0),
.s01_axi_arlen(8'd0),
.s01_axi_arsize(3'd0),
.s01_axi_arburst(2'd0),
.s01_axi_arlock(1'd0),
.s01_axi_arcache(4'd0),
.s01_axi_arprot(3'd0),
.s01_axi_arqos(4'd0),
.s01_axi_arvalid(1'd0),
.s01_axi_arready(),
.s01_axi_rid(),
.s01_axi_rdata(),
.s01_axi_rresp(),
.s01_axi_rlast(),
.s01_axi_rvalid(),
.s01_axi_rready(1'd0),
.s01_axi_awuser(),
.s01_axi_wuser(),
.s01_axi_buser(),
.s01_axi_aruser(),
.s01_axi_ruser(),
.s02_axi_awid(npu_out_axi_awid),
.s02_axi_awaddr(npu_out_axi_awaddr),
.s02_axi_awlen(npu_out_axi_awlen),
.s02_axi_awsize(npu_out_axi_awsize),
.s02_axi_awburst(npu_out_axi_awburst),
.s02_axi_awlock(npu_out_axi_awlock),
.s02_axi_awcache(npu_out_axi_awcache),
.s02_axi_awprot(npu_out_axi_awprot),
.s02_axi_awqos(4'd0),
.s02_axi_awvalid(npu_out_axi_awvalid),
.s02_axi_awready(),
.s02_axi_wdata(npu_out_axi_wdata),
.s02_axi_wstrb(npu_out_axi_wstrb),
.s02_axi_wlast(npu_out_axi_wlast),
.s02_axi_wvalid(npu_out_axi_wvalid),
.s02_axi_wready(),
.s02_axi_bid(),
.s02_axi_bresp(),
.s02_axi_bvalid(),
.s02_axi_bready(npu_out_axi_bready),
.s02_axi_arid(npu_s0_axi_arid),
.s02_axi_araddr(npu_s0_axi_araddr),
.s02_axi_arlen(npu_s0_axi_arlen),
.s02_axi_arsize(npu_s0_axi_arsize),
.s02_axi_arburst(npu_s0_axi_arburst),
.s02_axi_arlock(npu_s0_axi_arlock),
.s02_axi_arcache(npu_s0_axi_arcache),
.s02_axi_arprot(npu_s0_axi_arprot),
.s02_axi_arqos(4'd0),
.s02_axi_arvalid(npu_s0_axi_arvalid),
.s02_axi_arready(),
.s02_axi_rid(),
.s02_axi_rdata(),
.s02_axi_rresp(),
.s02_axi_rlast(),
.s02_axi_rvalid(),
.s02_axi_rready(npu_s0_axi_rready),
.s02_axi_awuser(),
.s02_axi_wuser(),
.s02_axi_buser(),
.s02_axi_aruser(),
.s02_axi_ruser(),
.s03_axi_awid(4'd0),
.s03_axi_awaddr(32'd0),
.s03_axi_awlen(8'd0),
.s03_axi_awsize(3'd0),
.s03_axi_awburst(2'd0),
.s03_axi_awlock(1'd0),
.s03_axi_awcache(4'd0),
.s03_axi_awprot(3'd0),
.s03_axi_awqos(4'd0),
.s03_axi_awvalid(1'd0),
.s03_axi_awready(),
.s03_axi_wdata(128'd0),
.s03_axi_wstrb(16'd0),
.s03_axi_wlast(1'd0),
.s03_axi_wvalid(1'd0),
.s03_axi_wready(),
.s03_axi_bid(),
.s03_axi_bresp(),
.s03_axi_bvalid(),
.s03_axi_bready(1'd0),
.s03_axi_arid(npu_s1_axi_arid),
.s03_axi_araddr(npu_s1_axi_araddr),
.s03_axi_arlen(npu_s1_axi_arlen),
.s03_axi_arsize(npu_s1_axi_arsize),
.s03_axi_arburst(npu_s1_axi_arburst),
.s03_axi_arlock(npu_s1_axi_arlock),
.s03_axi_arcache(npu_s1_axi_arcache),
.s03_axi_arprot(npu_s1_axi_arprot),
.s03_axi_arqos(4'd0),
.s03_axi_arvalid(npu_s1_axi_arvalid),
.s03_axi_arready(),
.s03_axi_rid(),
.s03_axi_rdata(),
.s03_axi_rresp(),
.s03_axi_rlast(),
.s03_axi_rvalid(),
.s03_axi_rready(npu_s1_axi_rready),
.s03_axi_awuser(),
.s03_axi_wuser(),
.s03_axi_buser(),
.s03_axi_aruser(),
.s03_axi_ruser(),
.s04_axi_awid(4'd0),
.s04_axi_awaddr(32'd0),
.s04_axi_awlen(8'd0),
.s04_axi_awsize(3'd0),
.s04_axi_awburst(2'd0),
.s04_axi_awlock(1'd0),
.s04_axi_awcache(4'd0),
.s04_axi_awprot(3'd0),
.s04_axi_awqos(4'd0),
.s04_axi_awvalid(1'd0),
.s04_axi_awready(),
.s04_axi_wdata(128'd0),
.s04_axi_wstrb(16'd0),
.s04_axi_wlast(1'd0),
.s04_axi_wvalid(1'd0),
.s04_axi_wready(),
.s04_axi_bid(),
.s04_axi_bresp(),
.s04_axi_bvalid(),
.s04_axi_bready(1'd0),
.s04_axi_arid(npu_s2_axi_arid),
.s04_axi_araddr(npu_s2_axi_araddr),
.s04_axi_arlen(npu_s2_axi_arlen),
.s04_axi_arsize(npu_s2_axi_arsize),
.s04_axi_arburst(npu_s2_axi_arburst),
.s04_axi_arlock(npu_s2_axi_arlock),
.s04_axi_arcache(npu_s2_axi_arcache),
.s04_axi_arprot(npu_s2_axi_arprot),
.s04_axi_arqos(4'd0),
.s04_axi_arvalid(npu_s2_axi_arvalid),
.s04_axi_arready(),
.s04_axi_rid(),
.s04_axi_rdata(),
.s04_axi_rresp(),
.s04_axi_rlast(),
.s04_axi_rvalid(),
.s04_axi_rready(npu_s2_axi_rready),
.s04_axi_awuser(),
.s04_axi_wuser(),
.s04_axi_buser(),
.s04_axi_aruser(),
.s04_axi_ruser(),
.s05_axi_awid(4'd0),
.s05_axi_awaddr(32'd0),
.s05_axi_awlen(8'd0),
.s05_axi_awsize(3'd0),
.s05_axi_awburst(2'd0),
.s05_axi_awlock(1'd0),
.s05_axi_awcache(4'd0),
.s05_axi_awprot(3'd0),
.s05_axi_awqos(4'd0),
.s05_axi_awvalid(1'd0),
.s05_axi_awready(),
.s05_axi_wdata(128'd0),
.s05_axi_wstrb(16'd0),
.s05_axi_wlast(1'd0),
.s05_axi_wvalid(1'd0),
.s05_axi_wready(),
.s05_axi_bid(),
.s05_axi_bresp(),
.s05_axi_bvalid(),
.s05_axi_bready(1'd0),
.s05_axi_arid(4'd0),
.s05_axi_araddr(32'd0),
.s05_axi_arlen(8'd0),
.s05_axi_arsize(3'd0),
.s05_axi_arburst(2'd0),
.s05_axi_arlock(1'd0),
.s05_axi_arcache(4'd0),
.s05_axi_arprot(3'd0),
.s05_axi_arqos(4'd0),
.s05_axi_arvalid(1'd0),
.s05_axi_arready(),
.s05_axi_rid(),
.s05_axi_rdata(),
.s05_axi_rresp(),
.s05_axi_rlast(),
.s05_axi_rvalid(),
.s05_axi_rready(1'd0),
.s05_axi_awuser(),
.s05_axi_wuser(),
.s05_axi_buser(),
.s05_axi_aruser(),
.s05_axi_ruser(),
.s06_axi_awid(4'd0),
.s06_axi_awaddr(32'd0),
.s06_axi_awlen(8'd0),
.s06_axi_awsize(3'd0),
.s06_axi_awburst(2'd0),
.s06_axi_awlock(1'd0),
.s06_axi_awcache(4'd0),
.s06_axi_awprot(3'd0),
.s06_axi_awqos(4'd0),
.s06_axi_awvalid(1'd0),
.s06_axi_awready(),
.s06_axi_wdata(128'd0),
.s06_axi_wstrb(16'd0),
.s06_axi_wlast(1'd0),
.s06_axi_wvalid(1'd0),
.s06_axi_wready(),
.s06_axi_bid(),
.s06_axi_bresp(),
.s06_axi_bvalid(),
.s06_axi_bready(1'd0),
.s06_axi_arid(4'hd),
.s06_axi_araddr(ep_araddr),
.s06_axi_arlen(ep_arlen),
.s06_axi_arsize(ep_arsize),
.s06_axi_arburst(ep_arburst),
.s06_axi_arlock(1'b0),
.s06_axi_arcache(4'd0),
.s06_axi_arprot(3'd0),
.s06_axi_arqos(4'd0),
.s06_axi_arvalid(ep_arvalid),
.s06_axi_arready(ep_arready),
.s06_axi_rid(),
.s06_axi_rdata(ep_rdata),
.s06_axi_rresp(ep_rresp),
.s06_axi_rlast(ep_rlast),
.s06_axi_rvalid(ep_rvalid),
.s06_axi_rready(ep_rready),
.s06_axi_awuser(),
.s06_axi_wuser(),
.s06_axi_buser(),
.s06_axi_aruser(),
.s06_axi_ruser(),
.m00_axi_awid(),
.m00_axi_awaddr(),
.m00_axi_awlen(),
.m00_axi_awsize(),
.m00_axi_awburst(),
.m00_axi_awlock(),
.m00_axi_awcache(),
.m00_axi_awprot(),
.m00_axi_awqos(),
.m00_axi_awregion(),
.m00_axi_awvalid(),
.m00_axi_awready(1'd0),
.m00_axi_wdata(),
.m00_axi_wstrb(),
.m00_axi_wlast(),
.m00_axi_wvalid(),
.m00_axi_wready(1'd0),
.m00_axi_bid(7'd0),
.m00_axi_bresp(2'd0),
.m00_axi_bvalid(1'd0),
.m00_axi_bready(),
.m00_axi_arid(),
.m00_axi_araddr(araddr),
.m00_axi_arlen(arlen),
.m00_axi_arsize(arsize),
.m00_axi_arburst(arburst),
.m00_axi_arlock(),
.m00_axi_arcache(),
.m00_axi_arprot(),
.m00_axi_arqos(),
.m00_axi_arregion(),
.m00_axi_arvalid(arvalid),
.m00_axi_arready(arready),
.m00_axi_rid(7'h6d),
.m00_axi_rdata(rdata),
.m00_axi_rresp(rresp),
.m00_axi_rlast(rlast),
.m00_axi_rvalid(rvalid),
.m00_axi_rready(rready),
.m00_axi_awuser(),
.m00_axi_wuser(),
.m00_axi_buser(),
.m00_axi_aruser(),
.m00_axi_ruser(),
.m01_axi_awid(),
.m01_axi_awaddr(),
.m01_axi_awlen(),
.m01_axi_awsize(),
.m01_axi_awburst(),
.m01_axi_awlock(),
.m01_axi_awcache(),
.m01_axi_awprot(),
.m01_axi_awqos(),
.m01_axi_awregion(),
.m01_axi_awvalid(),
.m01_axi_awready(1'd0),
.m01_axi_wdata(),
.m01_axi_wstrb(),
.m01_axi_wlast(),
.m01_axi_wvalid(),
.m01_axi_wready(1'd0),
.m01_axi_bid(7'd0),
.m01_axi_bresp(2'd0),
.m01_axi_bvalid(1'd0),
.m01_axi_bready(),
.m01_axi_arid(),
.m01_axi_araddr(),
.m01_axi_arlen(),
.m01_axi_arsize(),
.m01_axi_arburst(),
.m01_axi_arlock(),
.m01_axi_arcache(),
.m01_axi_arprot(),
.m01_axi_arqos(),
.m01_axi_arregion(),
.m01_axi_arvalid(),
.m01_axi_arready(1'd0),
.m01_axi_rid(7'd0),
.m01_axi_rdata(128'd0),
.m01_axi_rresp(2'd0),
.m01_axi_rlast(1'd0),
.m01_axi_rvalid(1'd0),
.m01_axi_rready(),
.m01_axi_awuser(),
.m01_axi_wuser(),
.m01_axi_buser(),
.m01_axi_aruser(),
.m01_axi_ruser(),
.m02_axi_awid(mmio_awid),
.m02_axi_awaddr(mmio_awaddr),
.m02_axi_awlen(mmio_awlen),
.m02_axi_awsize(mmio_awsize),
.m02_axi_awburst(mmio_awburst),
.m02_axi_awlock(mmio_awlock),
.m02_axi_awcache(mmio_awcache),
.m02_axi_awprot(mmio_awprot),
.m02_axi_awqos(mmio_awqos),
.m02_axi_awregion(mmio_awregion),
.m02_axi_awvalid(mmio_awvalid),
.m02_axi_awready(mmio_awready),
.m02_axi_wdata(mmio_wdata),
.m02_axi_wstrb(mmio_wstrb),
.m02_axi_wlast(mmio_wlast),
.m02_axi_wvalid(mmio_wvalid),
.m02_axi_wready(mmio_wready),
.m02_axi_bid(mmio_bid),
.m02_axi_bresp(mmio_bresp),
.m02_axi_bvalid(mmio_bvalid),
.m02_axi_bready(mmio_bready),
.m02_axi_arid(mmio_arid),
.m02_axi_araddr(mmio_araddr),
.m02_axi_arlen(mmio_arlen),
.m02_axi_arsize(mmio_arsize),
.m02_axi_arburst(mmio_arburst),
.m02_axi_arlock(mmio_arlock),
.m02_axi_arcache(mmio_arcache),
.m02_axi_arprot(mmio_arprot),
.m02_axi_arqos(mmio_arqos),
.m02_axi_arregion(mmio_arregion),
.m02_axi_arvalid(mmio_arvalid),
.m02_axi_arready(mmio_arready),
.m02_axi_rid(mmio_rid),
.m02_axi_rdata(mmio_rdata),
.m02_axi_rresp(mmio_rresp),
.m02_axi_rlast(mmio_rlast),
.m02_axi_rvalid(mmio_rvalid),
.m02_axi_rready(mmio_rready),
.m02_axi_awuser(),
.m02_axi_wuser(),
.m02_axi_buser(),
.m02_axi_aruser(),
.m02_axi_ruser()
);

    reg [31:0] value;
    reg [1:0] expected_bresp=0, expected_rresp=0;
    task mmio_write(input [31:0] offset,input [31:0] data);
        begin
            @(negedge clk); host_awaddr=32'h40020000+offset; host_awvalid=1;
            host_wdata=data; host_wvalid=0;
            do @(posedge clk); while (!host_awready);
            @(negedge clk); host_awvalid=0; host_wvalid=1;
            do @(posedge clk); while (!host_wready);
            @(negedge clk); host_wvalid=0;
            wait(host_bvalid); if(host_bresp!=expected_bresp) $fatal(1,"FAIL MMIO write");
            @(negedge clk); host_bready=1; @(negedge clk); host_bready=0;
        end
    endtask
    task mmio_read(input [31:0] offset,output [31:0] data);
        begin
            @(negedge clk); host_araddr=32'h40020000+offset; host_arvalid=1;
            do @(posedge clk); while(!host_arready);
            @(negedge clk); host_arvalid=0;
            wait(host_rvalid); if(host_rresp!=expected_rresp || !host_rlast) $fatal(1,"FAIL MMIO read");
            data=host_rdata[31:0];
            // Check response remains stable under independent host backpressure.
            repeat(3) @(negedge clk);
            if(host_rdata[31:0]!==data || !host_rvalid) $fatal(1,"FAIL MMIO read stall");
            host_rready=1; @(negedge clk); host_rready=0;
        end
    endtask
    reg [7:0] expected[0:N*2-1];
    integer cycle=0,read_count=0,write_count=0,frame=0,fd,i;
    integer rd_delay=-1,wr_delay=-1;
    reg got_aw=0,got_w=0;
    reg [31:0] saved_aw;
    reg [3:0] saved_owner;
    reg [127:0] saved_w;
    reg [15:0] saved_strb;
    reg [127:0] staged_w[0:15];
    reg [15:0] staged_strb[0:15];
    integer rd_left=0,wr_beats=0,staged_count=0,j,physical_offset,logical_offset;
    reg prev_arstall=0,prev_awstall=0,prev_wstall=0;
    reg [31:0] prev_ar,prev_aw;
    reg [127:0] prev_w;
    reg [15:0] prev_strb;
    reg [31:0] rng=32'h12345678;
    // Independent channels, delayed responses, W can precede AW.
    always @(negedge clk) begin
        rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
        arready=rst_n && (!STALL || rng[0]);
        awready=rst_n && (!STALL || rng[1]);
        wready=rst_n && (!STALL || rng[2]);
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if (cycle>10000000) $fatal(1,"FAIL watchdog");
        if (!rst_n) begin
            rvalid<=0; bvalid<=0; rd_delay=-1; wr_delay=-1;
            got_aw=0; got_w=0; read_count=0; write_count=0;
            rd_left=0; staged_count=0;
            prev_arstall=0; prev_awstall=0; prev_wstall=0;
        end else begin
            if (prev_arstall && (!arvalid || araddr!==prev_ar)) $fatal(1,"FAIL AR stall");
            if (prev_awstall && (!awvalid || awaddr!==prev_aw)) $fatal(1,"FAIL AW stall");
            if (prev_wstall && (!wvalid || wdata!==prev_w || wstrb!==prev_strb)) $fatal(1,"FAIL W stall");
            prev_arstall=arvalid&&!arready; prev_ar=araddr;
            prev_awstall=awvalid&&!awready; prev_aw=awaddr;
            prev_wstall=wvalid&&!wready; prev_w=wdata; prev_strb=wstrb;
            if (arvalid && arready) begin
                if (rd_delay>=0 || rvalid) $fatal(1,"FAIL overlapping read");
                if (araddr!==32'h01800000+read_count*16 || arlen!=(READS-read_count>=16 ? 15 : READS-read_count-1) || arsize!=4 || arburst!=1)
                    $fatal(1,"FAIL read address/attributes");
                // HMIC native word address -> physical bytes. Camera stores
                // 256 physical bytes per 512-byte slot (burst16, bus stride256).
                physical_offset=(araddr-32'h01800000)*2;
                logical_offset=(physical_offset/512)*256+physical_offset%512;
                for (i=0;i<8;i=i+1) rdata[i*16 +:16]<=((logical_offset/2+i) ^ (frame*16'h1357)) & 65535;
                rd_left=arlen+1; rd_delay=STALL ? 3 : 0;
                rresp<=(FAULT==1 && frame==0) ? 2 : 0;
                rlast<=(rd_left==1) && !(FAULT==3 && frame==0);
            end else if (rd_delay>0) rd_delay=rd_delay-1;
            else if (rd_delay==0) begin rvalid<=1; rd_delay=-1; end
            if (rvalid && rready) begin
                read_count=read_count+1; rd_left=rd_left-1; rvalid<=0;
                if (rd_left>0) begin
                    for (i=0;i<8;i=i+1) rdata[i*16 +:16]<=((read_count*8+i) ^ (frame*16'h1357)) & 65535;
                    rlast<=(rd_left==1) && !(FAULT==3 && frame==0);
                    rd_delay=STALL ? 3 : 0;
                end
            end
            if (awvalid && awready) begin
                if (got_aw || (slave_awid==13 && (awaddr!==32'h0a000000+write_count*16 || awlen!=(WORDS-write_count>=16 ? 15 : WORDS-write_count-1))) || awsize!=4 || awburst!=1)
                    $fatal(1,"FAIL write address/attributes");
                saved_aw=awaddr; saved_owner=slave_awid; got_aw=1;
                wr_beats=awlen+1;
            end
            if (wvalid && wready) begin
                if (got_w || staged_count>=16) $fatal(1,"FAIL overlapping write/last");
                staged_w[staged_count]=wdata; staged_strb[staged_count]=wstrb;
                staged_count=staged_count+1; got_w=wlast;
            end
            if (got_aw && got_w && wr_delay<0 && !bvalid) begin
                if(staged_count!=wr_beats) $fatal(1,"FAIL burst beat count");
                for(j=0;j<wr_beats;j=j+1) begin
                saved_w=staged_w[j]; saved_strb=staged_strb[j];
                // Native HMIC address stride within a burst is eight WORDS.
                physical_offset=(saved_aw-32'h0a000000)*2+j*16;
                logical_offset=(physical_offset/512)*256+physical_offset%512;
                if (saved_owner==13 && (FAULT==0 || frame>0)) begin
                    for (i=0;i<16;i=i+1) begin
                        if (write_count*16+i<N) begin
                            if(logical_offset!=write_count*16) $fatal(1,"FAIL physical DDR layout");
                            if (!saved_strb[i] || saved_w[i*8 +:8]!==expected[frame*N+write_count*16+i])
                                $fatal(1,"FAIL RGB byte frame=%0d word=%0d lane=%0d",frame,write_count,i);
                        end else if (saved_strb[i]) $fatal(1,"FAIL tail guard overwritten");
                    end
                end
                if(saved_owner==13) begin
                    $fdisplay(fd,"%0d %08h %032h %04h",frame,saved_aw,saved_w,saved_strb);
                    write_count=write_count+1;
                end else begin
                    if(saved_owner>5 || saved_w!==saved_owner+1) $fatal(1,"FAIL camera data routing");
                    camera_writes[saved_owner]=camera_writes[saved_owner]+1;
                end
                end
                wr_delay=STALL ? 5 : 0;
                bresp<=(FAULT==2 && frame==0) ? 2 : 0;
            end else if (wr_delay>0) wr_delay=wr_delay-1;
            else if (wr_delay==0) begin bvalid<=1; wr_delay=-1; end
            if (bvalid && bready) begin bvalid<=0; got_aw=0; got_w=0; staged_count=0; end
            if (dut.done && (ep_bvalid || ep_awvalid || ep_wvalid || ep_rvalid))
                $fatal(1,"FAIL done before response retirement");
        end
    end
    initial begin
        $readmemh("expected.hex",expected);
        fd=$fopen("writes.txt","w");
        repeat(4) @(negedge clk); rst_n=1;

        for(i=0;i<6;i=i+1) camera_writes[i]=0;

        mmio_read(32'ha0,value); if(value!=3) $fatal(1,"FAIL capabilities");
        mmio_read(32'hb0,value); if(value!=0) $fatal(1,"FAIL default RGB mode");
        mmio_read(32'h40,value); if(value!=32'h0a000000) $fatal(1,"FAIL RGB destination");
        mmio_read(32'h60,value); if(value!=W*OH*3) $fatal(1,"FAIL RGB byte count");
        expected_bresp=2; mmio_write(32'hb0,2); // invalid mode
        expected_bresp=0; mmio_write(32'hb0,1);
        mmio_read(32'hb0,value); if(value!=1) $fatal(1,"FAIL thumbnail mode");
        mmio_read(32'h40,value); if(value!=32'h0a200000) $fatal(1,"FAIL thumbnail destination");
        mmio_read(32'h60,value); if(value!=(W/2)*(H/2)*2) $fatal(1,"FAIL thumbnail byte count");
        expected_bresp=2; mmio_write(32'h40,32'h0a000000); // wrong mode destination
        host_wstrb=1; mmio_write(32'hb0,0); host_wstrb=65535; // partial mode write
        expected_bresp=0; mmio_write(32'hb0,0);
        mmio_read(0,value); if(value!=32'h444c5632) $fatal(1,"FAIL signature");
        expected_bresp=2;
        mmio_write(32'h20,2); // reject submission before hold/freeze
        mmio_write(32'h40,32'h0b000000); // no arbitrary destination
        expected_bresp=0; expected_rresp=2;
        mmio_read(32'hc0,value); // exact register decode
        expected_rresp=0;
        mmio_write(32'h20,1);
        expected_bresp=2; mmio_write(32'hb0,1); // mode locked by capture lease
        expected_bresp=0;
        mmio_read(32'hb0,value); if(value!=0) $fatal(1,"FAIL held mode changed");
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze busy camera");
        camera_state=1; camera_cmd=1;
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze queued camera");
        camera_cmd=0;
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze unpublished bank");
        published=1;
        repeat(5) @(negedge clk);
        mmio_read(32'h10,value); if((value&3)!=3) $fatal(1,"FAIL freeze acknowledgment");
        mmio_read(32'h30,value); if(value!=32'h01800000) $fatal(1,"FAIL bank latch");
        for(frame=0;frame<2;frame=frame+1) begin
            read_count=0; write_count=0;
            mmio_write(32'h20,3);
            expected_bresp=2; mmio_write(32'h20,0); expected_bresp=0;
            if(!capture_hold) $fatal(1,"FAIL released a busy source");
            value=0;
            while(!(value&8)) mmio_read(32'h10,value);
            if(value&32'h74 || read_count!=READS || write_count!=WORDS) $fatal(1,"FAIL completion");
            mmio_read(32'h90,value); if(value!=frame+1) $fatal(1,"FAIL job counter");
            repeat(10) @(negedge clk);
        end
        mmio_write(32'h20,0); mmio_read(32'h10,value);
        if(value&7 || capture_hold) $fatal(1,"FAIL release");
        for(i=0;i<6;i=i+1) if(camera_writes[i]<1) $fatal(1,"FAIL camera starvation");
        $fclose(fd); $display("PASS tb_delivery_integration cycles=%0d",cycle); $finish;
    end

    initial begin
        host_awid=0;
        host_awaddr=0;
        host_awlen=0;
        host_awsize=4;
        host_awburst=1;
        host_awlock=0;
        host_awcache=0;
        host_awprot=0;
        host_awqos=0;
        host_awregion=0;
        host_awvalid=0;
        host_wdata=0;
        host_wstrb=65535;
        host_wlast=1;
        host_wvalid=0;
        host_bready=0;
        host_arid=0;
        host_araddr=0;
        host_arlen=0;
        host_arsize=4;
        host_arburst=1;
        host_arlock=0;
        host_arcache=0;
        host_arprot=0;
        host_arqos=0;
        host_arregion=0;
        host_arvalid=0;
        host_rready=0;
    end
endmodule
