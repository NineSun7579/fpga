module tiny(input clk,input [1:0] d,output [1:0] q);
genvar i; generate for(i=0;i<2;i=i+1) begin:cameras
leaf source(clk,d[i],q[i]); end endgenerate
endmodule
module leaf(input clk,input d,output reg q);
reg mailbox; always @(posedge clk) begin mailbox<=d; q<=mailbox; end
endmodule
