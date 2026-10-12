1: `timescale 1ns/1ps
2: // Isolated ready/valid RAW preprocessing; no camera, KF, DDR or board wiring.
3: module fpga_v8_raw_letterbox #(
4:     parameter integer WIDTH = 640,
5:     parameter integer HEIGHT = 480,
6:     parameter integer OUT_HEIGHT = 640,
7:     parameter integer TOP_ROWS = 80,
8:     parameter integer FILL_VALUE = 114
9: ) (
10:     input wire clk,
11:     input wire rst_n,
12:     input wire start_valid,
13:     output wire start_ready,
14:     output reg busy,
15:     output reg done,
16:     output reg frame_error,
17:     output wire config_error,
18:     input wire [15:0] s_data,
19:     input wire s_valid,
20:     output wire s_ready,
21:     input wire s_last,
22:     output reg [23:0] m_data,
23:     output reg m_valid,
24:     input wire m_ready,
25:     output reg m_last
26: );
27:     // Bounded geometry keeps row/column counters and comparisons unsigned.
28:     // No resize: WIDTH is both the source and output width.
29:     localparam CONFIG_OK = (WIDTH >= 1) && (WIDTH <= 65535) &&
30:                             (HEIGHT >= 1) && (HEIGHT <= 65535) &&
31:                             (OUT_HEIGHT >= HEIGHT) && (OUT_HEIGHT <= 65535) &&
32:                             (TOP_ROWS >= 0) &&
33:                             (TOP_ROWS <= OUT_HEIGHT - HEIGHT) &&
34:                             (FILL_VALUE >= 0) && (FILL_VALUE <= 255);
35:     reg [15:0] column;
36:     reg [15:0] row;
37:     reg generated_all;
38:     wire body_row;
39:     wire output_slot;
40:     wire final_source;
41:     wire final_output;
42:     wire [23:0] expanded;
43: 
44:     assign config_error = !CONFIG_OK;
45:     assign start_ready = rst_n && CONFIG_OK && !busy;
46:     assign body_row = (row >= TOP_ROWS) && (row < TOP_ROWS + HEIGHT);
47:     assign output_slot = !m_valid || m_ready;
48:     assign final_source = (column == WIDTH - 1) &&
49:                           (row == TOP_ROWS + HEIGHT - 1);
50:     assign final_output = (column == WIDTH - 1) && (row == OUT_HEIGHT - 1);
51:     assign s_ready = rst_n && busy && !generated_all && body_row && output_slot;
52:     // Lane byte 0 is R, then G, then B. Input is an assembled RGB565 word.
53:     assign expanded = {s_data[4:0], s_data[4:2],
54:                        s_data[10:5], s_data[10:9],
55:                        s_data[15:11], s_data[15:13]};
56: 
57:     // Simulation diagnostic plus synthesizable config_error/start rejection.
58:     // synthesis translate_off
59:     initial begin
60:         if (!CONFIG_OK)
61:             $display("FPGA_V8_RAW_LETTERBOX_INVALID_PARAMETERS");
62:     end
63:     // synthesis translate_on
64: 
65:     always @(posedge clk or negedge rst_n) begin
66:         if (!rst_n) begin
67:             busy <= 1'b0;
68:             done <= 1'b0;
69:             frame_error <= 1'b0;
70:             column <= 16'd0;
71:             row <= 16'd0;
72:             generated_all <= 1'b0;
73:             m_data <= 24'd0;
74:             m_valid <= 1'b0;
75:             m_last <= 1'b0;
76:         end else begin
77:             done <= 1'b0;
78:             if (start_valid && start_ready) begin
79:                 busy <= 1'b1;
80:                 frame_error <= 1'b0;
81:                 column <= 16'd0;
82:                 row <= 16'd0;
83:                 generated_all <= 1'b0;
84:                 m_valid <= 1'b0;
85:                 m_last <= 1'b0;
86:             end else if (busy) begin
87:                 if (m_valid && m_ready && m_last) begin
88:                     busy <= 1'b0;
89:                     done <= 1'b1;
90:                 end
91:                 if (output_slot) begin
92:                     m_valid <= 1'b0;
93:                     m_last <= 1'b0;
94:                     if (!generated_all && (!body_row || s_valid)) begin
95:                         m_data <= body_row ? expanded : {3{FILL_VALUE[7:0]}};
96:                         m_valid <= 1'b1;
97:                         m_last <= final_output;
98:                         // Check every accepted source marker, but always use
99:                         // geometry to locate the boundary. Error is sticky.
100:                         if (body_row && (s_last != final_source))
101:                             frame_error <= 1'b1;
102:                         if (final_output)
103:                             generated_all <= 1'b1;
104:                         if (column == WIDTH - 1) begin
105:                             column <= 16'd0;
106:                             row <= row + 16'd1;
107:                         end else begin
108:                             column <= column + 16'd1;
109:                         end
110:                     end
111:                 end
112:             end
113:         end
114:     end
115: endmodule
