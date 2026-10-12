1: `timescale 1ns/1ps
2: // Isolated candidate. Reset while a transaction is outstanding requires a
3: // common reset of the AXI interconnect/slave. Publish only on done && !error.
4: module fpga_v8_raw_frame_axi #(
5:     parameter integer WIDTH = 640,
6:     parameter integer HEIGHT = 480,
7:     parameter integer OUT_HEIGHT = 640,
8:     parameter integer TOP_ROWS = 80,
9:     parameter integer FILL_VALUE = 114,
10:     parameter integer ID_WIDTH = 4,
11:     parameter [ID_WIDTH-1:0] AXI_ID = 1,
12:     parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000
13: ) (
14:     input wire clk,
15:     input wire rst_n,
16:     input wire cmd_valid,
17:     output wire cmd_ready,
18:     input wire [31:0] cmd_src_addr,
19:     input wire [31:0] cmd_dst_addr,
20:     input wire [31:0] cmd_frame_id,
21:     output reg cmd_error,
22:     output reg busy,
23:     output reg done,
24:     output reg error,
25:     output reg [31:0] active_src_addr,
26:     output reg [31:0] active_dst_addr,
27:     output reg [31:0] active_frame_id,
28:     output reg [31:0] completed_frame_id,
29: 
30:     output wire [ID_WIDTH-1:0] m_axi_read_arid,
31:     output wire [31:0] m_axi_read_araddr,
32:     output wire [7:0] m_axi_read_arlen,
33:     output wire [2:0] m_axi_read_arsize,
34:     output wire [1:0] m_axi_read_arburst,
35:     output wire m_axi_read_arlock,
36:     output wire [3:0] m_axi_read_arcache,
37:     output wire [2:0] m_axi_read_arprot,
38:     output wire [3:0] m_axi_read_arqos,
39:     output wire [3:0] m_axi_read_arregion,
40:     output wire m_axi_read_arvalid,
41:     input wire m_axi_read_arready,
42:     input wire [ID_WIDTH-1:0] m_axi_read_rid,
43:     input wire [127:0] m_axi_read_rdata,
44:     input wire [1:0] m_axi_read_rresp,
45:     input wire m_axi_read_rlast,
46:     input wire m_axi_read_rvalid,
47:     output wire m_axi_read_rready,
48: 
49:     output wire [ID_WIDTH-1:0] m_axi_write_awid,
50:     output wire [31:0] m_axi_write_awaddr,
51:     output wire [7:0] m_axi_write_awlen,
52:     output wire [2:0] m_axi_write_awsize,
53:     output wire [1:0] m_axi_write_awburst,
54:     output wire m_axi_write_awlock,
55:     output wire [3:0] m_axi_write_awcache,
56:     output wire [2:0] m_axi_write_awprot,
57:     output wire [3:0] m_axi_write_awqos,
58:     output wire [3:0] m_axi_write_awregion,
59:     output wire m_axi_write_awvalid,
60:     input wire m_axi_write_awready,
61:     output wire [127:0] m_axi_write_wdata,
62:     output wire [15:0] m_axi_write_wstrb,
63:     output wire m_axi_write_wlast,
64:     output wire m_axi_write_wvalid,
65:     input wire m_axi_write_wready,
66:     input wire [ID_WIDTH-1:0] m_axi_write_bid,
67:     input wire [1:0] m_axi_write_bresp,
68:     input wire m_axi_write_bvalid,
69:     output wire m_axi_write_bready
70: );
71:     // Wide arithmetic validates both real bytes and the full bus footprint.
72:     localparam [63:0] SRC_PIXELS = 64'd1 * WIDTH * HEIGHT;
73:     localparam [63:0] SRC_WORDS = (SRC_PIXELS * 2 + 15) / 16;
74:     localparam [63:0] DST_WORDS = (64'd3 * WIDTH * OUT_HEIGHT + 15) / 16;
75:     localparam [63:0] SRC_BUS_BYTES = SRC_WORDS * 16;
76:     localparam [63:0] DST_BUS_BYTES = DST_WORDS * 16;
77:     // Live top.v forwards only [27:0] to DDR; the 512 MiB decode aliases.
78:     localparam [63:0] DDR_LIMIT = {32'd0, DDR_ADDRESS_LIMIT};
79:     localparam CONFIG_OK = (WIDTH >= 1) && (WIDTH <= 65535) &&
80:                            (HEIGHT >= 1) && (HEIGHT <= 65535) &&
81:                            (OUT_HEIGHT >= HEIGHT) && (OUT_HEIGHT <= 65535) &&
82:                            (TOP_ROWS >= 0) && (TOP_ROWS <= OUT_HEIGHT - HEIGHT) &&
83:                            (FILL_VALUE >= 0) && (FILL_VALUE <= 255) &&
84:                            (ID_WIDTH >= 1) && (DDR_ADDRESS_LIMIT != 0) &&
85:                            (DDR_ADDRESS_LIMIT[3:0] == 0) &&
86:                            (DDR_ADDRESS_LIMIT <= 32'h10000000) &&
87:                            (SRC_BUS_BYTES <= DDR_LIMIT) &&
88:                            (DST_BUS_BYTES <= DDR_LIMIT);
89:     localparam [1:0] WR_IDLE = 2'd0, WR_AW = 2'd1,
90:                      WR_W = 2'd2, WR_B = 2'd3;
91: 
92:     wire [63:0] src_end = {32'd0, cmd_src_addr} + SRC_BUS_BYTES;
93:     wire [63:0] dst_end = {32'd0, cmd_dst_addr} + DST_BUS_BYTES;
94:     wire cmd_invalid = !CONFIG_OK || (cmd_src_addr[3:0] != 0) ||
95:                        (cmd_dst_addr[3:0] != 0) ||
96:                        (src_end > DDR_LIMIT) || (dst_end > DDR_LIMIT) ||
97:                        (src_end > 64'h100000000) || (dst_end > 64'h100000000) ||
98:                        (({32'd0, cmd_src_addr} < dst_end) &&
99:                         ({32'd0, cmd_dst_addr} < src_end));
100: 
101:     reg ar_valid;
102:     reg [31:0] read_addr;
103:     reg read_pending;
104:     reg [31:0] read_words_remaining;
105:     reg [31:0] source_pixels_remaining;
106:     reg [127:0] serial_data;
107:     reg [3:0] serial_count;
108:     reg serial_valid;
109:     reg reader_done;
110:     reg [1:0] write_state;
111:     reg [31:0] write_addr;
112:     reg [127:0] write_data;
113:     reg [15:0] write_keep;
114:     reg write_last;
115:     reg last_write_retired;
116: 
117:     wire raw_start_ready, raw_busy, raw_done, raw_error, raw_config_error;
118:     wire [23:0] rgb_data;
119:     wire rgb_valid, rgb_ready, rgb_last, source_ready;
120:     wire [127:0] packed_data;
121:     wire [15:0] packed_keep;
122:     wire packed_valid, packed_ready, packed_last;
123:     wire pipeline_idle = !raw_busy && !rgb_valid && !packed_valid;
124: 
125:     assign cmd_ready = rst_n && !busy && !ar_valid && !read_pending &&
126:                        !serial_valid && (write_state == WR_IDLE) && pipeline_idle;
127:     wire accept_cmd = cmd_valid && cmd_ready;
128:     wire raw_start = accept_cmd && !cmd_invalid;
129:     assign packed_ready = rst_n && busy && (write_state == WR_IDLE) &&
130:                           !last_write_retired;
131: 
132:     fpga_v8_raw_letterbox #(
133:         .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT),
134:         .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE)
135:     ) raw_pipeline (
136:         .clk(clk), .rst_n(rst_n), .start_valid(raw_start),
137:         .start_ready(raw_start_ready), .busy(raw_busy), .done(raw_done),
138:         .frame_error(raw_error), .config_error(raw_config_error),
139:         .s_data(serial_data[15:0]), .s_valid(serial_valid),
140:         .s_ready(source_ready), .s_last(source_pixels_remaining == 1),
141:         .m_data(rgb_data), .m_valid(rgb_valid), .m_ready(rgb_ready),
142:         .m_last(rgb_last)
143:     );
144:     fpga_v8_rgb888_pack128 output_packer (
145:         .clk(clk), .rst_n(rst_n), .s_data(rgb_data), .s_valid(rgb_valid),
146:         .s_ready(rgb_ready), .s_last(rgb_last), .m_data(packed_data),
147:         .m_keep(packed_keep), .m_valid(packed_valid),
148:         .m_ready(packed_ready), .m_last(packed_last)
149:     );
150: 
151:     assign m_axi_read_arid = AXI_ID;
152:     assign m_axi_read_araddr = read_addr;
153:     assign m_axi_read_arlen = 8'd0;
154:     assign m_axi_read_arsize = 3'd4;
155:     assign m_axi_read_arburst = 2'b01;
156:     assign m_axi_read_arlock = 1'b0;
157:     assign m_axi_read_arcache = 4'h3;
158:     assign m_axi_read_arprot = 3'd0;
159:     assign m_axi_read_arqos = 4'd0;
160:     assign m_axi_read_arregion = 4'd0;
161:     assign m_axi_read_arvalid = rst_n && ar_valid;
162:     // An issued read always has a free serializer, so output padding never
163:     // keeps the DDR read response outstanding while RGB output is blocked.
164:     assign m_axi_read_rready = rst_n && busy && read_pending && !serial_valid;
165: 
166:     assign m_axi_write_awid = AXI_ID;
167:     assign m_axi_write_awaddr = write_addr;
168:     assign m_axi_write_awlen = 8'd0;
169:     assign m_axi_write_awsize = 3'd4;
170:     assign m_axi_write_awburst = 2'b01;
171:     assign m_axi_write_awlock = 1'b0;
172:     assign m_axi_write_awcache = 4'h3;
173:     assign m_axi_write_awprot = 3'd0;
174:     assign m_axi_write_awqos = 4'd0;
175:     assign m_axi_write_awregion = 4'd0;
176:     assign m_axi_write_awvalid = rst_n && busy && (write_state == WR_AW);
177:     assign m_axi_write_wdata = write_data;
178:     assign m_axi_write_wstrb = write_keep;
179:     assign m_axi_write_wlast = 1'b1;
180:     assign m_axi_write_wvalid = rst_n && busy && (write_state == WR_W);
181:     assign m_axi_write_bready = rst_n && busy && (write_state == WR_B);
182: 
183:     always @(posedge clk or negedge rst_n) begin
184:         if (!rst_n) begin
185:             cmd_error <= 1'b0;
186:             busy <= 1'b0;
187:             done <= 1'b0;
188:             error <= 1'b0;
189:             active_src_addr <= 32'd0;
190:             active_dst_addr <= 32'd0;
191:             active_frame_id <= 32'd0;
192:             completed_frame_id <= 32'd0;
193:             ar_valid <= 1'b0;
194:             read_addr <= 32'd0;
195:             read_pending <= 1'b0;
196:             read_words_remaining <= 32'd0;
197:             source_pixels_remaining <= 32'd0;
198:             serial_data <= 128'd0;
199:             serial_count <= 4'd0;
200:             serial_valid <= 1'b0;
201:             reader_done <= 1'b0;
202:             write_state <= WR_IDLE;
203:             write_addr <= 32'd0;
204:             write_data <= 128'd0;
205:             write_keep <= 16'd0;
206:             write_last <= 1'b0;
207:             last_write_retired <= 1'b0;
208:         end else begin
209:             cmd_error <= 1'b0;
210:             done <= 1'b0;
211:             if (accept_cmd) begin
212:                 active_src_addr <= cmd_src_addr;
213:                 active_dst_addr <= cmd_dst_addr;
214:                 active_frame_id <= cmd_frame_id;
215:                 error <= cmd_invalid;
216:                 if (cmd_invalid) begin
217:                     cmd_error <= 1'b1;
218:                 end else begin
219:                     busy <= 1'b1;
220:                     read_addr <= cmd_src_addr;
221:                     read_words_remaining <= SRC_WORDS[31:0];
222:                     source_pixels_remaining <= SRC_PIXELS[31:0];
223:                     serial_count <= 4'd0;
224:                     reader_done <= 1'b0;
225:                     write_addr <= cmd_dst_addr;
226:                     last_write_retired <= 1'b0;
227:                 end
228:             end else if (busy) begin
229:                 if (raw_error || raw_config_error)
230:                     error <= 1'b1;
231: 
232:                 if (!ar_valid && !read_pending && !serial_valid &&
233:                     (read_words_remaining != 0))
234:                     ar_valid <= 1'b1;
235:                 if (m_axi_read_arvalid && m_axi_read_arready) begin
236:                     ar_valid <= 1'b0;
237:                     read_pending <= 1'b1;
238:                     read_addr <= read_addr + 32'd16;
239:                     read_words_remaining <= read_words_remaining - 32'd1;
240:                 end
241:                 if (m_axi_read_rvalid && m_axi_read_rready) begin
242:                     read_pending <= 1'b0;
243:                     serial_data <= m_axi_read_rdata;
244:                     serial_count <= (source_pixels_remaining >= 8) ?
245:                                     4'd8 : source_pixels_remaining[3:0];
246:                     serial_valid <= 1'b1;
247:                     if ((m_axi_read_rid != AXI_ID) ||
248:                         (m_axi_read_rresp != 2'b00) || !m_axi_read_rlast)
249:                         error <= 1'b1;
250:                 end
251:                 if (serial_valid && source_ready) begin
252:                     serial_data <= {16'd0, serial_data[127:16]};
253:                     serial_count <= serial_count - 4'd1;
254:                     source_pixels_remaining <= source_pixels_remaining - 32'd1;
255:                     if (serial_count == 1)
256:                         serial_valid <= 1'b0;
257:                     if (source_pixels_remaining == 1)
258:                         reader_done <= 1'b1;
259:                 end
260: 
261:                 // AW is not requested until a complete packed beat exists.
262:                 // Accept AW, hold W through stalls, then wait for its B.
263:                 case (write_state)
264:                     WR_IDLE: if (packed_valid && packed_ready) begin
265:                         write_data <= packed_data;
266:                         write_keep <= packed_keep;
267:                         write_last <= packed_last;
268:                         write_state <= WR_AW;
269:                     end
270:                     WR_AW: if (m_axi_write_awready)
271:                         write_state <= WR_W;
272:                     WR_W: if (m_axi_write_wready)
273:                         write_state <= WR_B;
274:                     WR_B: if (m_axi_write_bvalid) begin
275:                         if ((m_axi_write_bid != AXI_ID) ||
276:                             (m_axi_write_bresp != 2'b00))
277:                             error <= 1'b1;
278:                         write_state <= WR_IDLE;
279:                         if (write_last)
280:                             last_write_retired <= 1'b1;
281:                         else
282:                             write_addr <= write_addr + 32'd16;
283:                     end
284:                 endcase
285:                 if (reader_done && last_write_retired && pipeline_idle &&
286:                     !ar_valid && !read_pending && !serial_valid &&
287:                     (write_state == WR_IDLE)) begin
288:                     busy <= 1'b0;
289:                     done <= 1'b1;
290:                     completed_frame_id <= active_frame_id;
291:                 end
292:             end
293:         end
294:     end
295: endmodule
