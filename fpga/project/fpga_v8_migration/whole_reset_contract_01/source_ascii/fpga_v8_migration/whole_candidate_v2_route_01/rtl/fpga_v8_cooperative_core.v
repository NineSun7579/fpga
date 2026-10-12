1: `timescale 1ns/1ps
2: // Isolated internal-IO integration candidate. All interfaces share core_clk.
3: // Packed camera slot i is [i*FIELD_WIDTH +: FIELD_WIDTH], m0 is least significant.
4: module fpga_v8_cooperative_core #(
5:     parameter integer WIDTH = 640,
6:     parameter integer HEIGHT = 480,
7:     parameter integer OUT_HEIGHT = 640,
8:     parameter integer TOP_ROWS = 80,
9:     parameter integer FILL_VALUE = 114,
10:     parameter [31:0] OUTPUT_BANK0_ADDR = 32'h08000000,
11:     parameter [31:0] OUTPUT_BANK1_ADDR = 32'h08200000,
12:     parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000,
13:     parameter [3:0] AXI_ID = 4'd1
14: ) (
15:     input wire core_clk,
16:     input wire rst_n,
17:     input wire input_valid,
18:     output wire input_ready,
19:     input wire input_raw_valid,
20:     input wire [31:0] input_src_addr,
21:     input wire [31:0] input_source_seq,
22:     input wire [31:0] input_generation,
23:     input wire [2:0] input_camera,
24:     input wire input_camera_bank,
25:     input wire [63:0] input_lease_token,
26:     output wire input_claim,
27:     output wire input_reject,
28:     output wire src_release_valid,
29:     input wire src_release_ready,
30:     output wire [31:0] src_release_addr,
31:     output wire [31:0] src_release_seq,
32:     output wire [31:0] src_release_generation,
33:     output wire [2:0] src_release_camera,
34:     output wire src_release_camera_bank,
35:     output wire [63:0] src_release_token,
36:     output wire busy,
37:     output wire [1:0] bank0_state,
38:     output wire [1:0] bank1_state,
39:     output wire bridge_busy,
40:     output wire bridge_done,
41:     output wire bridge_error,
42:     output wire bridge_cmd_error,
43:     output wire arbiter_busy,
44:     output wire [2:0] arbiter_owner,
45:     output wire arbiter_error,
46:     output wire [4:0] arbiter_error_flags,
47: 
48:     input wire [31:0] s_axil_awaddr,
49:     input wire [2:0] s_axil_awprot,
50:     input wire s_axil_awvalid,
51:     output wire s_axil_awready,
52:     input wire [31:0] s_axil_wdata,
53:     input wire [3:0] s_axil_wstrb,
54:     input wire s_axil_wvalid,
55:     output wire s_axil_wready,
56:     output wire [1:0] s_axil_bresp,
57:     output wire s_axil_bvalid,
58:     input wire s_axil_bready,
59:     input wire [31:0] s_axil_araddr,
60:     input wire [2:0] s_axil_arprot,
61:     input wire s_axil_arvalid,
62:     output wire s_axil_arready,
63:     output wire [31:0] s_axil_rdata,
64:     output wire [1:0] s_axil_rresp,
65:     output wire s_axil_rvalid,
66:     input wire s_axil_rready,
67: 
68:     input wire [23:0] camera_awid,
69:     input wire [191:0] camera_awaddr,
70:     input wire [47:0] camera_awlen,
71:     input wire [17:0] camera_awsize,
72:     input wire [11:0] camera_awburst,
73:     input wire [5:0] camera_awlock,
74:     input wire [23:0] camera_awcache,
75:     input wire [17:0] camera_awprot,
76:     input wire [23:0] camera_awqos,
77:     input wire [23:0] camera_awregion,
78:     input wire [5:0] camera_awvalid,
79:     output wire [5:0] camera_awready,
80:     input wire [767:0] camera_wdata,
81:     input wire [95:0] camera_wstrb,
82:     input wire [5:0] camera_wlast,
83:     input wire [5:0] camera_wvalid,
84:     output wire [5:0] camera_wready,
85:     output wire [23:0] camera_bid,
86:     output wire [11:0] camera_bresp,
87:     output wire [5:0] camera_bvalid,
88:     input wire [5:0] camera_bready,
89: 
90:     output wire [3:0] m_axi_read_arid,
91:     output wire [31:0] m_axi_read_araddr,
92:     output wire [7:0] m_axi_read_arlen,
93:     output wire [2:0] m_axi_read_arsize,
94:     output wire [1:0] m_axi_read_arburst,
95:     output wire m_axi_read_arlock,
96:     output wire [3:0] m_axi_read_arcache,
97:     output wire [2:0] m_axi_read_arprot,
98:     output wire [3:0] m_axi_read_arqos,
99:     output wire [3:0] m_axi_read_arregion,
100:     output wire m_axi_read_arvalid,
101:     input wire m_axi_read_arready,
102:     input wire [3:0] m_axi_read_rid,
103:     input wire [127:0] m_axi_read_rdata,
104:     input wire [1:0] m_axi_read_rresp,
105:     input wire m_axi_read_rlast,
106:     input wire m_axi_read_rvalid,
107:     output wire m_axi_read_rready,
108: 
109:     output wire [3:0] m_axi_write_awid,
110:     output wire [31:0] m_axi_write_awaddr,
111:     output wire [7:0] m_axi_write_awlen,
112:     output wire [2:0] m_axi_write_awsize,
113:     output wire [1:0] m_axi_write_awburst,
114:     output wire m_axi_write_awlock,
115:     output wire [3:0] m_axi_write_awcache,
116:     output wire [2:0] m_axi_write_awprot,
117:     output wire [3:0] m_axi_write_awqos,
118:     output wire [3:0] m_axi_write_awregion,
119:     output wire m_axi_write_awvalid,
120:     input wire m_axi_write_awready,
121:     output wire [127:0] m_axi_write_wdata,
122:     output wire [15:0] m_axi_write_wstrb,
123:     output wire m_axi_write_wlast,
124:     output wire m_axi_write_wvalid,
125:     input wire m_axi_write_wready,
126:     input wire [3:0] m_axi_write_bid,
127:     input wire [1:0] m_axi_write_bresp,
128:     input wire m_axi_write_bvalid,
129:     output wire m_axi_write_bready
130: );
131:     localparam [31:0] OUTPUT_LENGTH = 32'd3 * WIDTH * OUT_HEIGHT;
132:     wire cmd_valid, cmd_ready;
133:     wire [31:0] cmd_src_addr, cmd_dst_addr, cmd_frame_id;
134:     wire [3:0] bridge_awid, bridge_bid;
135:     wire [31:0] bridge_awaddr;
136:     wire [7:0] bridge_awlen;
137:     wire [2:0] bridge_awsize, bridge_awprot;
138:     wire [1:0] bridge_awburst, bridge_bresp;
139:     wire bridge_awlock;
140:     wire [3:0] bridge_awcache, bridge_awqos, bridge_awregion;
141:     wire bridge_awvalid, bridge_awready;
142:     wire [127:0] bridge_wdata;
143:     wire [15:0] bridge_wstrb;
144:     wire bridge_wlast, bridge_wvalid, bridge_wready, bridge_bvalid, bridge_bready;
145:     wire [6:0] all_awready, all_wready, all_bvalid;
146:     wire [27:0] all_bid;
147:     wire [13:0] all_bresp;
148:     assign camera_awready = all_awready[5:0];
149:     assign camera_wready = all_wready[5:0];
150:     assign camera_bid = all_bid[23:0];
151:     assign camera_bresp = all_bresp[11:0];
152:     assign camera_bvalid = all_bvalid[5:0];
153:     assign bridge_awready = all_awready[6];
154:     assign bridge_wready = all_wready[6];
155:     assign bridge_bid = all_bid[27:24];
156:     assign bridge_bresp = all_bresp[13:12];
157:     assign bridge_bvalid = all_bvalid[6];
158: 
159:     fpga_v8_coop_control_axil #(
160:         .OUTPUT_BANK0_ADDR(OUTPUT_BANK0_ADDR), .OUTPUT_BANK1_ADDR(OUTPUT_BANK1_ADDR),
161:         .OUTPUT_LENGTH(OUTPUT_LENGTH)
162:     ) control (
163:         .core_clk(core_clk), .rst_n(rst_n),
164:         .input_valid(input_valid), .input_ready(input_ready),
165:         .input_raw_valid(input_raw_valid), .input_src_addr(input_src_addr),
166:         .input_source_seq(input_source_seq), .input_generation(input_generation),
167:         .input_camera(input_camera), .input_camera_bank(input_camera_bank),
168:         .input_lease_token(input_lease_token), .input_claim(input_claim),
169:         .input_reject(input_reject), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
170:         .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr),
171:         .cmd_frame_id(cmd_frame_id), .bridge_busy(bridge_busy),
172:         .bridge_done(bridge_done), .bridge_error(bridge_error),
173:         .bridge_cmd_error(bridge_cmd_error), .src_release_valid(src_release_valid),
174:         .src_release_ready(src_release_ready), .src_release_addr(src_release_addr),
175:         .src_release_seq(src_release_seq), .src_release_generation(src_release_generation),
176:         .src_release_camera(src_release_camera), .src_release_camera_bank(src_release_camera_bank),
177:         .src_release_token(src_release_token), .busy(busy),
178:         .bank0_state(bank0_state), .bank1_state(bank1_state),
179:         .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot),
180:         .s_axil_awvalid(s_axil_awvalid), .s_axil_awready(s_axil_awready),
181:         .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
182:         .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready),
183:         .s_axil_bresp(s_axil_bresp), .s_axil_bvalid(s_axil_bvalid),
184:         .s_axil_bready(s_axil_bready), .s_axil_araddr(s_axil_araddr),
185:         .s_axil_arprot(s_axil_arprot), .s_axil_arvalid(s_axil_arvalid),
186:         .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata),
187:         .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
188:         .s_axil_rready(s_axil_rready)
189:     );
190: 
191:     fpga_v8_raw_frame_axi #(
192:         .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT),
193:         .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE),
194:         .ID_WIDTH(4), .AXI_ID(AXI_ID), .DDR_ADDRESS_LIMIT(DDR_ADDRESS_LIMIT)
195:     ) bridge (
196:         .clk(core_clk), .rst_n(rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
197:         .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr), .cmd_frame_id(cmd_frame_id),
198:         .cmd_error(bridge_cmd_error), .busy(bridge_busy), .done(bridge_done), .error(bridge_error),
199:         .active_src_addr(), .active_dst_addr(), .active_frame_id(), .completed_frame_id(),
200:         .m_axi_read_arid(m_axi_read_arid), .m_axi_read_araddr(m_axi_read_araddr),
201:         .m_axi_read_arlen(m_axi_read_arlen), .m_axi_read_arsize(m_axi_read_arsize),
202:         .m_axi_read_arburst(m_axi_read_arburst), .m_axi_read_arlock(m_axi_read_arlock),
203:         .m_axi_read_arcache(m_axi_read_arcache), .m_axi_read_arprot(m_axi_read_arprot),
204:         .m_axi_read_arqos(m_axi_read_arqos), .m_axi_read_arregion(m_axi_read_arregion),
205:         .m_axi_read_arvalid(m_axi_read_arvalid), .m_axi_read_arready(m_axi_read_arready),
206:         .m_axi_read_rid(m_axi_read_rid), .m_axi_read_rdata(m_axi_read_rdata),
207:         .m_axi_read_rresp(m_axi_read_rresp), .m_axi_read_rlast(m_axi_read_rlast),
208:         .m_axi_read_rvalid(m_axi_read_rvalid), .m_axi_read_rready(m_axi_read_rready),
209:         .m_axi_write_awid(bridge_awid), .m_axi_write_awaddr(bridge_awaddr),
210:         .m_axi_write_awlen(bridge_awlen), .m_axi_write_awsize(bridge_awsize),
211:         .m_axi_write_awburst(bridge_awburst), .m_axi_write_awlock(bridge_awlock),
212:         .m_axi_write_awcache(bridge_awcache), .m_axi_write_awprot(bridge_awprot),
213:         .m_axi_write_awqos(bridge_awqos), .m_axi_write_awregion(bridge_awregion),
214:         .m_axi_write_awvalid(bridge_awvalid), .m_axi_write_awready(bridge_awready),
215:         .m_axi_write_wdata(bridge_wdata), .m_axi_write_wstrb(bridge_wstrb),
216:         .m_axi_write_wlast(bridge_wlast), .m_axi_write_wvalid(bridge_wvalid),
217:         .m_axi_write_wready(bridge_wready), .m_axi_write_bid(bridge_bid),
218:         .m_axi_write_bresp(bridge_bresp), .m_axi_write_bvalid(bridge_bvalid),
219:         .m_axi_write_bready(bridge_bready)
220:     );
221: 
222:     // The verified candidate arbiter has synchronous active-low rst_n.
223:     fpga_v8_ddr_write_arbiter #(
224:         .MASTER_COUNT(7), .ID_WIDTH(4), .ADDR_WIDTH(32), .DATA_WIDTH(128), .OWNER_WIDTH(3)
225:     ) write_arbiter (
226:         .clk(core_clk), .rst_n(rst_n),
227:         .m_awid({bridge_awid, camera_awid}), .m_awaddr({bridge_awaddr, camera_awaddr}),
228:         .m_awlen({bridge_awlen, camera_awlen}), .m_awsize({bridge_awsize, camera_awsize}),
229:         .m_awburst({bridge_awburst, camera_awburst}), .m_awlock({bridge_awlock, camera_awlock}),
230:         .m_awcache({bridge_awcache, camera_awcache}), .m_awprot({bridge_awprot, camera_awprot}),
231:         .m_awqos({bridge_awqos, camera_awqos}), .m_awregion({bridge_awregion, camera_awregion}),
232:         .m_awvalid({bridge_awvalid, camera_awvalid}), .m_awready(all_awready),
233:         .m_wdata({bridge_wdata, camera_wdata}), .m_wstrb({bridge_wstrb, camera_wstrb}),
234:         .m_wlast({bridge_wlast, camera_wlast}), .m_wvalid({bridge_wvalid, camera_wvalid}),
235:         .m_wready(all_wready), .m_bid(all_bid), .m_bresp(all_bresp), .m_bvalid(all_bvalid),
236:         .m_bready({bridge_bready, camera_bready}),
237:         .s_awid(m_axi_write_awid), .s_awaddr(m_axi_write_awaddr),
238:         .s_awlen(m_axi_write_awlen), .s_awsize(m_axi_write_awsize),
239:         .s_awburst(m_axi_write_awburst), .s_awlock(m_axi_write_awlock),
240:         .s_awcache(m_axi_write_awcache), .s_awprot(m_axi_write_awprot),
241:         .s_awqos(m_axi_write_awqos), .s_awregion(m_axi_write_awregion),
242:         .s_awvalid(m_axi_write_awvalid), .s_awready(m_axi_write_awready),
243:         .s_wdata(m_axi_write_wdata), .s_wstrb(m_axi_write_wstrb),
244:         .s_wlast(m_axi_write_wlast), .s_wvalid(m_axi_write_wvalid), .s_wready(m_axi_write_wready),
245:         .s_bid(m_axi_write_bid), .s_bresp(m_axi_write_bresp),
246:         .s_bvalid(m_axi_write_bvalid), .s_bready(m_axi_write_bready),
247:         .busy(arbiter_busy), .owner(arbiter_owner), .error(arbiter_error),
248:         .error_flags(arbiter_error_flags)
249:     );
250: endmodule
