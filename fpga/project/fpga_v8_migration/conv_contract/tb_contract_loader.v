`timescale 1ns/1ps
module tb_contract_loader;
  parameter K=3,USE11=0;
  localparam NB=8,NW=8*K*K*2,NT=NB+NW;
  reg clk=0,rst=1,start=0;
  always #5 clk=~clk;
  reg [127:0] image[0:NT-1];
  reg [127:0] sd=0;
  reg sv=0,sl=0,cr=0,req=0,breq=0;
  wire sr,cv,mv,ml,bv,bl;
  wire [31:0] ca,cl;
  wire [127:0] w[0:8];
  wire [63:0] bias;
  generate if(USE11) begin
    conv11_weight #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.CHA_IMG_IN(512),.CHA_IMG_OUT(256)) loader(
      .clk(clk),.rst(rst),.start(start),.type(1'b1),.stride(1'b0),
      .base_addr(32'h1000),.weight_sum(NT*16),.weight_len(NB*16),.row_num(1),
      .calculate_num(8),.calculate_cout_num(8),.s_data(sd),.s_valid(sv),.s_last(sl),.s_ready(sr),
      .m_data_4(w[4]),.m_valid(mv),.m_last(ml),.m_req(req),
      .bias(bias),.bias_valid(bv),.bias_last(bl),.bias_req(breq),
      .cmd_addr(ca),.cmd_len(cl),.cmd_valid(cv),.cmd_ready(cr),.calculate_end(1'b0));
    assign w[0]=0;assign w[1]=0;assign w[2]=0;assign w[3]=0;
    assign w[5]=0;assign w[6]=0;assign w[7]=0;assign w[8]=0;
  end else begin
    conv_weight #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.CHA_IMG_IN(512),.CHA_IMG_OUT(256)) loader(
      .clk(clk),.rst(rst),.start(start),.type(K==1),.stride(1'b0),
      .base_addr(32'h1000),.weight_sum(NT*16),.bias_len(NB*16),.row_num(1),
      .calculate_num(8),.calculate_cout_num(8),.s_data(sd),.s_valid(sv),.s_last(sl),.s_ready(sr),
      .m_data_0(w[0]),.m_data_1(w[1]),.m_data_2(w[2]),.m_data_3(w[3]),.m_data_4(w[4]),
      .m_data_5(w[5]),.m_data_6(w[6]),.m_data_7(w[7]),.m_data_8(w[8]),
      .m_valid(mv),.m_last(ml),.m_req(req),
      .bias(bias),.bias_valid(bv),.bias_last(bl),.bias_req(breq),
      .cmd_addr(ca),.cmd_len(cl),.cmd_valid(cv),.cmd_ready(cr),.calculate_end(1'b0));
  end endgenerate
  integer fd,cyc=0,t,b,base,count,g,j;
  always @(negedge clk) begin
    cyc=cyc+1;
    if(!rst && (mv!==1'b0 || ml!==1'b0))
      $fdisplay(fd,"W %0d %b %b %032h %032h %032h %032h %032h %032h %032h %032h %032h",cyc,mv,ml,w[0],w[1],w[2],w[3],w[4],w[5],w[6],w[7],w[8]);
    if(!rst && (bv!==1'b0 || bl!==1'b0)) $fdisplay(fd,"B %0d %b %b %016h",cyc,bv,bl,bias);
  end
  task transfer;
    begin
      wait(cv===1'b1);@(negedge clk);
      base=(ca-32'h1000)/16;count=cl/16;
      $fdisplay(fd,"C %08h %0d",ca,cl);
      cr=1;@(negedge clk);cr=0;
      for(b=0;b<count;b=b+1) begin
        while(sr!==1'b1) @(negedge clk);
        sd=image[base+b];sv=1;sl=(b==count-1);@(negedge clk);
      end
      sv=0;sl=0;
    end
  endtask
  initial begin
    fd=$fopen("loader_observed.txt","w");$readmemh("parameter_image.mem",image);
    repeat(12) @(negedge clk);rst=0;
    @(negedge clk);start=1;@(negedge clk);start=0;
    transfer;transfer;
    repeat(32) @(negedge clk);
    for(g=0;g<8;g=g+1) begin
      req=1;breq=1;@(negedge clk);req=0;breq=0;
      repeat(24) @(negedge clk);
    end
    repeat(16) @(negedge clk);$fclose(fd);$display("CONTRACT_LOADER_DONE");$finish;
  end
  initial begin #100000;$display("CONTRACT_TIMEOUT");$finish;end
endmodule
