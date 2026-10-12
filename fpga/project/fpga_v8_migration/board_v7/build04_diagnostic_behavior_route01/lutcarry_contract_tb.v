`timescale 1ns/1ps
module lutcarry_contract_tb;
reg [5:0] inputs=0;
wire [63:0] y;
genvar g;
generate for(g=0;g<64;g=g+1) begin: lookup
 V_LUT6CARRY #(.INIT(64'b1<<g),.I5_TO_CARRY("TRUE"),.I5_TO_LUT("TRUE")) lut(.I0(inputs[0]),.I1(inputs[1]),.I2(inputs[2]),.I3(inputs[3]),.I4(inputs[4]),.I5(inputs[5]),.CIN(1'b0),.Z(y[g]),.Z5(),.COUT());
end endgenerate
integer i,failures=0;
initial begin
 for(i=0;i<64;i=i+1) begin inputs=i;#1;if(y !== (64'b1<<i)) begin failures=failures+1;$display("LUTCARRY_MISMATCH input=%d actual=%h",i,y);end end
 if(failures==0) $display("PASS_OFFICIAL_LUT6CARRY 4096 single-bit truth-table observations");
 else $display("FAIL_OFFICIAL_LUT6CARRY failures=%d",failures);
 $finish;
end
endmodule
