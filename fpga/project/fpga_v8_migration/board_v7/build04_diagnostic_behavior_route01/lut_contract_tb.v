`timescale 1ns/1ps
module lut_contract_tb;
reg [5:0] inputs=0;
wire [63:0] y;
genvar g;
generate for(g=0;g<64;g=g+1) begin: lookup
 wire low,high;
 V_LUT5 #(.INIT((64'b1 << g) & 64'hffffffff)) lo(.I0(inputs[0]),.I1(inputs[1]),.I2(inputs[2]),.I3(inputs[3]),.I4(inputs[4]),.Y(low));
 V_LUT5 #(.INIT((64'b1 << g) >> 32)) hi(.I0(inputs[0]),.I1(inputs[1]),.I2(inputs[2]),.I3(inputs[3]),.I4(inputs[4]),.Y(high));
 V_MUX2LUT6 mux(.I0(low),.I1(high),.S(inputs[5]),.Z(y[g]));
end endgenerate
integer i,failures=0;
initial begin
 for(i=0;i<64;i=i+1) begin
  inputs=i;#1;
  if(y !== (64'b1<<i)) begin failures=failures+1;$display("LUT_MISMATCH input=%d actual=%h",i,y);end
 end
 if(failures==0) $display("PASS_OFFICIAL_LUT6_COMPOSITION 4096 single-bit truth-table observations");
 else $display("FAIL_OFFICIAL_LUT6_COMPOSITION failures=%d",failures);
 $finish;
end
endmodule
