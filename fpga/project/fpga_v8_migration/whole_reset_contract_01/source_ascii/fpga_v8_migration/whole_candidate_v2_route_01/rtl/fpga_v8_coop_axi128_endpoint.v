1: `timescale 1ns/1ps
2: // Isolated candidate. Verilog-2001; common clock/reset with the controller.
3: // A 16-byte physical slot represents ONE local 32-bit register, never four.
4: module fpga_v8_coop_axi128_endpoint #(
5:     parameter ID_WIDTH = 7,
6:     parameter [31:0] BASE_ADDR = 32'h40010000,
7:     parameter [31:0] WINDOW_BYTES = 32'h00001000
8: ) (
9:     input wire clk, input wire rst_n,
10:     input wire [ID_WIDTH-1:0] s_axi_awid,
11:     input wire [31:0] s_axi_awaddr,
12:     input wire [7:0] s_axi_awlen,
13:     input wire [2:0] s_axi_awsize,
14:     input wire [1:0] s_axi_awburst,
15:     input wire s_axi_awlock,
16:     input wire [3:0] s_axi_awcache,
17:     input wire [2:0] s_axi_awprot,
18:     input wire [3:0] s_axi_awqos, input wire [3:0] s_axi_awregion,
19:     input wire s_axi_awvalid, output wire s_axi_awready,
20:     input wire [127:0] s_axi_wdata,
21:     input wire [15:0] s_axi_wstrb,
22:     input wire s_axi_wlast, input wire s_axi_wvalid,
23:     output wire s_axi_wready,
24:     output reg [ID_WIDTH-1:0] s_axi_bid,
25:     output reg [1:0] s_axi_bresp,
26:     output wire s_axi_bvalid, input wire s_axi_bready,
27:     input wire [ID_WIDTH-1:0] s_axi_arid,
28:     input wire [31:0] s_axi_araddr,
29:     input wire [7:0] s_axi_arlen,
30:     input wire [2:0] s_axi_arsize,
31:     input wire [1:0] s_axi_arburst,
32:     input wire s_axi_arlock,
33:     input wire [3:0] s_axi_arcache,
34:     input wire [2:0] s_axi_arprot,
35:     input wire [3:0] s_axi_arqos, input wire [3:0] s_axi_arregion,
36:     input wire s_axi_arvalid, output wire s_axi_arready,
37:     output reg [ID_WIDTH-1:0] s_axi_rid,
38:     output reg [127:0] s_axi_rdata,
39:     output reg [1:0] s_axi_rresp,
40:     output wire s_axi_rlast, output wire s_axi_rvalid,
41:     input wire s_axi_rready,
42:     output wire [31:0] m_axil_awaddr,
43:     output wire [2:0] m_axil_awprot,
44:     output wire m_axil_awvalid, input wire m_axil_awready,
45:     output wire [31:0] m_axil_wdata,
46:     output wire [3:0] m_axil_wstrb,
47:     output wire m_axil_wvalid, input wire m_axil_wready,
48:     input wire [1:0] m_axil_bresp,
49:     input wire m_axil_bvalid, output wire m_axil_bready,
50:     output wire [31:0] m_axil_araddr,
51:     output wire [2:0] m_axil_arprot,
52:     output wire m_axil_arvalid, input wire m_axil_arready,
53:     input wire [31:0] m_axil_rdata,
54:     input wire [1:0] m_axil_rresp,
55:     input wire m_axil_rvalid, output wire m_axil_rready
56: );
57:     localparam [1:0] WC = 0, WS = 1, WB = 2, WF = 3;
58:     localparam [2:0] RC = 0, RS = 1, RR = 2, RF = 3, RE = 4;
59:     localparam CONFIG_VALID = (ID_WIDTH > 0) && (BASE_ADDR[3:0] == 0) &&
60:         (WINDOW_BYTES != 0) && (WINDOW_BYTES[3:0] == 0) &&
61:         (({1'b0, BASE_ADDR} + {1'b0, WINDOW_BYTES}) <= 33'h100000000);
62:     reg [1:0] wr_state;
63:     reg [2:0] rd_state;
64:     reg aw_held, w_held, w_last, w_bad;
65:     reg [31:0] aw_addr, ar_addr, w_data;
66:     reg [7:0] aw_len;
67:     reg [2:0] aw_size, aw_prot, ar_prot;
68:     reg [1:0] aw_burst;
69:     reg aw_lock;
70:     reg [3:0] w_strb;
71:     reg [8:0] w_remaining, r_remaining;
72:     reg ctrl_aw_pending, ctrl_w_pending;
73:     wire [31:0] aw_diff = aw_addr - BASE_ADDR;
74:     wire [31:0] ar_diff = ar_addr - BASE_ADDR;
75: 
76:     function eligible;
77:         input [31:0] addr;
78:         input [7:0] len;
79:         input [2:0] size;
80:         input [1:0] burst;
81:         reg [32:0] addr_end;
82:         begin
83:             addr_end = {1'b0, addr} + 33'd16;
84:             eligible = CONFIG_VALID && len == 0 && size == 4 &&
85:                 (burst == 0 || burst == 1) && addr[3:0] == 0 &&
86:                 addr[11:0] <= 12'hff0 && addr >= BASE_ADDR &&
87:                 addr_end <= ({1'b0, BASE_ADDR} + {1'b0, WINDOW_BYTES});
88:         end
89:     endfunction
90: 
91:     assign s_axi_awready = rst_n && wr_state == WC && !aw_held;
92:     // First W may precede AW. This slot is not reused until its beat is counted.
93:     assign s_axi_wready = rst_n && wr_state == WC && !w_held;
94:     assign s_axi_bvalid = rst_n && wr_state == WF;
95:     assign m_axil_awaddr = aw_diff >> 2;
96:     assign m_axil_awprot = aw_prot;
97:     assign m_axil_awvalid = rst_n && wr_state == WS && ctrl_aw_pending;
98:     assign m_axil_wdata = w_data;
99:     assign m_axil_wstrb = w_strb;
100:     assign m_axil_wvalid = rst_n && wr_state == WS && ctrl_w_pending;
101:     assign m_axil_bready = rst_n && wr_state == WB;
102:     assign s_axi_arready = rst_n && rd_state == RC;
103:     assign m_axil_araddr = ar_diff >> 2;
104:     assign m_axil_arprot = ar_prot;
105:     assign m_axil_arvalid = rst_n && rd_state == RS;
106:     assign m_axil_rready = rst_n && rd_state == RR;
107:     assign s_axi_rvalid = rst_n && (rd_state == RF || rd_state == RE);
108:     assign s_axi_rlast = (rd_state == RE) ? (r_remaining == 1) : 1'b1;
109: 
110:     always @(posedge clk or negedge rst_n) begin
111:         if (!rst_n) begin
112:             wr_state <= WC;
113:             aw_held <= 0; w_held <= 0; w_last <= 0; w_bad <= 0;
114:             aw_addr <= BASE_ADDR; aw_len <= 0; aw_size <= 0;
115:             aw_burst <= 0; aw_lock <= 0; aw_prot <= 0;
116:             w_data <= 0; w_strb <= 0; w_remaining <= 0;
117:             ctrl_aw_pending <= 0; ctrl_w_pending <= 0;
118:             s_axi_bid <= 0; s_axi_bresp <= 0;
119:             rd_state <= RC; ar_addr <= BASE_ADDR; ar_prot <= 0;
120:             r_remaining <= 0; s_axi_rid <= 0;
121:             s_axi_rdata <= 0; s_axi_rresp <= 0;
122:         end else begin
123:             if (s_axi_awvalid && s_axi_awready) begin
124:                 aw_held <= 1;
125:                 s_axi_bid <= s_axi_awid;
126:                 aw_addr <= s_axi_awaddr; aw_len <= s_axi_awlen;
127:                 aw_size <= s_axi_awsize; aw_burst <= s_axi_awburst;
128:                 aw_lock <= s_axi_awlock; aw_prot <= s_axi_awprot;
129:                 w_remaining <= {1'b0, s_axi_awlen} + 9'd1;
130:                 w_bad <= 0;
131:             end
132:             if (s_axi_wvalid && s_axi_wready) begin
133:                 w_held <= 1;
134:                 w_data <= s_axi_wdata[31:0];
135:                 w_strb <= s_axi_wstrb[3:0];
136:                 w_last <= s_axi_wlast;
137:             end
138:             if (wr_state == WC && aw_held && w_held) begin
139:                 w_held <= 0;
140:                 // Diagnose early/missing WLAST but always drain AWLEN+1 beats.
141:                 if (w_last != (w_remaining == 1)) w_bad <= 1;
142:                 if (w_remaining == 1) begin
143:                     if (eligible(aw_addr, aw_len, aw_size, aw_burst) &&
144:                         !w_bad && w_last) begin
145:                         ctrl_aw_pending <= 1;
146:                         ctrl_w_pending <= 1;
147:                         wr_state <= WS;
148:                     end else begin
149:                         s_axi_bresp <= 2'b10;
150:                         wr_state <= WF;
151:                     end
152:                     w_remaining <= 0;
153:                 end else w_remaining <= w_remaining - 9'd1;
154:             end
155:             if (wr_state == WS) begin
156:                 if (m_axil_awvalid && m_axil_awready) ctrl_aw_pending <= 0;
157:                 if (m_axil_wvalid && m_axil_wready) ctrl_w_pending <= 0;
158:                 if ((!ctrl_aw_pending || m_axil_awready) &&
159:                     (!ctrl_w_pending || m_axil_wready)) wr_state <= WB;
160:             end
161:             if (m_axil_bvalid && m_axil_bready) begin
162:                 s_axi_bresp <= m_axil_bresp;
163:                 wr_state <= WF;
164:             end
165:             if (s_axi_bvalid && s_axi_bready) begin
166:                 wr_state <= WC;
167:                 aw_held <= 0;
168:                 w_bad <= 0;
169:             end
170: 
171:             if (s_axi_arvalid && s_axi_arready) begin
172:                 s_axi_rid <= s_axi_arid;
173:                 ar_addr <= s_axi_araddr; ar_prot <= s_axi_arprot;
174:                 r_remaining <= {1'b0, s_axi_arlen} + 9'd1;
175:                 if (eligible(s_axi_araddr, s_axi_arlen, s_axi_arsize,
176:                              s_axi_arburst)) rd_state <= RS;
177:                 else begin
178:                     s_axi_rdata <= 0; s_axi_rresp <= 2'b10;
179:                     rd_state <= RE;
180:                 end
181:             end
182:             if (m_axil_arvalid && m_axil_arready) rd_state <= RR;
183:             if (m_axil_rvalid && m_axil_rready) begin
184:                 s_axi_rdata <= {96'd0, m_axil_rdata};
185:                 s_axi_rresp <= m_axil_rresp;
186:                 rd_state <= RF;
187:             end
188:             if (s_axi_rvalid && s_axi_rready) begin
189:                 if (rd_state == RF || r_remaining == 1) begin
190:                     rd_state <= RC; r_remaining <= 0;
191:                 end else r_remaining <= r_remaining - 9'd1;
192:             end
193:         end
194:     end
195:     // LOCK/CACHE/QOS/REGION have no local semantics. LOCK never returns EXOKAY.
196:     // Invalid static configurations reject every transaction; runner validates
197:     // the published configuration before simulation. No cancellation/timeout.
198: endmodule
