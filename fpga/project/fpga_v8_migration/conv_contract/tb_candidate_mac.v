`timescale 1ns/1ps
// Test-only byte-preserving core copies instantiate the persistent candidate.
// Stimulus and full output capture match tb_contract_mac.v.
module fpga_v8_tb_candidate_mac;
  parameter K=3, USE11=0, CI=3, CO=3, IB=1, W=256, MUL_DELAY=4;
  localparam NG=8*IB, NW=NG*K*K*2, BEATS=W+2;
  reg clk=0, rst=1, start=0;
  always #5 clk=~clk;
  GTP_GRS GRS_INST(.GRS_N(1'b1));
  reg [127:0] wm[0:NW-1];
  reg [127:0] dm0[0:IB*BEATS-1],dm1[0:IB*BEATS-1],dm2[0:IB*BEATS-1];
  reg [127:0] wp[0:8];
  reg wvalid=0,wlast=0,svalid=0,slast=0;
  reg [127:0] s0=0,s1=0,s2=0;
  wire [47:0] md;
  wire mv,ml;
  generate if(USE11) begin
    fpga_v8_test_conv11_conv #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.MUL_DELAY(MUL_DELAY)) dut(
      .clk(clk),.rst(rst),.start(start),.weight_4(wp[4]),.weight_valid(wvalid),.weight_last(wlast),
      .s_data_1(s1),.s_valid(svalid),.s_last(slast),.m_data(md),.m_valid(mv),.m_last(ml));
  end else begin
    fpga_v8_test_conv_conv #(.CHA_PAR_IN(16),.CHA_PAR_OUT(2),.MUL_DELAY(MUL_DELAY)) dut(
      .clk(clk),.rst(rst),.start(start),.type(K==1),
      .weight_0(wp[0]),.weight_1(wp[1]),.weight_2(wp[2]),.weight_3(wp[3]),.weight_4(wp[4]),
      .weight_5(wp[5]),.weight_6(wp[6]),.weight_7(wp[7]),.weight_8(wp[8]),
      .weight_valid(wvalid),.weight_last(wlast),.s_data_0(s0),.s_data_1(s1),.s_data_2(s2),
      .s_valid(svalid),.s_last(slast),.m_data(md),.m_valid(mv),.m_last(ml));
  end endgenerate
  integer fd, cyc=0, g, lane, tap, beat, ii;
  always @(negedge clk) begin
    cyc=cyc+1;
    if(!rst) $fdisplay(fd,"%0d %b %b %012h",cyc,mv,ml,md);
  end
  task load_group(input integer groupid);
    integer l,t;
    begin
      @(negedge clk);
      for(l=0;l<2;l=l+1) begin
        for(t=0;t<9;t=t+1) wp[t]=0;
        if(K==1) wp[4]=wm[groupid*2+l];
        else for(t=0;t<9;t=t+1) wp[t]=wm[groupid*18+t*2+l];
        wvalid=1; wlast=(l==1);
        @(negedge clk);
      end
      wvalid=0;wlast=0;
    end
  endtask
  task data_group(input integer groupid);
    integer b;
    begin
      @(negedge clk);
      for(b=0;b<BEATS;b=b+1) begin
        s0=dm0[(groupid%IB)*BEATS+b];s1=dm1[(groupid%IB)*BEATS+b];s2=dm2[(groupid%IB)*BEATS+b];
        svalid=1;slast=(b==BEATS-1);
        @(negedge clk);
      end
      svalid=0;slast=0;s0=0;s1=0;s2=0;
    end
  endtask
  initial begin
    fd=$fopen("mac_observed.txt","w");
    $readmemh("weights.mem",wm);$readmemh("data0.mem",dm0);$readmemh("data1.mem",dm1);$readmemh("data2.mem",dm2);
    for(ii=0;ii<9;ii=ii+1) wp[ii]=0;
    repeat(12) @(negedge clk);rst=0;
    @(negedge clk);start=1;@(negedge clk);start=0;
    load_group(0);load_group(1);
    repeat(8) @(negedge clk);
    for(g=0;g<NG;g=g+1) begin
      data_group(g);
      // Preserve the audited ping-pong-bank release/overwrite schedule.
      repeat(8) @(negedge clk);
      if(g+2<NG) load_group(g+2);
      repeat(32) @(negedge clk);
    end
    repeat(32) @(negedge clk);
    $fclose(fd);$display("CANDIDATE_MAC_DONE");$finish;
  end
  initial begin #1000000;$display("CONTRACT_TIMEOUT");$finish;end
endmodule
