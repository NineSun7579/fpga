1: //******************************************************************
2: // Copyright (c) 2015 PANGO MICROSYSTEMS, INC
3: // ALL RIGHTS REVERVED.
4: //******************************************************************
5: `timescale 1ns/1ps
6: module hsst_rst_sync_v1_0
7:     (
8:      input                  clk,
9:      input                  rst_n,
10: 
11:      input                  sig_async,
12:      output reg             sig_synced
13:     );
14: 
15: //
16: reg                      sig_async_ff;
17: 
18: //single bit
19: always@(posedge clk or negedge rst_n)
20: begin
21:     if (!rst_n)
22:         sig_async_ff <= 1'b0;
23:     else
24:         sig_async_ff <= sig_async;
25: end
26: 
27: always@(posedge clk or negedge rst_n)
28: begin
29:     if (!rst_n)
30:         sig_synced <= 1'b0;
31:     else
32:         sig_synced <= sig_async_ff;
33: end
34: 
35: endmodule
