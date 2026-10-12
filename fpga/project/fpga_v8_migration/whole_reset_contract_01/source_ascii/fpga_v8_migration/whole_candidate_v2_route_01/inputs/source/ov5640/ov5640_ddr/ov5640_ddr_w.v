1: module ov5640_ddr_w #(
2:     parameter DATA_WIDTH = 24,
3:     parameter AXI_DATA_WIDTH = 128,
4:     parameter CAM_DATA_LEN  = 172800, //1280*720*3/16
5:     parameter DEVICE = "PG"
6: )(
7:     input          axi_clk        ,
8:     input          axi_rst        ,
9:     input          capture_flush,
10:     output         capture_overflow,
11:     output [15:0] axi_data_available,
12: 
13: 
14:     input  [$clog2(CAM_DATA_LEN) : 0]  data_len       /*synthesis PAP_MARK_DEBUG="1"*/, //\xef\xbf\xbd\xef\xbf\xbd16\xef\xbf\xbd\xd6\xbd\xef\xbf\xbd\xce\xaa\xef\xbf\xbd\xef\xbf\xbd\xce\xbb
15: 
16:     input  [DATA_WIDTH-1 :0]       s_data       ,
17:     input                          s_data_valid ,
18:     input                          s_vsync      ,
19:     input                          s_hsync      ,       //\xc3\xbb\xef\xbf\xbd\xef\xbf\xbd
20: 
21:     output [AXI_DATA_WIDTH-1 : 0]  axi_data       /*synthesis PAP_MARK_DEBUG="1"*/,
22:     output                         axi_data_valid /*synthesis PAP_MARK_DEBUG="1"*/,
23:     output                         axi_data_last  /*synthesis PAP_MARK_DEBUG="1"*/, 
24:     input                          axi_data_ready /*synthesis PAP_MARK_DEBUG="1"*/,
25:     output [31:0]                  dbg_axi_cnt,
26:     output [31:0]                  dbg_axi_num  ,
27:     // [ZDIAG 2026-09-18] per-frame zero-beat accounting, latched at VSYNC so
28:     // it can be read reliably once streaming stops.
29:     output [31:0]                  dbg_zdin     ,  // wr_en && din==0
30:     output [31:0]                  dbg_zout         // fifo_we && fifo_wd==0
31: );
32: 
33: 
34: 
35: 
36:     wire local_rst = axi_rst | capture_flush;
37:     wire out_full;
38:     reg             wr_en;
39:     reg  [31 : 0]   din  ;
40:     wire            rd_en;
41:     wire [AXI_DATA_WIDTH-1 : 0] dout ;
42: 
43:     wire                        empty;
44:     wire                        full /*synthesis PAP_MARK_DEBUG="1"*/;
45: 
46: 
47: 
48:     reg [1 : 0] cnt;
49:     always @(posedge axi_clk) begin
50:         if(local_rst)begin
51:             cnt <= 2'd0;
52:         end
53:         else if(s_data_valid)begin
54:             cnt <= cnt + 2'd1;
55:         end
56:     end
57: generate
58:     if(DATA_WIDTH == 24) begin    
59:     
60:         reg [23 : 0]  cam_data_temp;
61:         always @(posedge axi_clk) begin
62:             if(s_data_valid)begin
63:                 case (cnt)
64:                     2'b00:begin
65:                         cam_data_temp <= s_data;
66:                     end
67:                     2'b01:begin
68:                         cam_data_temp <= {8'd0, s_data[23:8]};
69:                     end
70:                     2'b10:begin
71:                         cam_data_temp <= {16'd0, s_data[23:16]};
72:                     end
73:                     2'b11:begin
74:                         cam_data_temp <= 24'd0;
75:                     end
76:                 endcase
77:             end
78:         end
79: 
80:         always @(posedge axi_clk) begin
81:             if(s_data_valid)begin
82:                 case (cnt)
83:                     2'b01:begin
84:                         din <= {s_data[7:0], cam_data_temp[23:0]};
85:                     end
86:                     2'b10:begin
87:                         din <= {s_data[15:0], cam_data_temp[15:0]};
88:                     end
89:                     2'b11:begin
90:                         din <= {s_data, cam_data_temp[7:0]};
91:                     end
92:                 endcase
93:             end
94:         end
95: 
96:         always @(posedge axi_clk) begin
97:             if(local_rst)begin
98:                 wr_en <= 1'b0;
99:             end
100:             else if(s_data_valid & (cnt != 2'b00))begin
101:                 wr_en <= 1'b1;
102:             end
103:             else begin
104:                 wr_en <= 1'b0;
105:             end
106:         end
107: 
108:     end
109:     else if(DATA_WIDTH == 16) begin
110: 
111:         reg [15 : 0] cam_data_temp;
112:         always @(posedge axi_clk) begin
113:             if(s_data_valid) begin
114:                 cam_data_temp <= s_data;
115:             end
116:         end
117: 
118: 
119:         always @(posedge axi_clk) begin
120:             if(s_data_valid)begin
121:                 if(cnt[0]) begin
122:                     din <= {s_data, cam_data_temp};
123:                 end
124:             end
125:         end
126: 
127:         always @(posedge axi_clk) begin
128:             if(local_rst)begin
129:                 wr_en <= 1'b0;
130:             end
131:             else if(s_data_valid & cnt[0])begin
132:                 wr_en <= 1'b1;
133:             end
134:             else begin
135:                 wr_en <= 1'b0;
136:             end
137:         end
138: 
139:     end
140:     else if(DATA_WIDTH == 8) begin
141: 
142:         reg [23 : 0] cam_data_temp;
143:         always @(posedge axi_clk) begin
144:             if(s_data_valid) begin
145:                 cam_data_temp <= {s_data, cam_data_temp[23:8]};
146:             end
147:         end
148: 
149:         always @(posedge axi_clk) begin
150:             if(s_data_valid)begin
151:                 if(&cnt) begin
152:                     din <= {s_data, cam_data_temp};
153:                 end
154:             end
155:         end
156: 
157: 
158:         always @(posedge axi_clk) begin
159:             if(local_rst)begin
160:                 wr_en <= 1'b0;
161:             end
162:             else if(s_data_valid & &cnt)begin
163:                 wr_en <= 1'b1;
164:             end
165:             else begin
166:                 wr_en <= 1'b0;
167:             end
168:         end
169: 
170:     end
171: endgenerate
172: 
173: 
174: 
175: 
176: 
177: 
178:         reg [$clog2(CAM_DATA_LEN) : 0] axi_num/*synthesis PAP_MARK_DEBUG="1"*/;
179:         reg [$clog2(CAM_DATA_LEN) : 0] axi_cnt/*synthesis PAP_MARK_DEBUG="1"*/;
180: 
181:         always @(posedge axi_clk) begin
182:             if(local_rst)begin
183:                 axi_num <= 20'd0;
184:             end
185:             else begin
186:                 axi_num <= data_len - 20'd1;
187:             end
188:         end
189: 
190:         always @(posedge axi_clk) begin
191:             if(local_rst)begin
192:                 axi_cnt <= 20'd0;
193:             end
194:             else if(s_vsync)begin
195:                 axi_cnt <= 20'd0;
196:             end
197:             else if(axi_data_valid & axi_data_ready)begin
198:                 if(axi_data_last)begin
199:                     axi_cnt <= 20'd0;
200:                 end
201:                 else begin
202:                     axi_cnt <= axi_cnt + 20'd1;
203:                 end
204:             end
205:         end
206: 
207:     // reg test1/*synthesis PAP_MARK_DEBUG="1"*/;
208:     // always @(posedge axi_clk) begin
209:     //     if(axi_rst) begin
210:     //         test1 <= 1'b0;
211:     //     end
212:     //     else if(s_vsync && (axi_cnt != 0)) begin
213:     //         test1 <= 1'b1;
214:     //     end
215:     // end
216: 
217: 
218:     // The distributed FIFO is first-word fall-through with OUTPUT_REG=0:
219:     // dout already addresses the current head, and rd_en advances it only
220:     // after the AXI consumer accepts that word.
221:     assign rd_en = axi_data_valid & axi_data_ready;
222:     assign axi_data_last = (axi_cnt == axi_num);
223:     assign axi_data = dout;
224:     assign axi_data_valid = !empty && !local_rst;
225: 
226: 
227: 
228: 
229:         wire [AXI_DATA_WIDTH-1 : 0] dout_drm;
230:         wire                        empty_drm/*synthesis PAP_MARK_DEBUG="1"*/;  
231:         wire                        almost_full_drm;
232:         wire                        almost_full_out;
233:         // Do not drain the DRM FIFO unless both stages can accept the word.
234:         // Without almost_full_out the output FIFO fills during AXI stalls and
235:         // DRM words are silently dropped -> periodic 128-bit stripes.
236:         wire rd_en_drm = !(empty_drm | almost_full_out | local_rst);
237:         ov5640_ddr_fifo_DRM ov5640_ddr_fifo_DRM (
238:           .clk(axi_clk),                      // input
239:           .rst(local_rst),                      // input
240:           .wr_en(wr_en),                  // input
241:           .wr_data(din),              // input [31:0]
242:           .wr_full(full),              // output
243:           
244:           .rd_en(rd_en_drm),                  // input
245:           .rd_data(dout_drm),              // output [127:0]
246:           .rd_empty(empty_drm),            // output
247: 
248:           .almost_full(almost_full_drm),      // output
249:           .almost_empty()     // output
250:         );
251: 
252: 
253:         // reg rd_en_drm_d;
254:         // always @(posedge axi_clk) begin
255:         //     if(axi_rst) begin
256:         //         rd_en_drm_d <= 1'b0;
257:         //     end
258:         //     else begin
259:         //         rd_en_drm_d <= rd_en_drm;  
260:         //     end
261:         // end
262: 
263:         // DRM rd_data is valid one cycle after rd_en. Delay only the write
264:         // enable; dout_drm is aligned with wr_en_drm on that following cycle.
265:         reg wr_en_drm;
266:         always @(posedge axi_clk) begin
267:             if (local_rst) begin
268:                 wr_en_drm <= 1'b0;
269:             end
270:             else begin
271:                 wr_en_drm <= rd_en_drm;
272:             end
273:         end
274: 
275:         wire                     fifo_we  = wr_en_drm;
276:         wire [AXI_DATA_WIDTH-1:0] fifo_wd = dout_drm;
277: 
278:         ov5640_ddr_fifo ov5640_ddr_fifo (
279:           .clk(axi_clk),                      // input
280:           .rst(local_rst),                      // input
281:           .wr_en  (fifo_we ),                  // input
282:           .wr_data(fifo_wd ),              // input [127:0]
283:           .full(out_full),              // output
284:           
285: 
286:           .rd_en(rd_en),                  // input
287:           .rd_data(dout),              // output [127:0]
288:           .empty(empty),            // output
289: 
290:           .almost_full(almost_full_out),      // output
291:           .almost_empty()     // output
292:         );
293: 
294: 
295: 
296: 
297: 
298:     
299:     // Stored credits span BOTH existing FIFOs and the DRM read pipeline.
300:     // Count accepted 32-bit writes minus consumed AXI words; no new storage.
301:     // Counting only the 16-deep output FIFO would deadlock at almost_full=15
302:     // when the input is sparse and no DRM read is pending to fill slot 16.
303:     localparam CREDIT_WORDS_PER_BEAT = AXI_DATA_WIDTH / 32;
304:     reg [12:0] stored_words;
305:     always @(posedge axi_clk) begin
306:         if(local_rst) stored_words <= 0;
307:         else case ({(wr_en && !full), rd_en})
308:             2'b10: stored_words <= stored_words + 1'b1;
309:             2'b01: stored_words <= stored_words - CREDIT_WORDS_PER_BEAT;
310:             2'b11: stored_words <= stored_words - (CREDIT_WORDS_PER_BEAT-1);
311:             default: stored_words <= stored_words;
312:         endcase
313:     end
314:     assign axi_data_available = local_rst ? 16'd0 :
315:                                 stored_words / CREDIT_WORDS_PER_BEAT;
316:     assign capture_overflow = !local_rst && ((wr_en && full) || (fifo_we && out_full));
317:     assign dbg_axi_cnt = axi_cnt;
318:     assign dbg_axi_num = axi_num;
319: 
320:     // [ZDIAG 2026-09-18] zero-beat accounting for the stripe hunt.
321:     reg [31:0] zdin_cnt, zout_cnt;
322:     reg [31:0] zdin_lat, zout_lat;
323:     always @(posedge axi_clk) begin
324:         if (axi_rst) begin
325:             zdin_cnt <= 32'd0;
326:             zout_cnt <= 32'd0;
327:             zdin_lat <= 32'd0;
328:             zout_lat <= 32'd0;
329:         end
330:         else begin
331:             if (wr_en   && (din      == {32{1'b0}})) zdin_cnt <= zdin_cnt + 32'd1;
332:             if (fifo_we && (fifo_wd  == {AXI_DATA_WIDTH{1'b0}})) zout_cnt <= zout_cnt + 32'd1;
333:             if (s_vsync) begin
334:                 zdin_lat <= zdin_cnt;
335:                 zout_lat <= zout_cnt;
336:                 zdin_cnt <= 32'd0;
337:                 zout_cnt <= 32'd0;
338:             end
339:         end
340:     end
341:     assign dbg_zdin = zdin_lat;
342:     assign dbg_zout = zout_lat;
343: 
344: endmodule
