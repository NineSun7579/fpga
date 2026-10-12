`timescale 1ns/1ps
module tb_decode;
parameter [31:0] BASE=32'h100;
reg clk=0; always #5 clk=~clk;
reg  rst_n=0;
reg  config_ready=0;
reg  config_accept=0;
reg  config_reject=0;
reg  epoch_start=0;
reg  armed=0;
reg  config_ok=0;
reg  protocol_fault=0;
reg [1:0] bank0_state=0;
reg [1:0] bank1_state=0;
reg  host_valid=0;
reg [31:0] host_src_addr=0;
reg [31:0] host_length=0;
reg [31:0] host_seq=0;
reg [31:0] host_generation=0;
reg [2:0] host_camera=0;
reg  host_bank=0;
reg [63:0] host_token=0;
reg  host_release_ready=0;
reg  host_release_accept=0;
reg  host_release_reject=0;
reg [31:0] published_count=0;
reg [31:0] failed_count=0;
reg [31:0] rejected_release_count=0;
reg [31:0] s_axil_awaddr=0;
reg [2:0] s_axil_awprot=0;
reg  s_axil_awvalid=0;
reg [31:0] s_axil_wdata=0;
reg [3:0] s_axil_wstrb=0;
reg  s_axil_wvalid=0;
reg  s_axil_bready=0;
reg [31:0] s_axil_araddr=0;
reg [2:0] s_axil_arprot=0;
reg  s_axil_arvalid=0;
reg  s_axil_rready=0;
fpga_v8_capture_control_axil_arm_v2_golden #(.LOCAL_BASE(BASE)) gold(.clk(clk),.rst_n(rst_n),.config_ready(config_ready),.config_accept(config_accept),.config_reject(config_reject),.epoch_start(epoch_start),.armed(armed),.config_ok(config_ok),.protocol_fault(protocol_fault),.bank0_state(bank0_state),.bank1_state(bank1_state),.host_valid(host_valid),.host_src_addr(host_src_addr),.host_length(host_length),.host_seq(host_seq),.host_generation(host_generation),.host_camera(host_camera),.host_bank(host_bank),.host_token(host_token),.host_release_ready(host_release_ready),.host_release_accept(host_release_accept),.host_release_reject(host_release_reject),.published_count(published_count),.failed_count(failed_count),.rejected_release_count(rejected_release_count),.s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_bready(s_axil_bready),.s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_rready(s_axil_rready));
fpga_v8_capture_control_axil_arm_v2 #(.LOCAL_BASE(BASE)) cand(.clk(clk),.rst_n(rst_n),.config_ready(config_ready),.config_accept(config_accept),.config_reject(config_reject),.epoch_start(epoch_start),.armed(armed),.config_ok(config_ok),.protocol_fault(protocol_fault),.bank0_state(bank0_state),.bank1_state(bank1_state),.host_valid(host_valid),.host_src_addr(host_src_addr),.host_length(host_length),.host_seq(host_seq),.host_generation(host_generation),.host_camera(host_camera),.host_bank(host_bank),.host_token(host_token),.host_release_ready(host_release_ready),.host_release_accept(host_release_accept),.host_release_reject(host_release_reject),.published_count(published_count),.failed_count(failed_count),.rejected_release_count(rejected_release_count),.s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_bready(s_axil_bready),.s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_rready(s_axil_rready));
integer cycles=0,arms=0,rels=0,claims=0,armwait=0,relwait=0,bothcfg=0,bothrel=0;
integer seed=1,i,j,order,strb,offset;
reg [31:0] value, address;
task check; begin if(gold.config_valid !== cand.config_valid) $fatal(1,"mismatch config_valid t=%0t",$time);
if(gold.config_generation !== cand.config_generation) $fatal(1,"mismatch config_generation t=%0t",$time);
if(gold.host_ready !== cand.host_ready) $fatal(1,"mismatch host_ready t=%0t",$time);
if(gold.host_release_valid !== cand.host_release_valid) $fatal(1,"mismatch host_release_valid t=%0t",$time);
if(gold.host_release_camera !== cand.host_release_camera) $fatal(1,"mismatch host_release_camera t=%0t",$time);
if(gold.host_release_bank !== cand.host_release_bank) $fatal(1,"mismatch host_release_bank t=%0t",$time);
if(gold.host_release_seq !== cand.host_release_seq) $fatal(1,"mismatch host_release_seq t=%0t",$time);
if(gold.host_release_generation !== cand.host_release_generation) $fatal(1,"mismatch host_release_generation t=%0t",$time);
if(gold.host_release_token !== cand.host_release_token) $fatal(1,"mismatch host_release_token t=%0t",$time);
if(gold.s_axil_awready !== cand.s_axil_awready) $fatal(1,"mismatch s_axil_awready t=%0t",$time);
if(gold.s_axil_wready !== cand.s_axil_wready) $fatal(1,"mismatch s_axil_wready t=%0t",$time);
if(gold.s_axil_bresp !== cand.s_axil_bresp) $fatal(1,"mismatch s_axil_bresp t=%0t",$time);
if(gold.s_axil_bvalid !== cand.s_axil_bvalid) $fatal(1,"mismatch s_axil_bvalid t=%0t",$time);
if(gold.s_axil_arready !== cand.s_axil_arready) $fatal(1,"mismatch s_axil_arready t=%0t",$time);
if(gold.s_axil_rdata !== cand.s_axil_rdata) $fatal(1,"mismatch s_axil_rdata t=%0t",$time);
if(gold.s_axil_rresp !== cand.s_axil_rresp) $fatal(1,"mismatch s_axil_rresp t=%0t",$time);
if(gold.s_axil_rvalid !== cand.s_axil_rvalid) $fatal(1,"mismatch s_axil_rvalid t=%0t",$time);
if(gold.aw_held !== cand.aw_held) $fatal(1,"mismatch aw_held t=%0t",$time);
if(gold.w_held !== cand.w_held) $fatal(1,"mismatch w_held t=%0t",$time);
if(gold.aw_addr !== cand.aw_addr) $fatal(1,"mismatch aw_addr t=%0t",$time);
if(gold.w_data !== cand.w_data) $fatal(1,"mismatch w_data t=%0t",$time);
if(gold.w_strb !== cand.w_strb) $fatal(1,"mismatch w_strb t=%0t",$time);
if(gold.pending !== cand.pending) $fatal(1,"mismatch pending t=%0t",$time);
if(gold.staged_generation !== cand.staged_generation) $fatal(1,"mismatch staged_generation t=%0t",$time);
if(gold.accepted_generation !== cand.accepted_generation) $fatal(1,"mismatch accepted_generation t=%0t",$time);
if(gold.host_bound !== cand.host_bound) $fatal(1,"mismatch host_bound t=%0t",$time);
if(gold.bound_bank !== cand.bound_bank) $fatal(1,"mismatch bound_bank t=%0t",$time);
if(gold.bound_seq !== cand.bound_seq) $fatal(1,"mismatch bound_seq t=%0t",$time);
if(gold.bound_generation !== cand.bound_generation) $fatal(1,"mismatch bound_generation t=%0t",$time);
if(gold.bound_length !== cand.bound_length) $fatal(1,"mismatch bound_length t=%0t",$time);
if(gold.bound_addr !== cand.bound_addr) $fatal(1,"mismatch bound_addr t=%0t",$time);
if(gold.bound_camera !== cand.bound_camera) $fatal(1,"mismatch bound_camera t=%0t",$time);
if(gold.bound_token !== cand.bound_token) $fatal(1,"mismatch bound_token t=%0t",$time);
if(gold.ack_bank !== cand.ack_bank) $fatal(1,"mismatch ack_bank t=%0t",$time);
if(gold.ack_seq !== cand.ack_seq) $fatal(1,"mismatch ack_seq t=%0t",$time);
if(gold.ack_generation !== cand.ack_generation) $fatal(1,"mismatch ack_generation t=%0t",$time);
if(gold.ack_token_low !== cand.ack_token_low) $fatal(1,"mismatch ack_token_low t=%0t",$time);
if(gold.ack_token_high !== cand.ack_token_high) $fatal(1,"mismatch ack_token_high t=%0t",$time);
if(gold.ack_camera !== cand.ack_camera) $fatal(1,"mismatch ack_camera t=%0t",$time);
if(gold.rejected_claims !== cand.rejected_claims) $fatal(1,"mismatch rejected_claims t=%0t",$time);
if(gold.bad_acks !== cand.bad_acks) $fatal(1,"mismatch bad_acks t=%0t",$time);
if(gold.rejected_configs !== cand.rejected_configs) $fatal(1,"mismatch rejected_configs t=%0t",$time);
if(gold.accepted_configs !== cand.accepted_configs) $fatal(1,"mismatch accepted_configs t=%0t",$time);
if(gold.accepted_claims !== cand.accepted_claims) $fatal(1,"mismatch accepted_claims t=%0t",$time);
if(gold.accepted_releases !== cand.accepted_releases) $fatal(1,"mismatch accepted_releases t=%0t",$time);
if(gold.commit !== cand.commit) $fatal(1,"mismatch commit t=%0t",$time);
if(gold.wr_in_range !== cand.wr_in_range) $fatal(1,"mismatch wr_in_range t=%0t",$time);
if(gold.doorbell !== cand.doorbell) $fatal(1,"mismatch doorbell t=%0t",$time);
if(gold.key_match !== cand.key_match) $fatal(1,"mismatch key_match t=%0t",$time); end endtask
always @(posedge clk) begin
 check(); cycles=cycles+1;
 if(gold.config_valid) arms=arms+1;
 if(gold.host_ready) claims=claims+1;
 if(gold.host_release_valid) rels=rels+1;
 if(gold.pending==1) armwait=armwait+1;
 if(gold.pending==2) relwait=relwait+1;
 if(gold.pending==1 && config_accept && config_reject) bothcfg=bothcfg+1;
 if(gold.pending==2 && host_release_accept && host_release_reject) bothrel=bothrel+1;
 #1;check();
end
always @(negedge clk) begin #1;check(); end
task tick; input integer n; integer t; begin for(t=0;t<n;t=t+1) @(negedge clk); end endtask
task reset; begin rst_n=0; tick(2);rst_n=1;tick(2); end endtask
task write; input [31:0] addr,data; input [3:0] mask; input integer ord; begin
 s_axil_awaddr=addr;s_axil_wdata=data;s_axil_wstrb=mask;
 if(ord==0) begin s_axil_awvalid=1;s_axil_wvalid=1;tick(1);s_axil_awvalid=0;s_axil_wvalid=0;end
 if(ord==1) begin s_axil_awvalid=1;tick(1);s_axil_awvalid=0;tick(3);s_axil_wvalid=1;tick(1);s_axil_wvalid=0;end
 if(ord==2) begin s_axil_wvalid=1;tick(1);s_axil_wvalid=0;tick(3);s_axil_awvalid=1;tick(1);s_axil_awvalid=0;end
 tick(2);
end endtask
task drain; begin
 if(gold.pending==1) begin tick(4);config_accept=1;tick(1);config_accept=0;end
 if(gold.pending==2) begin tick(4);host_release_accept=1;tick(1);host_release_accept=0;end
 tick(2);
end endtask
task bind_ack; begin
 write(BASE+32'h14,{31'd0,host_bank},15,1);
 write(BASE+32'h38,{31'd0,host_bank},15,2);
 write(BASE+32'h3c,host_seq,15,0);
 write(BASE+32'h40,host_generation,15,1);
 write(BASE+32'h44,host_token[31:0],15,2);
 write(BASE+32'h48,host_token[63:32],15,0);
 write(BASE+32'h4c,{29'd0,host_camera},15,1);
end endtask
initial begin
 if(!$value$plusargs("SEED=%d",seed)) seed=1;
 tick(1);reset();s_axil_bready=1;s_axil_rready=1;
 config_ready=1;host_valid=1;host_release_ready=1;host_bank=1;host_seq=32'h87654321;
 host_generation=32'hffffffff;host_camera=7;host_token=64'hfedcba9876543210;
 host_length=32'hfffffff0;host_src_addr=32'hfffffff0;
 // All 16 byte masks, both AW/W orderings, every aligned register and illegal boundary byte.
 for(i=0;i<16;i=i+1) begin
  for(j=-4;j<132;j=j+1) begin
   s_axil_araddr=BASE+j;s_axil_arvalid=1;
   write(BASE+j,32'h12345679,i,i%3);drain();
  end
 end
 s_axil_arvalid=0;reset();
 // ARM dispatch with SOF/status and response on the same edge, then delayed contradictory ack.
 config_accept=1;config_reject=1;epoch_start=1;
 write(BASE+32'h10,1,1,0);
 config_accept=0;config_reject=0;tick(5);
 config_accept=1;config_reject=1;tick(1);config_accept=0;config_reject=0;tick(3);
 bind_ack();
 // Release dispatch concurrent with SOF/config response; registered reject wins over accept.
 host_release_accept=1;host_release_reject=1;config_accept=1;epoch_start=1;
 write(BASE+32'h50,1,1,2);
 host_release_accept=0;host_release_reject=0;config_accept=0;tick(5);
 host_release_accept=1;host_release_reject=1;tick(1);host_release_accept=0;host_release_reject=0;tick(3);
 write(BASE+32'h50,1,1,1);drain();
 // Reset aborts ARM_WAIT, RELEASE_WAIT and independently held AW/W and blocked B/R.
 write(BASE+32'h10,1,1,0);reset();
 bind_ack();write(BASE+32'h50,1,1,0);reset();
 s_axil_awvalid=1;tick(1);s_axil_awvalid=0;reset();
 s_axil_wvalid=1;tick(1);s_axil_wvalid=0;reset();
 s_axil_bready=0;s_axil_rready=0;s_axil_arvalid=1;s_axil_araddr=BASE;
 write(BASE+32'h0c,32'hdeadbeef,15,0);reset();
 s_axil_bready=1;s_axil_rready=1;s_axil_arvalid=0;
 // Reproducible directed random traffic: full-address aliases, backpressure and asynchronous reset.
 for(i=0;i<4000;i=i+1) begin
  value=$random(seed);offset=($random(seed)&255)-64;
  case(i%7)
   0: address=BASE+offset;
   1: address=$random(seed);
   2: address=32'hffffffff;
   3: address=0;
   default: address=BASE+((value&31)*4);
  endcase
  config_ready=value[0];host_release_ready=value[1];host_valid=value[2];
  epoch_start=value[3];armed=value[4];config_ok=value[5];protocol_fault=value[6];
  bank0_state=value[8:7];bank1_state=value[10:9];published_count=value;failed_count=~value;
  rejected_release_count=$random(seed);s_axil_awprot=value[13:11];s_axil_arprot=value[16:14];
  s_axil_araddr=address;s_axil_arvalid=1;s_axil_rready=value[17];
  write(address,value,value[21:18],i%3);s_axil_rready=1;drain();
  if(i%17==0) begin #2;rst_n=0;#1;check();tick(1);rst_n=1;tick(2);end
 end
 if(BASE[1:0]==0 && BASE<=32'hffffff80 && (!arms || !rels || !claims || !armwait || !relwait || !bothcfg || !bothrel))
  $fatal(1,"missing directed coverage arms=%d rels=%d claims=%d both=%d/%d",arms,rels,claims,bothcfg,bothrel);
 $display("DECODE_MITER_PASS base=%h cycles=%0d arms=%0d releases=%0d claims=%0d ARM_WAIT=%0d RELEASE_WAIT=%0d bothcfg=%0d bothrel=%0d",BASE,cycles,arms,rels,claims,armwait,relwait,bothcfg,bothrel);$finish;
end
initial begin #20000000;$fatal(1,"watchdog");end
endmodule
