`timescale 1ns/1ps
module adapter_boundary #(parameter [63:0] RAW_LIMIT=0, parameter N=1,
                           parameter VECTOR_FILE="vectors.hex") (output reg done=0);
reg clk=0; always #5 clk=~clk;
reg  rst_n=0;
reg [3:0] s_awid=0;
reg [31:0] s_awaddr=0;
reg [7:0] s_awlen=0;
reg [2:0] s_awsize=0;
reg [1:0] s_awburst=0;
reg  s_awvalid=0;
wire  s_awready;
reg [127:0] s_wdata=0;
reg [15:0] s_wstrb=0;
reg  s_wlast=0;
reg  s_wvalid=0;
wire  s_wready;
wire [3:0] s_bid;
wire [1:0] s_bresp;
wire  s_bvalid;
reg  s_bready=0;
reg [6:0] s_arid=0;
reg [31:0] s_araddr=0;
reg [7:0] s_arlen=0;
reg [2:0] s_arsize=0;
reg [1:0] s_arburst=0;
reg  s_arvalid=0;
wire  s_arready;
wire [6:0] s_rid;
wire [127:0] s_rdata;
wire [1:0] s_rresp;
wire  s_rlast;
wire  s_rvalid;
reg  s_rready=0;
wire [3:0] v_awid;
wire [27:0] v_awaddr;
wire [3:0] v_awlen;
wire  v_awvalid;
reg  v_awready=0;
wire [127:0] v_wdata;
wire [15:0] v_wstrb;
reg  v_wready=0;
reg  v_wlast=0;
reg [3:0] v_wid=0;
wire [3:0] v_arid;
wire [27:0] v_araddr;
wire [3:0] v_arlen;
wire  v_arvalid;
reg  v_arready=0;
reg [3:0] v_rid=0;
reg [127:0] v_rdata=0;
reg  v_rlast=0;
reg  v_rvalid=0;
wire [7:0] error_flags;
wire [4:0] write_water_level;
wire  write_fifo_full;
wire  write_fifo_empty;
wire  read_fifo_full;
wire  read_fifo_empty;
wire  write_busy;
wire  read_busy;
fpga_v8_ddr_adapter #(.DDR_ADDRESS_LIMIT(RAW_LIMIT)) reference (
.clk(clk),
.rst_n(rst_n),
.s_awid(s_awid),
.s_awaddr(s_awaddr),
.s_awlen(s_awlen),
.s_awsize(s_awsize),
.s_awburst(s_awburst),
.s_awvalid(s_awvalid),
.s_awready(s_awready),
.s_wdata(s_wdata),
.s_wstrb(s_wstrb),
.s_wlast(s_wlast),
.s_wvalid(s_wvalid),
.s_wready(s_wready),
.s_bid(s_bid),
.s_bresp(s_bresp),
.s_bvalid(s_bvalid),
.s_bready(s_bready),
.s_arid(s_arid),
.s_araddr(s_araddr),
.s_arlen(s_arlen),
.s_arsize(s_arsize),
.s_arburst(s_arburst),
.s_arvalid(s_arvalid),
.s_arready(s_arready),
.s_rid(s_rid),
.s_rdata(s_rdata),
.s_rresp(s_rresp),
.s_rlast(s_rlast),
.s_rvalid(s_rvalid),
.s_rready(s_rready),
.v_awid(v_awid),
.v_awaddr(v_awaddr),
.v_awlen(v_awlen),
.v_awvalid(v_awvalid),
.v_awready(v_awready),
.v_wdata(v_wdata),
.v_wstrb(v_wstrb),
.v_wready(v_wready),
.v_wlast(v_wlast),
.v_wid(v_wid),
.v_arid(v_arid),
.v_araddr(v_araddr),
.v_arlen(v_arlen),
.v_arvalid(v_arvalid),
.v_arready(v_arready),
.v_rid(v_rid),
.v_rdata(v_rdata),
.v_rlast(v_rlast),
.v_rvalid(v_rvalid),
.error_flags(error_flags),
.write_water_level(write_water_level),
.write_fifo_full(write_fifo_full),
.write_fifo_empty(write_fifo_empty),
.read_fifo_full(read_fifo_full),
.read_fifo_empty(read_fifo_empty),
.write_busy(write_busy),
.read_busy(read_busy));
wire  tc03_s_awready;
wire  tc03_s_wready;
wire [3:0] tc03_s_bid;
wire [1:0] tc03_s_bresp;
wire  tc03_s_bvalid;
wire  tc03_s_arready;
wire [6:0] tc03_s_rid;
wire [127:0] tc03_s_rdata;
wire [1:0] tc03_s_rresp;
wire  tc03_s_rlast;
wire  tc03_s_rvalid;
wire [3:0] tc03_v_awid;
wire [27:0] tc03_v_awaddr;
wire [3:0] tc03_v_awlen;
wire  tc03_v_awvalid;
wire [127:0] tc03_v_wdata;
wire [15:0] tc03_v_wstrb;
wire [3:0] tc03_v_arid;
wire [27:0] tc03_v_araddr;
wire [3:0] tc03_v_arlen;
wire  tc03_v_arvalid;
wire [7:0] tc03_error_flags;
wire [4:0] tc03_write_water_level;
wire  tc03_write_fifo_full;
wire  tc03_write_fifo_empty;
wire  tc03_read_fifo_full;
wire  tc03_read_fifo_empty;
wire  tc03_write_busy;
wire  tc03_read_busy;
fpga_v8_ddr_adapter_tc03 #(.DDR_ADDRESS_LIMIT(RAW_LIMIT)) candidate (
.clk(clk),
.rst_n(rst_n),
.s_awid(s_awid),
.s_awaddr(s_awaddr),
.s_awlen(s_awlen),
.s_awsize(s_awsize),
.s_awburst(s_awburst),
.s_awvalid(s_awvalid),
.s_awready(tc03_s_awready),
.s_wdata(s_wdata),
.s_wstrb(s_wstrb),
.s_wlast(s_wlast),
.s_wvalid(s_wvalid),
.s_wready(tc03_s_wready),
.s_bid(tc03_s_bid),
.s_bresp(tc03_s_bresp),
.s_bvalid(tc03_s_bvalid),
.s_bready(s_bready),
.s_arid(s_arid),
.s_araddr(s_araddr),
.s_arlen(s_arlen),
.s_arsize(s_arsize),
.s_arburst(s_arburst),
.s_arvalid(s_arvalid),
.s_arready(tc03_s_arready),
.s_rid(tc03_s_rid),
.s_rdata(tc03_s_rdata),
.s_rresp(tc03_s_rresp),
.s_rlast(tc03_s_rlast),
.s_rvalid(tc03_s_rvalid),
.s_rready(s_rready),
.v_awid(tc03_v_awid),
.v_awaddr(tc03_v_awaddr),
.v_awlen(tc03_v_awlen),
.v_awvalid(tc03_v_awvalid),
.v_awready(v_awready),
.v_wdata(tc03_v_wdata),
.v_wstrb(tc03_v_wstrb),
.v_wready(v_wready),
.v_wlast(v_wlast),
.v_wid(v_wid),
.v_arid(tc03_v_arid),
.v_araddr(tc03_v_araddr),
.v_arlen(tc03_v_arlen),
.v_arvalid(tc03_v_arvalid),
.v_arready(v_arready),
.v_rid(v_rid),
.v_rdata(v_rdata),
.v_rlast(v_rlast),
.v_rvalid(v_rvalid),
.error_flags(tc03_error_flags),
.write_water_level(tc03_write_water_level),
.write_fifo_full(tc03_write_fifo_full),
.write_fifo_empty(tc03_write_fifo_empty),
.read_fifo_full(tc03_read_fifo_full),
.read_fifo_empty(tc03_read_fifo_empty),
.write_busy(tc03_write_busy),
.read_busy(tc03_read_busy));
integer differential_samples=0;
task compare_public; begin
if (s_awready !== tc03_s_awready) $fatal(1,"PUBLIC_OUTPUT_DIFF s_awready time=%0t",$time);
if (s_wready !== tc03_s_wready) $fatal(1,"PUBLIC_OUTPUT_DIFF s_wready time=%0t",$time);
if (s_bid !== tc03_s_bid) $fatal(1,"PUBLIC_OUTPUT_DIFF s_bid time=%0t",$time);
if (s_bresp !== tc03_s_bresp) $fatal(1,"PUBLIC_OUTPUT_DIFF s_bresp time=%0t",$time);
if (s_bvalid !== tc03_s_bvalid) $fatal(1,"PUBLIC_OUTPUT_DIFF s_bvalid time=%0t",$time);
if (s_arready !== tc03_s_arready) $fatal(1,"PUBLIC_OUTPUT_DIFF s_arready time=%0t",$time);
if (s_rid !== tc03_s_rid) $fatal(1,"PUBLIC_OUTPUT_DIFF s_rid time=%0t",$time);
if (s_rdata !== tc03_s_rdata) $fatal(1,"PUBLIC_OUTPUT_DIFF s_rdata time=%0t",$time);
if (s_rresp !== tc03_s_rresp) $fatal(1,"PUBLIC_OUTPUT_DIFF s_rresp time=%0t",$time);
if (s_rlast !== tc03_s_rlast) $fatal(1,"PUBLIC_OUTPUT_DIFF s_rlast time=%0t",$time);
if (s_rvalid !== tc03_s_rvalid) $fatal(1,"PUBLIC_OUTPUT_DIFF s_rvalid time=%0t",$time);
if (v_awid !== tc03_v_awid) $fatal(1,"PUBLIC_OUTPUT_DIFF v_awid time=%0t",$time);
if (v_awaddr !== tc03_v_awaddr) $fatal(1,"PUBLIC_OUTPUT_DIFF v_awaddr time=%0t",$time);
if (v_awlen !== tc03_v_awlen) $fatal(1,"PUBLIC_OUTPUT_DIFF v_awlen time=%0t",$time);
if (v_awvalid !== tc03_v_awvalid) $fatal(1,"PUBLIC_OUTPUT_DIFF v_awvalid time=%0t",$time);
if (v_wdata !== tc03_v_wdata) $fatal(1,"PUBLIC_OUTPUT_DIFF v_wdata time=%0t",$time);
if (v_wstrb !== tc03_v_wstrb) $fatal(1,"PUBLIC_OUTPUT_DIFF v_wstrb time=%0t",$time);
if (v_arid !== tc03_v_arid) $fatal(1,"PUBLIC_OUTPUT_DIFF v_arid time=%0t",$time);
if (v_araddr !== tc03_v_araddr) $fatal(1,"PUBLIC_OUTPUT_DIFF v_araddr time=%0t",$time);
if (v_arlen !== tc03_v_arlen) $fatal(1,"PUBLIC_OUTPUT_DIFF v_arlen time=%0t",$time);
if (v_arvalid !== tc03_v_arvalid) $fatal(1,"PUBLIC_OUTPUT_DIFF v_arvalid time=%0t",$time);
if (error_flags !== tc03_error_flags) $fatal(1,"PUBLIC_OUTPUT_DIFF error_flags time=%0t",$time);
if (write_water_level !== tc03_write_water_level) $fatal(1,"PUBLIC_OUTPUT_DIFF write_water_level time=%0t",$time);
if (write_fifo_full !== tc03_write_fifo_full) $fatal(1,"PUBLIC_OUTPUT_DIFF write_fifo_full time=%0t",$time);
if (write_fifo_empty !== tc03_write_fifo_empty) $fatal(1,"PUBLIC_OUTPUT_DIFF write_fifo_empty time=%0t",$time);
if (read_fifo_full !== tc03_read_fifo_full) $fatal(1,"PUBLIC_OUTPUT_DIFF read_fifo_full time=%0t",$time);
if (read_fifo_empty !== tc03_read_fifo_empty) $fatal(1,"PUBLIC_OUTPUT_DIFF read_fifo_empty time=%0t",$time);
if (write_busy !== tc03_write_busy) $fatal(1,"PUBLIC_OUTPUT_DIFF write_busy time=%0t",$time);
if (read_busy !== tc03_read_busy) $fatal(1,"PUBLIC_OUTPUT_DIFF read_busy time=%0t",$time);
differential_samples=differential_samples+1; end endtask
always @(posedge clk) begin compare_public(); #1; compare_public(); end
always @(negedge clk) begin #1; compare_public(); end

reg [45:0] vectors [0:N-1];
reg expected;
integer k, legal_count=0, rejected_count=0;
initial begin
  $readmemh(VECTOR_FILE,vectors);
  repeat(5) @(negedge clk); rst_n=1; repeat(3) @(negedge clk);
  for(k=0;k<N;k=k+1) begin
    {s_awaddr,s_awlen,s_awsize,s_awburst,expected}=vectors[k];
    {s_araddr,s_arlen,s_arsize,s_arburst}=vectors[k][45:1];
    // Illegal VALID requests must stay unaccepted and flag both directions.
    // Legal requests remain combinational probes here; transactions run separately.
    s_awvalid=!expected; s_arvalid=!expected;
    #1; compare_public();
    if(s_awready!==expected || s_arready!==expected)
      $fatal(1,"ORACLE_DIFF limit=%h index=%0d addr=%h len=%0d",RAW_LIMIT,k,s_awaddr,s_awlen);
    @(posedge clk); #2;
    if(!expected && (error_flags[1:0]!==2'b11 || v_awvalid || v_arvalid || write_busy || read_busy))
      $fatal(1,"INVALID_ACCEPTED_OR_UNFLAGGED limit=%h index=%0d",RAW_LIMIT,k);
    if(expected) legal_count=legal_count+1; else rejected_count=rejected_count+1;
    @(negedge clk);
  end
  s_awvalid=0; s_arvalid=0;
  $display("BOUNDARY_PASS raw_limit=%h effective_limit=%h vectors=%0d legal=%0d rejected=%0d public_samples=%0d",
           RAW_LIMIT,RAW_LIMIT[31:0],N,legal_count,rejected_count,differential_samples);
  done=1;
end
endmodule

module tb_adapter_boundary;
wire done_0; adapter_boundary #(.RAW_LIMIT(64'h0000000010000000), .N(78928), .VECTOR_FILE("boundary_0.hex")) b0(done_0);
wire done_1; adapter_boundary #(.RAW_LIMIT(64'h0000000000001000), .N(13392), .VECTOR_FILE("boundary_1.hex")) b1(done_1);
wire done_2; adapter_boundary #(.RAW_LIMIT(64'h0000000000100010), .N(13392), .VECTOR_FILE("boundary_2.hex")) b2(done_2);
wire done_3; adapter_boundary #(.RAW_LIMIT(64'h0000000000100ff0), .N(13392), .VECTOR_FILE("boundary_3.hex")) b3(done_3);
wire done_4; adapter_boundary #(.RAW_LIMIT(64'h0000000000000010), .N(13392), .VECTOR_FILE("boundary_4.hex")) b4(done_4);
wire done_5; adapter_boundary #(.RAW_LIMIT(64'h0000000000000ff0), .N(13392), .VECTOR_FILE("boundary_5.hex")) b5(done_5);
wire done_6; adapter_boundary #(.RAW_LIMIT(64'h0000000000000000), .N(13392), .VECTOR_FILE("boundary_6.hex")) b6(done_6);
wire done_7; adapter_boundary #(.RAW_LIMIT(64'h0000000000000001), .N(13392), .VECTOR_FILE("boundary_7.hex")) b7(done_7);
wire done_8; adapter_boundary #(.RAW_LIMIT(64'h0000000000100001), .N(13392), .VECTOR_FILE("boundary_8.hex")) b8(done_8);
wire done_9; adapter_boundary #(.RAW_LIMIT(64'h0000000010001000), .N(13392), .VECTOR_FILE("boundary_9.hex")) b9(done_9);
wire done_10; adapter_boundary #(.RAW_LIMIT(64'h00000000fffffff0), .N(13392), .VECTOR_FILE("boundary_10.hex")) b10(done_10);
wire done_11; adapter_boundary #(.RAW_LIMIT(64'h00000000ffffffff), .N(13392), .VECTOR_FILE("boundary_11.hex")) b11(done_11);
wire done_12; adapter_boundary #(.RAW_LIMIT(64'h0000000110000000), .N(13392), .VECTOR_FILE("boundary_12.hex")) b12(done_12);
wire done_13; adapter_boundary #(.RAW_LIMIT(64'h0000000100000000), .N(13392), .VECTOR_FILE("boundary_13.hex")) b13(done_13);
wire done_14; adapter_boundary #(.RAW_LIMIT(64'h0000000100000010), .N(13392), .VECTOR_FILE("boundary_14.hex")) b14(done_14);
initial begin wait(done_0 && done_1 && done_2 && done_3 && done_4 && done_5 && done_6 && done_7 && done_8 && done_9 && done_10 && done_11 && done_12 && done_13 && done_14); $display("ALL_BOUNDARY_PASS"); $finish; end
initial begin #2000000; $fatal(1,"boundary watchdog"); end
endmodule
