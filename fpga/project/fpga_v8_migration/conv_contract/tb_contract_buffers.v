`timescale 1ns/1ps
module tb_contract_buffers;
  reg clk=0,rst=1;
  always #5 clk=~clk;
  reg [127:0] input_words[0:11];
  reg [127:0] sd=0;
  reg sv=0,sl=0,req=0;
  wire ready,ready11,mv,ml,mv11,ml11;
  wire [127:0] md,md11;
  conv_in_buf #(.DATA_DEPTH(32)) dut(.clk(clk),.rst(rst),.read_num(6'd12),
    .s_data(sd),.s_valid(sv),.s_last(sl),.s_ready(ready),.m_req(req),.m_data(md),.m_valid(mv),.m_last(ml));
  conv11_in_buf #(.DATA_DEPTH(32)) dut11(.clk(clk),.rst(rst),.read_num(6'd12),
    .s_data(sd),.s_valid(sv),.s_last(sl),.s_ready(ready11),.m_req(req),.m_data(md11),.m_valid(mv11),.m_last(ml11));
  integer fd,cyc=0,b;
  always @(negedge clk) begin
    cyc=cyc+1;
    if(!rst && (mv!==1'b0 || ml!==1'b0)) $fdisplay(fd,"B %0d %b %b %032h",cyc,mv,ml,md);
    if(!rst && (mv11!==1'b0 || ml11!==1'b0)) $fdisplay(fd,"J %0d %b %b %032h",cyc,mv11,ml11,md11);
  end
  initial begin
    fd=$fopen("buffers_observed.txt","w");$readmemh("input_words.mem",input_words);
    repeat(12) @(negedge clk);rst=0;
    for(b=0;b<12;b=b+1) begin
      while(ready!==1'b1 || ready11!==1'b1) @(negedge clk);
      sd=input_words[b];sv=1;sl=(b==11);@(negedge clk);
      sv=0;sl=0;repeat(2) @(negedge clk);
    end
    repeat(8) @(negedge clk);req=1;@(negedge clk);req=0;
    repeat(40) @(negedge clk);$fclose(fd);$display("CONTRACT_BUFFERS_DONE");$finish;
  end
  initial begin #100000;$display("CONTRACT_TIMEOUT");$finish;end
endmodule
