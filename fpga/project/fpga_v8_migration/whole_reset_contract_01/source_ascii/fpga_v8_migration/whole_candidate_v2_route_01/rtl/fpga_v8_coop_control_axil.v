1: `timescale 1ns/1ps
2: // Isolated candidate, Verilog-2001. All ports use core_clk.
3: // A certified descriptor handshake transfers an EXISTING input lease.
4: // Common reset with the bridge/interconnect is mandatory. See README.md.
5: module fpga_v8_coop_control_axil #(
6:     parameter [31:0] OUTPUT_BANK0_ADDR = 32'h08000000,
7:     parameter [31:0] OUTPUT_BANK1_ADDR = 32'h08200000,
8:     parameter [31:0] OUTPUT_LENGTH = 32'd1228800,
9:     parameter [31:0] DEVICE_ID = 32'h434f4f50,
10:     parameter [31:0] VERSION = 32'h00010000
11: ) (
12:     input wire core_clk,
13:     input wire rst_n,
14:     input wire input_valid,
15:     output wire input_ready,
16:     input wire input_raw_valid,
17:     input wire [31:0] input_src_addr,
18:     input wire [31:0] input_source_seq,
19:     input wire [31:0] input_generation,
20:     input wire [2:0] input_camera,
21:     input wire input_camera_bank,
22:     input wire [63:0] input_lease_token,
23:     output wire input_claim,
24:     output wire input_reject,
25: 
26:     output reg cmd_valid,
27:     input wire cmd_ready,
28:     output reg [31:0] cmd_src_addr,
29:     output reg [31:0] cmd_dst_addr,
30:     output reg [31:0] cmd_frame_id,
31:     input wire bridge_busy,
32:     input wire bridge_done,
33:     input wire bridge_error,
34:     input wire bridge_cmd_error,
35: 
36:     output reg src_release_valid,
37:     input wire src_release_ready,
38:     output reg [31:0] src_release_addr,
39:     output reg [31:0] src_release_seq,
40:     output reg [31:0] src_release_generation,
41:     output reg [2:0] src_release_camera,
42:     output reg src_release_camera_bank,
43:     output reg [63:0] src_release_token,
44:     output wire busy,
45:     output wire [1:0] bank0_state,
46:     output wire [1:0] bank1_state,
47: 
48:     input wire [31:0] s_axil_awaddr,
49:     input wire [2:0] s_axil_awprot,
50:     input wire s_axil_awvalid,
51:     output wire s_axil_awready,
52:     input wire [31:0] s_axil_wdata,
53:     input wire [3:0] s_axil_wstrb,
54:     input wire s_axil_wvalid,
55:     output wire s_axil_wready,
56:     output reg [1:0] s_axil_bresp,
57:     output reg s_axil_bvalid,
58:     input wire s_axil_bready,
59:     input wire [31:0] s_axil_araddr,
60:     input wire [2:0] s_axil_arprot,
61:     input wire s_axil_arvalid,
62:     output wire s_axil_arready,
63:     output reg [31:0] s_axil_rdata,
64:     output reg [1:0] s_axil_rresp,
65:     output reg s_axil_rvalid,
66:     input wire s_axil_rready
67: );
68:     localparam [1:0] FREE = 2'd0, WRITING = 2'd1,
69:                      READY = 2'd2, HOST_READING = 2'd3;
70:     localparam [1:0] OKAY = 2'b00, SLVERR = 2'b10;
71:     reg [1:0] bank_state [0:1];
72:     reg [31:0] bank_seq [0:1];
73:     reg [31:0] bank_gen [0:1];
74:     reg [31:0] bank_src [0:1];
75:     reg [2:0] bank_camera [0:1];
76:     reg bank_camera_bank [0:1];
77:     reg [63:0] bank_token [0:1];
78:     reg active, active_bank, issued, operation_failed, command_rejected;
79:     reg ready_older, host_valid, host_bank;
80:     reg [31:0] ack_bank, ack_seq, ack_gen;
81:     reg [31:0] rejected_ack_count, rejected_claim_count, rejected_raw_count;
82:     reg [31:0] bridge_failure_count, completed_count, released_count;
83:     reg [31:0] accepted_count, last_error;
84:     reg aw_held, w_held;
85:     reg [31:0] aw_addr, w_data;
86:     reg [3:0] w_strb;
87:     integer index;
88: 
89:     wire free_exists = (bank_state[0] == FREE) || (bank_state[1] == FREE);
90:     wire free_bank = (bank_state[0] != FREE);
91:     wire ready_exists = (bank_state[0] == READY) || (bank_state[1] == READY);
92:     wire oldest_bank = ((bank_state[0] == READY) && (bank_state[1] == READY)) ?
93:                        ready_older : (bank_state[1] == READY);
94:     wire cmd_fire = cmd_valid && cmd_ready;
95:     // bridge_cmd_error is the bridge's no-launch command rejection, not an
96:     // in-flight AXI error. A rejection may only retire once bridge_busy is low.
97:     wire rejected_idle = (command_rejected || bridge_cmd_error) && !bridge_busy;
98:     wire operation_finished = active && issued && (bridge_done || rejected_idle);
99:     wire operation_error = operation_failed || bridge_error ||
100:                            bridge_cmd_error || command_rejected;
101: 
102:     assign input_ready = rst_n && !active && !cmd_valid && !bridge_busy &&
103:                          !src_release_valid && free_exists;
104:     assign input_claim = input_valid && input_ready && input_raw_valid;
105:     assign input_reject = input_valid && input_ready && !input_raw_valid;
106:     assign busy = active;
107:     assign bank0_state = bank_state[0];
108:     assign bank1_state = bank_state[1];
109:     // One independent holding slot per write channel, one B outstanding.
110:     // Channels remain backpressured while B is pending; every accepted beat
111:     // is retained. B consumption permits the next captures on the next cycle.
112:     assign s_axil_awready = rst_n && !aw_held && !s_axil_bvalid;
113:     assign s_axil_wready = rst_n && !w_held && !s_axil_bvalid;
114:     assign s_axil_arready = rst_n && (!s_axil_rvalid || s_axil_rready);
115: 
116:     function [31:0] merge_bytes;
117:         input [31:0] original;
118:         input [31:0] replacement;
119:         input [3:0] strobes;
120:         integer byte_index;
121:         begin
122:             merge_bytes = original;
123:             for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1)
124:                 if (strobes[byte_index])
125:                     merge_bytes[byte_index*8 +: 8] = replacement[byte_index*8 +: 8];
126:         end
127:     endfunction
128: 
129:     function valid_read;
130:         input [31:0] addr;
131:         begin
132:             case (addr)
133:                 32'h00, 32'h04, 32'h08, 32'h0c, 32'h10, 32'h14,
134:                 32'h18, 32'h1c, 32'h20, 32'h24, 32'h28, 32'h2c,
135:                 32'h30, 32'h34, 32'h38, 32'h40, 32'h44, 32'h48,
136:                 32'h4c, 32'h50, 32'h54, 32'h58, 32'h5c, 32'h60,
137:                 32'h64, 32'h68, 32'h6c: valid_read = 1'b1;
138:                 default: valid_read = 1'b0;
139:             endcase
140:         end
141:     endfunction
142: 
143:     function [31:0] read_register;
144:         input [31:0] addr;
145:         begin
146:             case (addr)
147:                 32'h00: read_register = DEVICE_ID;
148:                 32'h04: read_register = {18'd0, bank_state[1], bank_state[0],
149:                     3'd0, (last_error != 0), bridge_busy, src_release_valid,
150:                     host_valid, ready_exists, cmd_valid, active};
151:                 32'h08: read_register = VERSION;
152:                 32'h0c: read_register = ready_exists ? {31'd0, oldest_bank} : 32'hffffffff;
153:                 // All descriptor words refer ONLY to the bound host claim.
154:                 32'h10: read_register = host_valid ? {31'd0, host_bank} : 32'hffffffff;
155:                 32'h14: read_register = host_valid ? bank_seq[host_bank] : 32'd0;
156:                 32'h18: read_register = host_valid ? bank_gen[host_bank] : 32'd0;
157:                 32'h1c: read_register = host_valid ? OUTPUT_LENGTH : 32'd0;
158:                 32'h20: read_register = host_valid ?
159:                     (host_bank ? OUTPUT_BANK1_ADDR : OUTPUT_BANK0_ADDR) : 32'd0;
160:                 32'h24: read_register = host_valid ? {29'd0, bank_camera[host_bank]} : 32'd0;
161:                 32'h28: read_register = host_valid ? {31'd0, bank_camera_bank[host_bank]} : 32'd0;
162:                 32'h2c: read_register = host_valid ? bank_src[host_bank] : 32'd0;
163:                 32'h30: read_register = host_valid ? {31'd0, host_bank} : 32'hffffffff;
164:                 32'h34: read_register = host_valid ? bank_token[host_bank][31:0] : 32'd0;
165:                 32'h38: read_register = host_valid ? bank_token[host_bank][63:32] : 32'd0;
166:                 32'h40: read_register = ack_bank;
167:                 32'h44: read_register = ack_seq;
168:                 32'h48: read_register = ack_gen;
169:                 32'h4c: read_register = 32'd0;
170:                 32'h50: read_register = rejected_ack_count;
171:                 32'h54: read_register = rejected_claim_count;
172:                 32'h58: read_register = rejected_raw_count;
173:                 32'h5c: read_register = bridge_failure_count;
174:                 32'h60: read_register = completed_count;
175:                 32'h64: read_register = released_count;
176:                 32'h68: read_register = accepted_count;
177:                 32'h6c: read_register = last_error;
178:                 default: read_register = 32'd0;
179:             endcase
180:         end
181:     endfunction
182: 
183:     always @(posedge core_clk or negedge rst_n) begin
184:         if (!rst_n) begin
185:             for (index = 0; index < 2; index = index + 1) begin
186:                 bank_state[index] <= FREE;
187:                 bank_seq[index] <= 0;
188:                 bank_gen[index] <= 0;
189:                 bank_src[index] <= 0;
190:                 bank_camera[index] <= 0;
191:                 bank_camera_bank[index] <= 0;
192:                 bank_token[index] <= 0;
193:             end
194:             active <= 0;
195:             active_bank <= 0;
196:             issued <= 0;
197:             operation_failed <= 0;
198:             command_rejected <= 0;
199:             ready_older <= 0;
200:             host_valid <= 0;
201:             host_bank <= 0;
202:             cmd_valid <= 0;
203:             cmd_src_addr <= 0;
204:             cmd_dst_addr <= 0;
205:             cmd_frame_id <= 0;
206:             src_release_valid <= 0;
207:             src_release_addr <= 0;
208:             src_release_seq <= 0;
209:             src_release_generation <= 0;
210:             src_release_camera <= 0;
211:             src_release_camera_bank <= 0;
212:             src_release_token <= 0;
213:             ack_bank <= 0;
214:             ack_seq <= 0;
215:             ack_gen <= 0;
216:             rejected_ack_count <= 0;
217:             rejected_claim_count <= 0;
218:             rejected_raw_count <= 0;
219:             bridge_failure_count <= 0;
220:             completed_count <= 0;
221:             released_count <= 0;
222:             accepted_count <= 0;
223:             last_error <= 0;
224:             aw_held <= 0;
225:             w_held <= 0;
226:             aw_addr <= 0;
227:             w_data <= 0;
228:             w_strb <= 0;
229:             s_axil_bresp <= OKAY;
230:             s_axil_bvalid <= 0;
231:             s_axil_rdata <= 0;
232:             s_axil_rresp <= OKAY;
233:             s_axil_rvalid <= 0;
234:         end else begin
235:             if (src_release_valid && src_release_ready) begin
236:                 src_release_valid <= 0;
237:                 released_count <= released_count + 1;
238:             end
239:             if (input_reject) begin
240:                 rejected_raw_count <= rejected_raw_count + 1;
241:                 last_error <= 32'd1;
242:             end
243:             if (input_claim) begin
244:                 bank_state[free_bank] <= WRITING;
245:                 bank_seq[free_bank] <= input_source_seq;
246:                 bank_gen[free_bank] <= input_generation;
247:                 bank_src[free_bank] <= input_src_addr;
248:                 bank_camera[free_bank] <= input_camera;
249:                 bank_camera_bank[free_bank] <= input_camera_bank;
250:                 bank_token[free_bank] <= input_lease_token;
251:                 active <= 1;
252:                 active_bank <= free_bank;
253:                 issued <= 0;
254:                 operation_failed <= 0;
255:                 command_rejected <= 0;
256:                 accepted_count <= accepted_count + 1;
257:                 cmd_valid <= 1;
258:                 cmd_src_addr <= input_src_addr;
259:                 cmd_dst_addr <= free_bank ? OUTPUT_BANK1_ADDR : OUTPUT_BANK0_ADDR;
260:                 cmd_frame_id <= input_source_seq;
261:                 src_release_addr <= input_src_addr;
262:                 src_release_seq <= input_source_seq;
263:                 src_release_generation <= input_generation;
264:                 src_release_camera <= input_camera;
265:                 src_release_camera_bank <= input_camera_bank;
266:                 src_release_token <= input_lease_token;
267:             end
268:             if (cmd_fire) begin
269:                 cmd_valid <= 0;
270:                 issued <= 1;
271:             end
272:             if (active && issued) begin
273:                 if (bridge_error || bridge_cmd_error)
274:                     operation_failed <= 1;
275:                 if (bridge_cmd_error)
276:                     command_rejected <= 1;
277:             end
278:             if (operation_finished) begin
279:                 active <= 0;
280:                 issued <= 0;
281:                 src_release_valid <= 1;
282:                 if (operation_error) begin
283:                     bank_state[active_bank] <= FREE;
284:                     bridge_failure_count <= bridge_failure_count + 1;
285:                     last_error <= 32'd2;
286:                 end else begin
287:                     bank_state[active_bank] <= READY;
288:                     ready_older <= (bank_state[!active_bank] == READY) ?
289:                                    !active_bank : active_bank;
290:                     completed_count <= completed_count + 1;
291:                 end
292:             end
293: 
294:             if (s_axil_bvalid && s_axil_bready)
295:                 s_axil_bvalid <= 0;
296:             if (s_axil_awvalid && s_axil_awready) begin
297:                 aw_held <= 1;
298:                 aw_addr <= s_axil_awaddr;
299:             end
300:             if (s_axil_wvalid && s_axil_wready) begin
301:                 w_held <= 1;
302:                 w_data <= s_axil_wdata;
303:                 w_strb <= s_axil_wstrb;
304:             end
305:             if (aw_held && w_held && !s_axil_bvalid) begin
306:                 aw_held <= 0;
307:                 w_held <= 0;
308:                 s_axil_bvalid <= 1;
309:                 s_axil_bresp <= OKAY;
310:                 case (aw_addr)
311:                     32'h30: if (w_strb[0] && w_data[0]) begin
312:                         // Bank 1 claim; upper command bits are ignored.
313:                         if (!host_valid && ready_exists && oldest_bank) begin
314:                             host_valid <= 1;
315:                             host_bank <= 1;
316:                             bank_state[1] <= HOST_READING;
317:                         end else begin
318:                             s_axil_bresp <= SLVERR;
319:                             rejected_claim_count <= rejected_claim_count + 1;
320:                             last_error <= 32'd3;
321:                         end
322:                     end else if (w_strb[0]) begin
323:                         if (!host_valid && ready_exists && !oldest_bank) begin
324:                             host_valid <= 1;
325:                             host_bank <= 0;
326:                             bank_state[0] <= HOST_READING;
327:                         end else begin
328:                             s_axil_bresp <= SLVERR;
329:                             rejected_claim_count <= rejected_claim_count + 1;
330:                             last_error <= 32'd3;
331:                         end
332:                     end
333:                     32'h40: ack_bank <= merge_bytes(ack_bank, w_data, w_strb);
334:                     32'h44: ack_seq <= merge_bytes(ack_seq, w_data, w_strb);
335:                     32'h48: ack_gen <= merge_bytes(ack_gen, w_data, w_strb);
336:                     32'h4c: if (w_strb[0] && w_data[0]) begin
337:                         if (host_valid && (ack_bank == {31'd0, host_bank}) &&
338:                             (bank_state[host_bank] == HOST_READING) &&
339:                             (ack_seq == bank_seq[host_bank]) &&
340:                             (ack_gen == bank_gen[host_bank])) begin
341:                             bank_state[host_bank] <= FREE;
342:                             host_valid <= 0;
343:                         end else begin
344:                             s_axil_bresp <= SLVERR;
345:                             rejected_ack_count <= rejected_ack_count + 1;
346:                             last_error <= 32'd4;
347:                         end
348:                     end
349:                     default: s_axil_bresp <= SLVERR;
350:                 endcase
351:             end
352: 
353:             // Read current state using THIS accepted AR, never a previous AR.
354:             // Capture the whole response; no live register mux while stalled.
355:             if (s_axil_arvalid && s_axil_arready) begin
356:                 s_axil_rvalid <= 1;
357:                 s_axil_rdata <= read_register(s_axil_araddr);
358:                 s_axil_rresp <= valid_read(s_axil_araddr) ? OKAY : SLVERR;
359:             end else if (s_axil_rvalid && s_axil_rready) begin
360:                 s_axil_rvalid <= 0;
361:             end
362:         end
363:     end
364: endmodule
