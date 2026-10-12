1: `timescale 1ns/1ps
2: // Byte-stream packer: input {B,G,R}; lane 0 of each output word is first byte.
3: module fpga_v8_rgb888_pack128 (
4:     input wire clk,
5:     input wire rst_n,
6:     input wire [23:0] s_data,
7:     input wire s_valid,
8:     output wire s_ready,
9:     input wire s_last,
10:     output reg [127:0] m_data,
11:     output reg [15:0] m_keep,
12:     output reg m_valid,
13:     input wire m_ready,
14:     output reg m_last
15: );
16:     reg [127:0] carry_bytes;
17:     reg [4:0] byte_count;
18:     reg flush_pending;
19:     wire output_slot;
20:     wire [143:0] appended;
21:     wire [5:0] appended_count;
22:     wire [15:0] partial_keep;
23: 
24:     assign output_slot = !m_valid || m_ready;
25:     // Finish a frame before accepting the next one. A final overflow may
26:     // need two output words: a full word followed by 1 or 2 remaining bytes.
27:     assign s_ready = rst_n && output_slot && !flush_pending &&
28:                      !(m_valid && m_last);
29:     assign appended = {16'd0, carry_bytes} |
30:                       ({120'd0, s_data} << (byte_count * 8));
31:     assign appended_count = {1'b0, byte_count} + 6'd3;
32:     assign partial_keep = (16'hffff >> (16 - appended_count));
33: 
34:     always @(posedge clk or negedge rst_n) begin
35:         if (!rst_n) begin
36:             carry_bytes <= 128'd0;
37:             byte_count <= 5'd0;
38:             flush_pending <= 1'b0;
39:             m_data <= 128'd0;
40:             m_keep <= 16'd0;
41:             m_valid <= 1'b0;
42:             m_last <= 1'b0;
43:         end else if (output_slot) begin
44:             m_valid <= 1'b0;
45:             m_last <= 1'b0;
46:             m_keep <= 16'd0;
47:             if (flush_pending) begin
48:                 m_data <= carry_bytes;
49:                 m_keep <= (16'hffff >> (16 - byte_count));
50:                 m_valid <= 1'b1;
51:                 m_last <= 1'b1;
52:                 carry_bytes <= 128'd0;
53:                 byte_count <= 5'd0;
54:                 flush_pending <= 1'b0;
55:             end else if (s_valid && s_ready) begin
56:                 if (appended_count >= 16) begin
57:                     m_data <= appended[127:0];
58:                     m_keep <= 16'hffff;
59:                     m_valid <= 1'b1;
60:                     m_last <= s_last && (appended_count == 16);
61:                     carry_bytes <= {112'd0, appended[143:128]};
62:                     byte_count <= appended_count - 16;
63:                     flush_pending <= s_last && (appended_count != 16);
64:                 end else if (s_last) begin
65:                     m_data <= appended[127:0];
66:                     m_keep <= partial_keep;
67:                     m_valid <= 1'b1;
68:                     m_last <= 1'b1;
69:                     carry_bytes <= 128'd0;
70:                     byte_count <= 5'd0;
71:                 end else begin
72:                     carry_bytes <= appended[127:0];
73:                     byte_count <= appended_count[4:0];
74:                 end
75:             end
76:         end
77:     end
78: endmodule
