1: //******************************************************************
2: // Copyright (c) 2015 PANGO MICROSYSTEMS, INC
3: // ALL RIGHTS REVERVED.
4: //******************************************************************
5: `timescale 1ns/1ps
6: module  hsst_rst_cross_sync_v1_0 #(
7:     parameter RST_CNTR_WIDTH     = 16,
8:     parameter RST_CNTR_VALUE     = 16'hC000
9: )(
10:     // Reset and Clock
11:     input           clk,
12:     input           rstn_in,
13: 
14:     output  reg     rstn_out
15: );
16: 
17: //****************************************************************************//
18: //                      Internal Signal                                       //
19: //****************************************************************************//
20:     reg rs1;
21:     reg rs2;
22: 
23:     wire                          rstn_inner;
24:     reg     [3:0]                 rstn_inner_d;
25:     reg                           rstn_sync;
26:     reg     [RST_CNTR_WIDTH-1:0]  cnt_rst;
27: 
28: //****************************************************************************//
29: //                      Sequential and Logic                                  //
30: //****************************************************************************//
31:     always@(posedge clk or negedge rstn_in) 
32:     begin
33:         if(!rstn_in) 
34:         begin
35:             rs1<=0;
36:             rs2<=0;
37:         end
38:         else
39:         begin
40:             rs1<=1;
41:             rs2<=rs1;
42:         end
43:     end
44: 
45: 
46:     assign rstn_inner = rs2;
47: 
48:     `ifdef IPS2L_PCIE_SPEEDUP_SIM
49:         initial begin
50:             rstn_inner_d = 4'hf; //CLM reg default value is 1
51:             rstn_sync    = 1'b1;
52:             cnt_rst      = {RST_CNTR_WIDTH{1'b1}};
53:             rstn_out     = 1'b1;
54:         end
55:     `endif
56: 
57:     always @(posedge clk or negedge rstn_inner)
58:     begin
59:         if (!rstn_inner) begin
60:             rstn_inner_d <= 4'h0; //CLM reg default value is 1
61:             rstn_sync    <= 1'b0;
62:             cnt_rst      <= {RST_CNTR_WIDTH{1'b1}};
63:             rstn_out     <= 1'b0;
64:         end
65:         else begin
66:             rstn_inner_d <= {rstn_inner_d[2:0], rstn_inner};
67: 
68:             if (rstn_inner_d[3:2] == 2'd0)
69:                 rstn_sync <= 1'b0;
70:             else
71:                 rstn_sync <= 1'b1;
72: 
73:             if (~rstn_sync) begin
74:                 cnt_rst <= {RST_CNTR_WIDTH{1'b1}};
75:                 rstn_out   <= 1'b0;
76:             end
77:             else if (cnt_rst == RST_CNTR_VALUE)
78:                 rstn_out <= 1'b1;
79:             else begin
80:                 rstn_out <= 1'b0;
81:                 cnt_rst <= cnt_rst + {{(RST_CNTR_WIDTH-1){1'b0}}, 1'b1};
82:             end
83:         end
84:     end
85: endmodule
