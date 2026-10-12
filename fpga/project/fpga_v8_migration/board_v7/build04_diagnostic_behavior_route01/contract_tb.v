`timescale 1ns/1ps
module contract_tb;
reg ck=0, sr=0, d=0, grs=1;
wire cq,pq,vcq,vpq;
integer i,j,k,failures=0,checks=0;
GTP_GRS GRS_INST(.GRS_N(grs));
GTP_DFF_C #(.GRS_EN("TRUE"),.INIT(1'b0)) c(.D(d),.CLK(ck),.C(sr),.Q(cq));
GTP_DFF_P #(.GRS_EN("TRUE"),.INIT(1'b1)) p(.D(d),.CLK(ck),.P(sr),.Q(pq));
V_FFASYN #(.GRS_EN("TRUE"),.SET_RESET("RESET"),.LRS_EN("TRUE"),.INIT(1'b0)) vc(.D(d),.CK(ck),.SR(sr),.CE(1'b1),.Q(vcq));
V_FFASYN #(.GRS_EN("TRUE"),.SET_RESET("SET"),.LRS_EN("TRUE"),.INIT(1'b1)) vp(.D(d),.CK(ck),.SR(sr),.CE(1'b1),.Q(vpq));
task check;
begin
 #1; checks=checks+1;
 if(cq !== vcq || pq !== vpq) begin failures=failures+1; $display("MISMATCH %t C=%b/%b P=%b/%b",$time,cq,vcq,pq,vpq); end
end
endtask
initial begin
 check;
 for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) for(k=0;k<2;k=k+1) begin
  ck=0; sr=0; grs=1; d=i; check; ck=1; check;
  ck=0; d=1-i; check;
  sr=j; check; grs=k; check; ck=1; check;
  sr=1; grs=0; check; grs=1; check; ck=0; check; ck=1; check;
  sr=0; check; ck=0; check; ck=1; check;
 end
 if(failures==0) $display("PASS_OFFICIAL_GTP_CP_V_FFASYN checks=%0d",checks);
 else $display("FAIL_OFFICIAL_GTP_CP_V_FFASYN failures=%0d",failures);
 $finish;
end
endmodule
