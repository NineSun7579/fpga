`timescale 1ns/1ps
// Isolated accumulation/bias stage; no connection to MAC or new finish RTL.
module tb_contract_add;
  reg clk=0,rst=1,start=0;
  always #5 clk=~clk;
  reg [63:0] bm[0:7];
  reg [47:0] dm[0:255];
  reg [63:0] bias=0;
  reg bv=0,bl=0,first=0,last=0,sv=0,sl=0;
  reg [47:0] sd=0;
  wire [15:0] md,mj;
  wire mv,ml,jv,jl,done,jdone;
  conv_add #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.MAX_OUT_COL(32),.CHA_IMG_IN(32)) dut(
    .clk(clk),.rst(rst),.start(start),.stride(1'b0),.en_relu(1'b0),.scale_3(16'd256),.zero_3(8'd128),
    .calculate_first(first),.calculate_last(last),.bias(bias),.bias_valid(bv),.bias_last(bl),
    .s_data(sd),.s_valid(sv),.s_last(sl),.m_data(md),.m_valid(mv),.m_last(ml),.add_last(done));
  conv11_add #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.MAX_OUT_COL(32),.CHA_IMG_IN(32)) dut11(
    .clk(clk),.rst(rst),.start(start),.en_relu(1'b0),.scale_3(16'd256),.zero_3(8'd128),
    .calculate_first(first),.calculate_last(last),.bias(bias),.bias_valid(bv),.bias_last(bl),
    .s_data(sd),.s_valid(sv),.s_last(sl),.m_data(mj),.m_valid(jv),.m_last(jl),.add_last(jdone));
  integer fd,cyc=0,g,blockid,i;
  always @(negedge clk) begin
    cyc=cyc+1;
    if(!rst && (mv!==1'b0 || ml!==1'b0)) $fdisplay(fd,"A %0d %b %b %04h",cyc,mv,ml,md);
    if(!rst && (jv!==1'b0 || jl!==1'b0)) $fdisplay(fd,"J %0d %b %b %04h",cyc,jv,jl,mj);
  end
  task load_bias(input integer groupid);
    begin @(negedge clk);bias=bm[groupid];bv=1;bl=1;@(negedge clk);bv=0;bl=0;end
  endtask
  task partial_row(input integer groupid,input integer part);
    integer x;
    begin
      @(negedge clk);
      for(x=0;x<16;x=x+1) begin
        sd=dm[(groupid*2+part)*16+x];sv=1;sl=(x==15);first=(part==0);last=(part==1);
        @(negedge clk);
      end
      sd=0;sv=0;sl=0;first=0;last=0;
      repeat(24) @(negedge clk);
    end
  endtask
  initial begin
    fd=$fopen("add_observed.txt","w");$readmemh("bias_pairs.mem",bm);$readmemh("partial_rows.mem",dm);
    repeat(12) @(negedge clk);rst=0;
    @(negedge clk);start=1;@(negedge clk);start=0;
    load_bias(0);load_bias(1);
    for(g=0;g<8;g=g+1) begin
      partial_row(g,0);partial_row(g,1);
      if(g+2<8) load_bias(g+2);
    end
    repeat(24) @(negedge clk);$fclose(fd);$display("CONTRACT_ADD_DONE");$finish;
  end
endmodule
