`timescale 1ns/1ps
module sccb_monitor #(parameter N=357, parameter CAMERA=1)(
 input rstn, enable, scl, sda, done, tr_end, ack,
 input [8:0] index, input [5:0] cycle,
 output reg all_done=0);
 reg [31:0] golden[0:356];
 reg [31:0] word_seen=0;
 reg transaction=0;
 integer starts=0, stops=0, completed=0, ack_bits=0, bits=0, runs=0;
 initial $readmemh("baseline_commands.mem",golden);
 always @(negedge rstn) begin
   starts=0; stops=0; completed=0; ack_bits=0; bits=0;
   transaction=0; all_done=0;
 end
 always @(negedge sda) if(rstn && scl===1 && cycle==2) begin
   if(!enable || transaction || starts>=N || index!==9'(starts))
     $fatal(1,"camera %0d START/enable/index",CAMERA);
   transaction=1; bits=0; word_seen=0; starts=starts+1;
 end
 always @(posedge scl) if(rstn && transaction && cycle>=4 && cycle<=39) begin
   if(cycle==12 || cycle==21 || cycle==30 || cycle==39) begin
     if(sda!==0) $fatal(1,"ACK not low");
     ack_bits=ack_bits+1;
   end else begin
     if($isunknown(sda)) $fatal(1,"unknown bus bit");
     word_seen={word_seen[30:0],sda}; bits=bits+1;
   end
 end
 always @(posedge sda) if(rstn && scl===1 && transaction && cycle==42) begin
   if(bits!=32) $fatal(1,"wrong payload bit count");
   if(stops<357) begin
     if(word_seen!==golden[stops])
       $fatal(1,"camera %0d command %0d expected=%h actual=%h",CAMERA,stops,golden[stops],word_seen);
   end else if(word_seen!==32'h78503d80) $fatal(1,"missing sensor colorbar write");
   transaction=0; stops=stops+1;
 end
 always @(posedge tr_end) if(rstn) begin
   #1;
   if(transaction || stops!=completed+1 || ack!==0) $fatal(1,"completion/ACK error");
   completed=completed+1;
 end
 always @(posedge done) begin
   #1;
   if(index!==9'(N) || starts!=N || stops!=N || completed!=N || ack_bits!=4*N)
     $fatal(1,"camera %0d incorrect totals",CAMERA);
   runs=runs+1;
   $display("SCCB PASS camera=%0d run=%0d commands=%0d START=%0d STOP=%0d completions=%0d ACK=%0d",CAMERA,runs,N,starts,stops,completed,ack_bits);
   all_done=1;
 end
 always @(negedge sda) if(rstn && done && scl===1) $fatal(1,"START after done");
endmodule

module tb_sensor_colorbar #(parameter COLOR_BAR_TEST=0);
 reg clk_25M=0, cfg_run=1, sys_clk=0, rstn=0;
 always #20 if(cfg_run) clk_25M=~clk_25M;
 always #10 sys_clk=~sys_clk;
 wire cmos1_reset,cmos2_reset,pwnd,initial_en;
 power_on_delay power_delay(sys_clk,rstn,cmos1_reset,cmos2_reset,pwnd,initial_en);
 wire cfg1_scl,cfg2_scl;
 tri1 cmos1_sda,cmos2_sda;
 wire [1:0] cmos_init_done_int;
 `include "actual_sensor_instances.vh"
 wire ack1=(coms1_reg_config.u1.cyc_count==12 || coms1_reg_config.u1.cyc_count==21 ||
            coms1_reg_config.u1.cyc_count==30 || coms1_reg_config.u1.cyc_count==39);
 wire ack2=(coms2_reg_config.u1.cyc_count==12 || coms2_reg_config.u1.cyc_count==21 ||
            coms2_reg_config.u1.cyc_count==30 || coms2_reg_config.u1.cyc_count==39);
 assign cmos1_sda=cmos1_reset && ack1 ? 1'b0 : 1'bz;
 assign cmos2_sda=cmos2_reset && ack2 ? 1'b0 : 1'bz;
 wire done1,done2;
 sccb_monitor #(.N(COLOR_BAR_TEST ? 358 : 357),.CAMERA(1)) m1(
  cmos1_reset,initial_en,cfg1_scl,cmos1_sda,cmos_init_done_int[0],
  coms1_reg_config.tr_end,coms1_reg_config.ack,coms1_reg_config.reg_index,
  coms1_reg_config.u1.cyc_count,done1);
 sccb_monitor #(.N(COLOR_BAR_TEST ? 358 : 357),.CAMERA(2)) m2(
  cmos2_reset,initial_en,cfg2_scl,cmos2_sda,cmos_init_done_int[1],
  coms2_reg_config.tr_end,coms2_reg_config.ack,coms2_reg_config.reg_index,
  coms2_reg_config.u1.cyc_count,done2);
 task check_reset;
 begin
  #1;
  if(cmos_init_done_int!==0 || coms1_reg_config.reg_index!==0 || coms2_reg_config.reg_index!==0 ||
     coms1_reg_config.clock_20k!==0 || coms2_reg_config.clock_20k!==0 ||
     coms1_reg_config.start!==0 || coms2_reg_config.start!==0 ||
     coms1_reg_config.config_step!==0 || coms2_reg_config.config_step!==0 ||
     coms1_reg_config.clock_20k_cnt!==0 || coms2_reg_config.clock_20k_cnt!==0 ||
     coms1_reg_config.u1.cyc_count!==63 || coms2_reg_config.u1.cyc_count!==63 ||
     coms1_reg_config.u1.tr_end!==0 || coms2_reg_config.u1.tr_end!==0 ||
     {cfg1_scl,cfg2_scl,cmos1_sda,cmos2_sda}!==4'b1111)
    $fatal(1,"both sensors stopped-clock reset failed");
 end
 endtask
 always @(posedge coms1_reg_config.clock_20k) if(cmos1_reset && !initial_en) begin
   #1;
   if(coms1_reg_config.start!==0 || coms2_reg_config.start!==0 ||
      cmos_init_done_int!==0 || coms1_reg_config.reg_index!==0 || coms2_reg_config.reg_index!==0)
     $fatal(1,"sensor command before initial enable");
 end
 integer round;
 initial begin
  repeat(4) @(posedge sys_clk); check_reset;
  for(round=0;round<2;round=round+1) begin
   @(negedge sys_clk); rstn=1;
   wait(done1 && done2);
   repeat(5) @(posedge coms1_reg_config.clock_20k);
   @(negedge clk_25M); cfg_run=0;
   @(negedge sys_clk); rstn=0;
   @(negedge cmos1_reset); check_reset;
   #1000; check_reset;
   cfg_run=1;
  end
  $display("TEST PASS mode=%0d: both actual top sensor instances, two complete bus-verified rounds, stopped-clock reset",COLOR_BAR_TEST);
  $finish;
 end
 initial begin #(64'd4000000000); $fatal(1,"timeout"); end
endmodule
