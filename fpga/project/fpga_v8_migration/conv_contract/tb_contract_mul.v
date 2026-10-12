`timescale 1ns/1ps
module tb_contract_mul;
  reg clk=0;
  always #5 clk=~clk;
  GTP_GRS GRS_INST(.GRS_N(1'b1));
  reg [7:0] a=0,b=0,c=0;
  wire [15:0] ac,bc,ac11,bc11;
  conv_mul_E2 dut(.clk(clk),.a(a),.b(b),.c(c),.a_c(ac),.b_c(bc));
  conv11_mul_E2 dut11(.clk(clk),.a(a),.b(b),.c(c),.a_c(ac11),.b_c(bc11));
  integer fd,i,cyc=0,stim=-1;
  always @(posedge clk) begin
    cyc=cyc+1;
    #1;
    $fdisplay(fd,"%0d %0d %04h %04h %04h %04h",cyc,stim,ac,bc,ac11,bc11);
  end
  initial begin
    fd=$fopen("mul_observed.txt","w");
    repeat(12) @(negedge clk);
    for(i=0;i<65536;i=i+1) begin
      a=i/256;b=~a;c=i%256;stim=i;
      @(negedge clk);
    end
    a=0;b=0;c=0;stim=-1;
    repeat(12) @(negedge clk);$fclose(fd);$display("CONTRACT_MUL_DONE");$finish;
  end
endmodule
