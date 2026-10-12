1: //////////////////////////////////////////////////////////////////////////////
2: //
3: // Copyright (c) 2019 PANGO MICROSYSTEMS, INC
4: // ALL RIGHTS REVERVED.
5: //
6: // THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
7: // IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
8: // PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
9: //
10: //////////////////////////////////////////////////////////////////////////////
11: //
12: // Library:
13: // Filename:ips2l_pcie_dma_controller.v
14: //////////////////////////////////////////////////////////////////////////////
15: module fpga_v8_pcie_dma_controller_h2f #(
16:     parameter                           DEVICE_TYPE = 3'd0      ,   //3'd0:EP,3'd1:Legacy EP,3'd4:RC
17:     parameter                           ADDR_WIDTH  = 4'd10
18: )(
19:     input                               clk                     ,   //gen1:62.5MHz,gen2:125MHz
20:     input                               rst_n                   ,
21: 
22:     /////
23:     input                               i_mwr_tx_busy           , // [\xe6\x96\xb0\xe5\xa2\x9e]
24:     input                               i_mrd_rx_busy           , // [\xe6\x96\xb0\xe5\xa2\x9e]
25:     output  reg                         o_fpga_msi              ,  // [\xe6\x96\xb0\xe5\xa2\x9e]
26:     //**********************************************************************
27:     //bar1 wr interface
28:     input                               i_bar1_wr_en            ,
29:     input           [ADDR_WIDTH-1:0]    i_bar1_wr_addr          ,
30:     input           [127:0]             i_bar1_wr_data          ,
31:     input           [15:0]              i_bar1_wr_byte_en       ,
32:     //**********************************************************************
33:     //apb interface
34:     input                               i_apb_psel              ,
35:     input           [9:0]               i_apb_paddr             ,
36:     input           [31:0]              i_apb_pwdata            ,
37:     input           [3:0]               i_apb_pstrb             ,
38:     input                               i_apb_pwrite            ,
39:     input                               i_apb_penable           ,
40:     output  reg                         o_apb_prdy              ,
41:     output  reg     [31:0]              o_apb_prdata            ,
42:     //**********************************************************************
43:     output  reg                         o_user_define_data_flag ,
44: 
45:     //**********************************************************************
46:     //to tx
47:     output  reg                         o_mwr32_req             ,
48:     input                               i_mwr32_req_ack         ,
49:     output  reg                         o_mwr64_req             ,
50:     input                               i_mwr64_req_ack         ,
51: 
52:     output  reg                         o_mrd32_req             ,
53:     input                               i_mrd32_req_ack         ,
54:     output  reg                         o_mrd64_req             ,
55:     input                               i_mrd64_req_ack         ,
56:     output  reg     [9:0]               o_req_length            ,
57:     output  reg     [63:0]              o_req_addr              ,
58:     output  reg     [31:0]              o_req_data              ,
59: 
60: 
61:     input           [63:0]              i_dma_check_result      ,
62:     output  wire                        o_tx_restart            ,
63:     output  reg                         o_cross_4kb_boundary    ,
64: 
65: 
66:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe4\xb8\x93\xe9\x97\xa8\xe8\xbe\x93\xe5\x87\xba\xe7\xbb\x99 DDR3 \xe8\xaf\xbb\xe5\x86\x99\xe6\x8e\xa7\xe5\x88\xb6\xe9\x80\xbb\xe8\xbe\x91\xe7\x9a\x84\xe8\xb5\xb7\xe5\xa7\x8b\xe5\x9c\xb0\xe5\x9d\x80
67:     output  reg     [31:0]              o_ddr3_addr             ,
68:     output  reg     [31:0]              o_ddr3_length           ,
69:     output  reg     [31:0]              o_ddr3_total_length
70: 
71: );
72: //apb register for rc
73: reg     [31:0]      apb_cmd_reg;
74: reg     [31:0]      apb_cmd_length;
75: reg     [31:0]      apb_cmd_l_addr;
76: reg     [31:0]      apb_cmd_h_addr;
77: reg     [31:0]      apb_cmd_data;
78: 
79: reg     [31:0]      apb_pwdata;
80: 
81: reg                 apb_cmd_reg_vld;
82: reg                 apb_cmd_length_vld;
83: reg                 apb_cmd_l_addr_vld;
84: reg                 apb_cmd_h_addr_vld;
85: reg                 apb_cmd_data_vld;
86: 
87: reg                 apb_ctrl_cfg_done;
88: reg                 apb_length_cfg_done;
89: reg                 apb_l_addr_cfg_done;
90: reg                 apb_h_addr_cfg_done;
91: reg                 apb_data_cfg_done;
92: 
93: // [\xe6\x96\xb0\xe5\xa2\x9e] DDR3 address register for RC
94: reg     [31:0]      apb_ddr3_addr;
95: reg                 apb_ddr3_addr_vld;
96: reg                 apb_ddr3_addr_cfg_done;
97: 
98: 
99: //mwr register for ep
100: reg     [31:0]      dma_cmd_reg;
101: reg     [31:0]      dma_cmd_l_addr;
102: reg     [31:0]      dma_cmd_h_addr;
103: 
104: reg     [31:0]      dma_wr_data;
105: 
106: reg                 dma_cmd_reg_vld;
107: reg                 dma_cmd_l_addr_vld;
108: reg                 dma_cmd_h_addr_vld;
109: 
110: reg                 dma_ctrl_cfg_done  ;
111: reg                 dma_l_addr_cfg_done;
112: reg                 dma_h_addr_cfg_done;
113: 
114: // [\xe6\x96\xb0\xe5\xa2\x9e] DDR3 address register for EP
115: reg     [31:0]      dma_ddr3_addr;
116: reg                 dma_ddr3_addr_vld;
117: reg                 dma_ddr3_addr_cfg_done;
118: 
119: // [\xe6\x96\xb0\xe5\xa2\x9e] Chunk Loop FSM \xe5\x86\x85\xe9\x83\xa8\xe4\xbf\xa1\xe5\x8f\xb7
120: reg [31:0] h2f_chunk_host_high;
121: reg     [31:0]      dma_total_length;
122: reg                 dma_total_length_vld;
123: reg                 dma_total_length_cfg_done;
124: 
125: reg     [31:0]      apb_total_length;
126: reg                 apb_total_length_vld;
127: reg                 apb_total_length_cfg_done;
128: 
129: // [\xe6\x96\xb0\xe5\xa2\x9e] cfg_done \xe9\x87\x8d\xe7\xbd\xae\xe5\x90\x8e\xe7\xab\x8b\xe5\x8d\xb3\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d\xe9\x80\xbb\xe8\xbe\x91
130: reg                 chunk_done_d1;      // chunk_done \xe5\xbb\xb6\xe8\xbf\x9f\xe4\xb8\x80\xe6\x8b\x8d
131: reg                 chunk_done_1shot;   // chunk_done \xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf\xe5\x8d\x95\xe5\x91\xa8\xe6\x9c\x9f\xe8\x84\x89\xe5\x86\xb2
132: 
133: wire                user_define_data_flag;
134: wire                dma_32_64_addr_cmd_flag;
135: wire                dma_wr_rd_cmd_flag;
136: 
137: wire                ack_rcv;
138: 
139: wire                device_rc;
140: wire                device_ep;
141: 
142: wire                apb_write;
143: wire                apb_read;
144: 
145: wire                cmd_reg_cfg_done;
146: wire                l_addr_cfg_done;
147: wire                h_addr_cfg_done;
148: // [\xe6\x96\xb0\xe5\xa2\x9e]
149: wire                ddr3_addr_cfg_done;
150: 
151: wire                mwr32_req_vld;
152: wire                mwr64_req_vld;
153: wire                mrd32_req_vld;
154: wire                mrd64_req_vld;
155: 
156: //4KB boundary
157: wire    [12:0]      req_l_addr;
158: wire    [12:0]      total_data;
159: wire    [12:0]      target_addr;
160: wire                cross_4kb_boundary;
161: //dma check
162: wire                dma_check_success;
163: 
164: assign device_rc = (DEVICE_TYPE == 3'b100 ) ? 1'b1 : 1'b0;
165: assign device_ep = (DEVICE_TYPE == 3'b000 || DEVICE_TYPE == 3'b001) ? 1'b1 : 1'b0;
166: 
167: //req_ack
168: assign ack_rcv = i_mwr32_req_ack | i_mwr64_req_ack | i_mrd32_req_ack | i_mrd64_req_ack;
169: 
170: //********************************************************************dma controller register*********************************************************************
171: //dma_wr_data
172: always@(posedge clk or negedge rst_n)
173: begin
174:     if(!rst_n)
175:         dma_wr_data <= 32'b0;
176:     else
177:         dma_wr_data <= i_bar1_wr_data[31:0];
178: end
179: 
180: //dma_cmd_reg_vld
181: always@(posedge clk or negedge rst_n)
182: begin
183:     if(!rst_n)
184:         dma_cmd_reg_vld <= 1'b0;
185:     else if(dma_cmd_reg_vld)
186:         dma_cmd_reg_vld <= 1'b0;
187:     else
188:         dma_cmd_reg_vld <= &i_bar1_wr_byte_en && i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 9'h100);
189: end
190: 
191: always@(posedge clk or negedge rst_n)
192: begin
193:     if(!rst_n)
194:         dma_cmd_reg <= 32'd0;
195:     else if(dma_cmd_reg_vld)
196:         dma_cmd_reg <= dma_wr_data;
197: end
198: 
199: always@(posedge clk or negedge rst_n)
200: begin
201:     if(!rst_n)
202:         dma_ctrl_cfg_done <= 1'b0;
203:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
204:         dma_ctrl_cfg_done <= 1'b0;
205:     else if(dma_cmd_reg_vld)
206:         dma_ctrl_cfg_done <= 1'b1;
207:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d\xef\xbc\x8c\xe6\x97\xa0\xe9\x9c\x80\xe9\xa9\xb1\xe5\x8a\xa8\xe5\x86\x8d\xe6\xac\xa1\xe5\x86\x99\xe5\x85\xa5
208:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
209:         dma_ctrl_cfg_done <= 1'b1;
210: end
211: 
212: //dma_cmd_l_addr
213: always@(posedge clk or negedge rst_n)
214: begin
215:     if(!rst_n)
216:         dma_cmd_l_addr_vld <= 1'b0;
217:     else if(dma_cmd_l_addr_vld)
218:         dma_cmd_l_addr_vld <= 1'b0;
219:     else
220:         dma_cmd_l_addr_vld <= &i_bar1_wr_byte_en && i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 9'h110);
221: end
222: 
223: always@(posedge clk or negedge rst_n)
224: begin
225:     if(!rst_n)
226:         dma_cmd_l_addr <= 32'd0;
227:     else if(dma_cmd_l_addr_vld)
228:         dma_cmd_l_addr <= dma_wr_data;
229: end
230: 
231: //l_addr_cfg_done
232: always@(posedge clk or negedge rst_n)
233: begin
234:     if(!rst_n)
235:         dma_l_addr_cfg_done <= 1'b0;
236:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
237:         dma_l_addr_cfg_done <= 1'b0;
238:     else if(dma_cmd_l_addr_vld)
239:         dma_l_addr_cfg_done <= 1'b1;
240:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
241:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
242:         dma_l_addr_cfg_done <= 1'b1;
243: end
244: 
245: //dma_cmd_h_addr
246: always@(posedge clk or negedge rst_n)
247: begin
248:     if(!rst_n)
249:         dma_cmd_h_addr_vld <= 1'b0;
250:     else if(dma_cmd_l_addr_vld)
251:         dma_cmd_h_addr_vld <= 1'b0;
252:     else
253:         dma_cmd_h_addr_vld <= &i_bar1_wr_byte_en && i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 9'h120);
254: end
255: 
256: always@(posedge clk or negedge rst_n)
257: begin
258:     if(!rst_n)
259:         dma_cmd_h_addr <= 32'd0;
260:     else if(dma_cmd_h_addr_vld)
261:         dma_cmd_h_addr <= dma_wr_data;
262: end
263: 
264: always@(posedge clk or negedge rst_n)
265: begin
266:     if(!rst_n)
267:         dma_h_addr_cfg_done <= 1'b0;
268:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
269:         dma_h_addr_cfg_done <= 1'b0;
270:     else if(dma_cmd_h_addr_vld)
271:         dma_h_addr_cfg_done <= 1'b1;
272:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
273:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
274:         dma_h_addr_cfg_done <= 1'b1;
275: end
276: 
277: 
278: 
279: //DDR3 addr
280: // [\xe6\x96\xb0\xe5\xa2\x9e] dma_ddr3_addr (EP\xe6\xa8\xa1\xe5\xbc\x8f\xe5\x86\x99\xe5\x85\xa5 9'h1E0)
281: always@(posedge clk or negedge rst_n)
282: begin
283:     if(!rst_n)
284:         dma_ddr3_addr_vld <= 1'b0;
285:     else if(dma_ddr3_addr_vld)
286:         dma_ddr3_addr_vld <= 1'b0;
287:     else
288:         dma_ddr3_addr_vld <= &i_bar1_wr_byte_en && i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 9'h1E0);
289: end
290: 
291: always@(posedge clk or negedge rst_n)
292: begin
293:     if(!rst_n)
294:         dma_ddr3_addr <= 32'd0;
295:     else if(dma_ddr3_addr_vld)
296:         dma_ddr3_addr <= dma_wr_data;
297: end
298: 
299: always@(posedge clk or negedge rst_n)
300: begin
301:     if(!rst_n)
302:         dma_ddr3_addr_cfg_done <= 1'b0;
303:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
304:         dma_ddr3_addr_cfg_done <= 1'b0;
305:     else if(dma_ddr3_addr_vld)
306:         dma_ddr3_addr_cfg_done <= 1'b1;
307:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
308:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
309:         dma_ddr3_addr_cfg_done <= 1'b1;
310: end
311: 
312: 
313: // TOTAL_LENGTH (\xe6\x96\xb0\xe5\xa2\x9e) - \xe6\x80\xbb\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0\xef\xbc\x8cCPU\xe5\x86\x99\xe5\x85\xa5\xe5\x90\x8e\xe6\x8e\xa7\xe5\x88\xb6\xe5\x99\xa8\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\x8c\xe6\x88\x90\xe6\x89\x80\xe6\x9c\x89chunk\xe4\xbc\xa0\xe8\xbe\x93
314: // EP\xe6\xa8\xa1\xe5\xbc\x8f: BAR1 0x200
315: always@(posedge clk or negedge rst_n)
316: begin
317:     if(!rst_n)
318:         dma_total_length_vld <= 1'b0;
319:     else if(dma_total_length_vld)
320:         dma_total_length_vld <= 1'b0;
321:     else
322:         dma_total_length_vld <= &i_bar1_wr_byte_en && i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 10'h200);
323: end
324: 
325: always@(posedge clk or negedge rst_n)
326: begin
327:     if(!rst_n)
328:         dma_total_length <= 32'd0;
329:     else if(dma_total_length_vld)
330:         dma_total_length <= dma_wr_data;
331: end
332: 
333: always@(posedge clk or negedge rst_n)
334: begin
335:     if(!rst_n)
336:         dma_total_length_cfg_done <= 1'b0;
337:     else if (ack_rcv)
338:         dma_total_length_cfg_done <= 1'b0;
339:     else if(dma_total_length_vld)
340:         dma_total_length_cfg_done <= 1'b1;
341: end
342: 
343: // APB TOTAL_LENGTH (\xe6\x96\xb0\xe5\xa2\x9e) - RC\xe6\xa8\xa1\xe5\xbc\x8f: APB 0x1A0
344: always@(posedge clk or negedge rst_n)
345: begin
346:     if(!rst_n)
347:         apb_total_length_vld <= 1'b0;
348:     else if(apb_total_length_vld)
349:         apb_total_length_vld <= 1'b0;
350:     else
351:         apb_total_length_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h1A0);
352: end
353: 
354: always@(posedge clk or negedge rst_n)
355: begin
356:     if(!rst_n)
357:         apb_total_length <= 32'd0;
358:     else if(apb_total_length_vld)
359:         apb_total_length <= apb_pwdata;
360: end
361: 
362: always@(posedge clk or negedge rst_n)
363: begin
364:     if(!rst_n)
365:         apb_total_length_cfg_done <= 1'b0;
366:     else if (ack_rcv)
367:         apb_total_length_cfg_done <= 1'b0;
368:     else if(apb_total_length_vld)
369:         apb_total_length_cfg_done <= 1'b1;
370: end
371: 
372: //********************************************************************apb controller register*********************************************************************
373: assign apb_write = i_apb_psel && i_apb_penable && i_apb_pwrite;
374: 
375: always@(posedge clk or negedge rst_n)
376: begin
377:     if(!rst_n)
378:         apb_pwdata <= 32'b0;
379:     else
380:         apb_pwdata <= i_apb_pwdata;
381: end
382: //apb_cmd_reg for rc
383: always@(posedge clk or negedge rst_n)
384: begin
385:     if(!rst_n)
386:         apb_cmd_reg_vld <= 1'b0;
387:     else if(apb_cmd_reg_vld)
388:         apb_cmd_reg_vld <= 1'b0;
389:     else
390:         apb_cmd_reg_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h140);
391: end
392: 
393: always@(posedge clk or negedge rst_n)
394: begin
395:     if(!rst_n)
396:         apb_cmd_reg <= 32'd0;
397:     else if(apb_cmd_reg_vld)
398:         apb_cmd_reg <= apb_pwdata;
399: end
400: 
401: always@(posedge clk or negedge rst_n)
402: begin
403:     if(!rst_n)
404:         apb_ctrl_cfg_done <= 1'b0;
405:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
406:         apb_ctrl_cfg_done <= 1'b0;
407:     else if(apb_cmd_reg_vld)
408:         apb_ctrl_cfg_done <= 1'b1;
409:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d\xef\xbc\x8c\xe6\x97\xa0\xe9\x9c\x80\xe9\xa9\xb1\xe5\x8a\xa8\xe5\x86\x8d\xe6\xac\xa1\xe5\x86\x99\xe5\x85\xa5
410:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
411:         apb_ctrl_cfg_done <= 1'b1;
412: end
413: 
414: //apb_cmd_length
415: always@(posedge clk or negedge rst_n)
416: begin
417:     if(!rst_n)
418:         apb_cmd_length_vld <= 1'b0;
419:     else if(apb_cmd_length_vld)
420:         apb_cmd_length_vld <= 1'b0;
421:     else
422:         apb_cmd_length_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h150);
423: end
424: 
425: always@(posedge clk or negedge rst_n)
426: begin
427:     if(!rst_n)
428:         apb_cmd_length <= 32'd0;
429:     else if(apb_cmd_length_vld)
430:         apb_cmd_length <= apb_pwdata;
431: end
432: 
433: always@(posedge clk or negedge rst_n)
434: begin
435:     if(!rst_n)
436:         apb_length_cfg_done <= 1'b0;
437:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
438:         apb_length_cfg_done <= 1'b0;
439:     else if(apb_cmd_length_vld)
440:         apb_length_cfg_done <= 1'b1;
441:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
442:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
443:         apb_length_cfg_done <= 1'b1;
444: end
445: 
446: //apb_cmd_l_addr
447: always@(posedge clk or negedge rst_n)
448: begin
449:     if(!rst_n)
450:         apb_cmd_l_addr_vld <= 1'b0;
451:     else if(apb_cmd_l_addr_vld)
452:         apb_cmd_l_addr_vld <= 1'b0;
453:     else
454:         apb_cmd_l_addr_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h160);
455: end
456: 
457: always@(posedge clk or negedge rst_n)
458: begin
459:     if(!rst_n)
460:         apb_cmd_l_addr <= 32'd0;
461:     else if(apb_cmd_l_addr_vld)
462:         apb_cmd_l_addr <= apb_pwdata;
463: end
464: 
465: //apb_l_addr_cfg_done
466: always@(posedge clk or negedge rst_n)
467: begin
468:     if(!rst_n)
469:         apb_l_addr_cfg_done <= 1'b0;
470:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
471:         apb_l_addr_cfg_done <= 1'b0;
472:     else if(apb_cmd_l_addr_vld)
473:         apb_l_addr_cfg_done <= 1'b1;
474:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
475:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
476:         apb_l_addr_cfg_done <= 1'b1;
477: end
478: 
479: //apb_cmd_h_addr
480: always@(posedge clk or negedge rst_n)
481: begin
482:     if(!rst_n)
483:         apb_cmd_h_addr_vld <= 1'b0;
484:     else if(apb_cmd_h_addr_vld)
485:         apb_cmd_h_addr_vld <= 1'b0;
486:     else
487:         apb_cmd_h_addr_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h170);
488: end
489: 
490: always@(posedge clk or negedge rst_n)
491: begin
492:     if(!rst_n)
493:         apb_cmd_h_addr <= 32'd0;
494:     else if(apb_cmd_h_addr_vld)
495:         apb_cmd_h_addr <= apb_pwdata;
496: end
497: 
498: always@(posedge clk or negedge rst_n)
499: begin
500:     if(!rst_n)
501:         apb_h_addr_cfg_done <= 1'b0;
502:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
503:         apb_h_addr_cfg_done <= 1'b0;
504:     else if(apb_cmd_h_addr_vld)
505:         apb_h_addr_cfg_done <= 1'b1;
506:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
507:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
508:         apb_h_addr_cfg_done <= 1'b1;
509: end
510: 
511: //apb_cmd_data
512: always@(posedge clk or negedge rst_n)
513: begin
514:     if(!rst_n)
515:         apb_cmd_data_vld <= 1'b0;
516:     else if(apb_cmd_data_vld)
517:         apb_cmd_data_vld <= 1'b0;
518:     else
519:         apb_cmd_data_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h180);
520: end
521: 
522: always@(posedge clk or negedge rst_n)
523: begin
524:     if(!rst_n)
525:         apb_cmd_data <= 32'd0;
526:     else if(apb_cmd_data_vld)
527:         apb_cmd_data <= apb_pwdata;
528: end
529: 
530: always@(posedge clk or negedge rst_n)
531: begin
532:     if(!rst_n)
533:         apb_data_cfg_done <= 1'b0;
534:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
535:         apb_data_cfg_done <= 1'b0;
536:     else if(apb_cmd_data_vld)
537:         apb_data_cfg_done <= 1'b1;
538: end
539: 
540: 
541: // [\xe6\x96\xb0\xe5\xa2\x9e] apb_ddr3_addr (RC\xe6\xa8\xa1\xe5\xbc\x8f\xe5\x86\x99\xe5\x85\xa5 9'h1C0)
542: always@(posedge clk or negedge rst_n)
543: begin
544:     if(!rst_n)
545:         apb_ddr3_addr_vld <= 1'b0;
546:     else if(apb_ddr3_addr_vld)
547:         apb_ddr3_addr_vld <= 1'b0;
548:     else
549:         apb_ddr3_addr_vld <= &i_apb_pstrb && apb_write && (i_apb_paddr == 9'h1C0);
550: end
551: 
552: always@(posedge clk or negedge rst_n)
553: begin
554:     if(!rst_n)
555:         apb_ddr3_addr <= 32'd0;
556:     else if(apb_ddr3_addr_vld)
557:         apb_ddr3_addr <= apb_pwdata;
558: end
559: 
560: always@(posedge clk or negedge rst_n)
561: begin
562:     if(!rst_n)
563:         apb_ddr3_addr_cfg_done <= 1'b0;
564:     else if (ack_rcv || cross_4kb_boundary || chunk_done_1shot)
565:         apb_ddr3_addr_cfg_done <= 1'b0;
566:     else if(apb_ddr3_addr_vld)
567:         apb_ddr3_addr_cfg_done <= 1'b1;
568:     // [\xe4\xbf\xae\xe5\xa4\x8d] \xe4\xb8\xad\xe9\x97\xb4chunk\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe8\x87\xaa\xe5\x8a\xa8\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d
569:     else if(chunk_done && chunk_loop_active && !is_final_chunk)
570:         apb_ddr3_addr_cfg_done <= 1'b1;
571: end
572: 
573: 
574: assign cmd_reg_cfg_done = (device_ep && dma_ctrl_cfg_done)   || (device_rc && apb_ctrl_cfg_done);
575: 
576: assign l_addr_cfg_done  = (device_ep && dma_l_addr_cfg_done) || (device_rc && apb_l_addr_cfg_done);
577: 
578: assign h_addr_cfg_done  = (device_ep && dma_h_addr_cfg_done) || (device_rc && apb_h_addr_cfg_done);
579: 
580: // DDR3 addr \xe5\x92\x8c total_length \xe7\x9a\x84 cfg_done \xe7\xbb\xbc\xe5\x90\x88
581: assign ddr3_addr_cfg_done = (device_ep && dma_ddr3_addr_cfg_done) || (device_rc && apb_ddr3_addr_cfg_done);
582: 
583: //********************************************************************************************************************************
584: // Chunk Loop FSM internal working registers (\xe6\x96\xb0\xe5\xa2\x9e)
585: // Tracks remaining bytes, current addresses, and chunk count for automatic multi-chunk DMA
586: // Chunk FSM: \xe5\xb0\x86 total_length \xe8\x87\xaa\xe5\x8a\xa8\xe6\x8b\x86\xe5\x88\x86\xe4\xb8\xba\xe5\xa4\x9a\xe4\xb8\xaa chunk\xef\xbc\x8c\xe6\xaf\x8f\xe6\xac\xa1\xe6\x9c\x80\xe5\xa4\xa7 4092 \xe5\xad\x97\xe8\x8a\x82\xef\xbc\x88\xe4\xb8\x8d\xe8\xb6\x85\xe8\xbf\x87 PCIe 4KB \xe5\x9c\xb0\xe5\x9d\x80\xe8\xbe\xb9\xe7\x95\x8c\xef\xbc\x89
587: // PCIe \xe8\xa6\x81\xe6\xb1\x82\xe5\x8d\x95\xe4\xb8\xaa TLP \xe7\x9a\x84\xe8\xb5\xb7\xe5\xa7\x8b\xe5\x9c\xb0\xe5\x9d\x80 + Length \xe4\xb8\x8d\xe8\x83\xbd\xe8\xb7\xa8 4KB \xe8\xbe\xb9\xe7\x95\x8c\xef\xbc\x9a
588: //   - \xe4\xb8\xbb\xe6\x9c\xba\xe5\x9c\xb0\xe5\x9d\x80\xe4\xbd\x8e 12 \xe4\xbd\x8d = x\xef\xbc\x8cchunk \xe6\x9c\x80\xe5\xa4\xa7\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0 = 4096 - x
589: //   - \xe4\xb8\xba\xe7\xae\x80\xe5\x8c\x96\xef\xbc\x8c\xe5\x9b\xba\xe5\xae\x9a\xe6\xaf\x8f\xe4\xb8\xaa chunk \xe6\x9c\x80\xe5\xa4\xa7 4092 \xe5\xad\x97\xe8\x8a\x82\xef\xbc\x881022 DWs\xef\xbc\x89\xef\xbc\x8c\xe7\xbb\x9d\xe5\xaf\xb9\xe4\xb8\x8d\xe8\xb7\xa8\xe8\xbe\xb9\xe7\x95\x8c
590: localparam CHUNK_SIZE_LOG2 = 12;  // log2(4096)
591: localparam CHUNK_SIZE_MAX  = 32'd4096;  // 1022 DWs < 1024 (max TLP DW), \xe4\xb8\x8d\xe4\xbc\x9a\xe8\xa7\xa6\xe5\x8f\x91 cross_4kb_boundary
592: 
593: reg  [31:0]  chunk_rem_bytes;    // remaining bytes to transfer
594: reg  [31:0]  chunk_host_addr;    // current host DMA address (accumulated)
595: reg  [31:0]  chunk_ddr3_addr;    // current DDR3 address (accumulated)
596: reg  [15:0]  chunk_count;        // number of chunks already completed
597: reg          chunk_loop_active;  // asserted while chunk loop is in progress
598: reg          chunk_first_write;  // first CMD_REG write (before total_length was set)
599: 
600: // chunk_done: one-shot pulse asserted when a single chunk TLP transfer finishes
601: // (recognized by the falling edge of i_mwr_tx_busy / i_mrd_rx_busy)
602: // For the last chunk: we DO NOT re-assert cmd_reg_cfg_done, so the controller
603: // stays idle and chunk_loop_done = 1 -> MSI fires once.
604: // For intermediate chunks: cmd_reg_cfg_done is re-asserted to accept the next CMD_REG write.
605: wire         chunk_done;
606: wire         chunk_loop_done;    // all chunks finished -> triggers MSI
607: wire         is_last_chunk;
608: 
609: // Size of the current chunk (may be smaller for the final partial chunk or when near 4KB boundary)
610: // PCIe 4KB boundary rule: single TLP cannot cross a 4KB boundary
611: //   chunk_cur_size = min(remaining_bytes, 4096 - host_addr[11:0])
612: //   \xe6\xb3\xa8\xe6\x84\x8f: \xe5\xbd\x93 host_addr[11:0] == 0 (4KB\xe5\xaf\xb9\xe9\xbd\x90) \xe6\x97\xb6, "\xe5\x88\xb0\xe8\xbe\xb9\xe7\x95\x8c\xe7\x9a\x84\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0" = 4096
613: wire         chunk_near_boundary;
614: wire [31:0]  chunk_boundary_limit;
615: wire [31:0]  chunk_cur_size;
616: assign chunk_near_boundary  = (chunk_host_addr[11:0] != 12'd0);  // 1=\xe6\x9c\xaa\xe5\xaf\xb9\xe9\xbd\x90, 0=4KB\xe5\xaf\xb9\xe9\xbd\x90
617: assign chunk_boundary_limit = chunk_near_boundary ?
618:                               (32'h1000 - {20'd0, chunk_host_addr[11:0]}) :  // \xe6\x9c\xaa\xe5\xaf\xb9\xe9\xbd\x90: 4096 - offset
619:                               32'h1000;                                       // \xe5\xaf\xb9\xe9\xbd\x90: \xe6\x9c\x80\xe5\xa4\xa74096
620: wire [31:0] h2f_chunk_capacity = (chunk_boundary_limit < CHUNK_SIZE_MAX) ? chunk_boundary_limit : CHUNK_SIZE_MAX;
621: wire [31:0] h2f_chunk_size = (chunk_rem_bytes < h2f_chunk_capacity) ? chunk_rem_bytes : h2f_chunk_capacity;
622: // CMD is latched on this same edge. Select its incoming direction for the
623: // first length, keeping F2H outputs identical from command acceptance onward.
624: wire h2f_length_cmd_is_write = (device_ep && dma_cmd_reg_vld) ? dma_wr_data[24] :
625:     (device_rc && apb_cmd_reg_vld) ? apb_pwdata[24] : dma_wr_rd_cmd_flag;
626: assign chunk_cur_size = !dma_wr_rd_cmd_flag ? h2f_chunk_size :
627:     ((chunk_rem_bytes[31:CHUNK_SIZE_LOG2] == 0) ? chunk_rem_bytes : CHUNK_SIZE_MAX);
628: assign is_last_chunk = !dma_wr_rd_cmd_flag ? (chunk_rem_bytes <= chunk_cur_size) :
629:                                            (chunk_rem_bytes <= CHUNK_SIZE_MAX);
630: wire [32:0] h2f_host_low_next = {1'b0,chunk_host_addr}+{1'b0,chunk_cur_size};
631: always @(posedge clk or negedge rst_n) begin
632:     if (!rst_n) h2f_chunk_host_high <= 0;
633:     else if (total_length_cfg_done)
634:         h2f_chunk_host_high <= device_ep ? dma_cmd_h_addr : apb_cmd_h_addr;
635:     else if (chunk_done && chunk_loop_active && !dma_wr_rd_cmd_flag)
636:         h2f_chunk_host_high <= h2f_chunk_host_high + h2f_host_low_next[32];
637: end
638: 
639: // Initialize internal chunk variables on TOTAL_LENGTH write
640: // Update them on each chunk boundary
641: always @(posedge clk or negedge rst_n) begin
642:     if (!rst_n) begin
643:         chunk_rem_bytes   <= 32'd0;
644:         chunk_host_addr   <= 32'd0;
645:         chunk_ddr3_addr   <= 32'd0;
646:         chunk_count        <= 16'd0;
647:         chunk_loop_active  <= 1'b0;
648:         chunk_first_write  <= 1'b0;
649:     end else if (total_length_cfg_done) begin
650:         // CPU has written TOTAL_LENGTH -> initialize for first chunk
651:         chunk_rem_bytes   <= device_ep ? dma_total_length : apb_total_length;
652:         chunk_host_addr   <= device_ep ? dma_cmd_l_addr   : apb_cmd_l_addr;
653:         chunk_ddr3_addr   <= device_ep ? dma_ddr3_addr    : apb_ddr3_addr;
654:         chunk_count        <= 16'd0;
655:         chunk_loop_active  <= 1'b1;
656:         chunk_first_write  <= 1'b1;
657:     end else if (chunk_done && chunk_loop_active) begin
658:         // Advance to next chunk
659:         chunk_rem_bytes   <= chunk_rem_bytes - chunk_cur_size;
660:         chunk_host_addr   <= chunk_host_addr + chunk_cur_size;
661:         chunk_ddr3_addr   <= chunk_ddr3_addr + chunk_cur_size;
662:         chunk_count        <= chunk_count + 16'd1;
663:         chunk_first_write  <= 1'b0;
664:         // If this was the last chunk, exit loop
665:         if (is_last_chunk)
666:             chunk_loop_active <= 1'b0;
667:     end else begin
668:         chunk_first_write <= 1'b0;
669:     end
670: end
671: 
672: 
673: // o_ddr3_addr: first chunk uses register value; subsequent chunks use accumulated value
674: always @(posedge clk or negedge rst_n) begin
675:     if (!rst_n)
676:         o_ddr3_total_length <= 32'd0;
677:     else if (dma_total_length_cfg_done)
678:         o_ddr3_total_length <= device_ep ? dma_total_length : apb_total_length;
679: end
680: 
681: 
682: // o_ddr3_addr: first chunk uses register value; subsequent chunks use accumulated value
683: always @(posedge clk or negedge rst_n) begin
684:     if (!rst_n)
685:         o_ddr3_addr <= 32'd0;
686:     else if (ddr3_addr_cfg_done && !chunk_loop_active)
687:         o_ddr3_addr <= device_ep ? dma_ddr3_addr : apb_ddr3_addr;
688:     else if (chunk_done_d1 && chunk_loop_active && !is_final_chunk_d1)
689:         o_ddr3_addr <= chunk_ddr3_addr;
690: end
691: 
692: // o_ddr3_length: \xe5\xae\x8c\xe5\x85\xa8\xe7\x94\xb1 total_length \xe5\x92\x8c chunk FSM \xe6\x8e\xa8\xe5\xaf\xbc\xef\xbc\x88\xe4\xb8\x8d\xe5\x86\x8d\xe4\xbe\x9d\xe8\xb5\x96\xe5\xa4\x96\xe9\x83\xa8 ddr3_length \xe5\xaf\x84\xe5\xad\x98\xe5\x99\xa8\xef\xbc\x89
693: // \xe7\xad\x89\xe4\xbb\xb7\xe4\xba\x8e min(total_length, CHUNK_SIZE_MAX)\xef\xbc\x8c\xe7\x94\xb1 total_length_cfg_done \xe5\x88\x9d\xe5\xa7\x8b\xe5\x8c\x96\xef\xbc\x8c\xe5\x90\x8e\xe7\xbb\xad\xe7\x94\xb1 chunk FSM \xe6\x9b\xb4\xe6\x96\xb0
694: wire [31:0] total_length_val;
695: assign total_length_val = device_ep ? dma_total_length : apb_total_length;
696: always @(posedge clk or negedge rst_n) begin
697:     if (!rst_n)
698:         o_ddr3_length <= 32'd0;    
699:     else if (chunk_done_d1 && chunk_loop_active && !is_final_chunk_d1)
700:         o_ddr3_length <= chunk_cur_size;
701:     else if (total_length_cfg_done)
702:         o_ddr3_length <= !h2f_length_cmd_is_write ? h2f_chunk_size :
703:             ((total_length_val <= CHUNK_SIZE_MAX) ? total_length_val : CHUNK_SIZE_MAX);
704: end
705: 
706: // o_req_addr: first chunk uses register value; subsequent chunks use accumulated host address
707: always @(posedge clk or negedge rst_n) begin
708:     if (!rst_n)
709:         o_req_addr[31:0] <= 32'd0;    
710:     else if (l_addr_cfg_done && !chunk_loop_active)
711:         o_req_addr[31:0] <= device_ep ? dma_cmd_l_addr : apb_cmd_l_addr;
712:     else if (chunk_done_d1 && chunk_loop_active && !is_final_chunk_d1)
713:         o_req_addr[31:0] <= chunk_host_addr;
714: end
715: 
716: // o_req_length: \xe7\x9b\xb4\xe6\x8e\xa5\xe7\xad\x89\xe4\xba\x8e\xe8\xa6\x81\xe4\xbc\xa0\xe8\xbe\x93\xe7\x9a\x84 DW \xe6\x95\xb0\xef\xbc\x8c\xe5\x90\x8e\xe7\xbb\xad DMA \xe5\xbc\x95\xe6\x93\x8e\xe6\x8c\x89\xe5\x8e\x9f\xe5\x80\xbc\xe4\xbd\xbf\xe7\x94\xa8\xef\xbc\x88\xe6\x97\xa0 +1\xef\xbc\x89
717: //   \xe7\xac\xac\xe4\xb8\x80\xe4\xb8\xaa chunk: \xe9\xa9\xb1\xe5\x8a\xa8\xe5\x86\x99\xe5\x85\xa5\xe7\x9a\x84\xe6\x98\xaf (DW\xe6\x95\xb0-1)\xef\xbc\x8c\xe6\x89\x80\xe4\xbb\xa5\xe8\xa6\x81 +1
718: //   \xe5\x90\x8e\xe7\xbb\xad chunk:   chunk_cur_size/4 \xe7\x9b\xb4\xe6\x8e\xa5\xe6\x98\xaf DW \xe6\x95\xb0
719: // \xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80\xe5\x8c\x85: chunk_done_d1\xe6\x97\xb6\xe5\x88\xbb\xef\xbc\x8cchunk_cur_size\xe5\xb7\xb2\xe6\x98\xaf\xe6\xad\xa3\xe7\xa1\xae\xe5\x80\xbc\xef\xbc\x8cis_final_chunk_d1\xe8\xae\xb0\xe5\xbd\x95"\xe5\x88\x9a\xe5\xae\x8c\xe6\x88\x90\xe7\x9a\x84\xe6\x98\xaf\xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80\xe5\x8c\x85"
720: always @(posedge clk or negedge rst_n) begin
721:     if (!rst_n)
722:         o_req_length <= 10'd0;
723:     else if (chunk_done_d1 && chunk_loop_active && !is_final_chunk_d1) begin
724:         o_req_length <= !dma_wr_rd_cmd_flag ? ((chunk_cur_size+32'd3)>>2) : {1'b0, chunk_cur_size[11:2]};  // chunk_cur_size/4 = DW \xe6\x95\xb0
725:     end
726:     else if (cmd_reg_cfg_done) begin
727:         if (!dma_wr_rd_cmd_flag && chunk_loop_active)
728:             o_req_length <= ((chunk_cur_size+32'd3)>>2);
729:         else if (device_ep)
730:             o_req_length <= dma_cmd_reg[9:0]; // \xe9\xa9\xb1\xe5\x8a\xa8\xe5\x86\x99\xe7\x9a\x84\xe6\x98\xaf DW
731:         else if (device_rc && apb_length_cfg_done)
732:             o_req_length <= apb_cmd_length[9:0];       // RC \xe5\x86\x99\xe7\x9a\x84\xe6\x98\xaf DW \xe6\x95\xb0
733:     end
734:     
735: end
736: 
737: assign chunk_done     = (tx_done_pulse && tx_active) || (rx_done_pulse && rx_active);
738: assign chunk_loop_done = chunk_done && chunk_loop_active && is_last_chunk;
739: 
740: // chunk_done_d1: delayed version of chunk_done for edge detection
741: // chunk_done_1shot: rising edge one-shot pulse of chunk_done
742: always @(posedge clk or negedge rst_n) begin
743:     if (!rst_n) begin
744:         chunk_done_d1    <= 1'b0;
745:         chunk_done_1shot <= 1'b0;
746:     end else begin
747:         chunk_done_d1    <= chunk_done;
748:         chunk_done_1shot <= chunk_done && !chunk_done_d1;  // rising edge of chunk_done
749:     end
750: end
751: 
752: assign total_length_cfg_done = (device_ep && dma_total_length_cfg_done) || (device_rc && apb_total_length_cfg_done);
753: 
754: //********************************************************************************************************************************
755: //********************************************************************req information*********************************************************************
756: // o_req_addr_hi: \xe9\x94\x81\xe5\xad\x98\xe9\xab\x98 32 \xe4\xbd\x8d\xef\xbc\x88\xe5\x8f\xaa\xe5\x9c\xa8 DMA \xe5\x90\xaf\xe5\x8a\xa8\xe6\x97\xb6\xe8\xae\xbe\xe7\xbd\xae\xe4\xb8\x80\xe6\xac\xa1\xef\xbc\x8c\xe5\x90\x8e\xe7\xbb\xad chunk \xe4\xbf\x9d\xe6\x8c\x81\xe4\xb8\x8d\xe5\x8f\x98\xef\xbc\x89
757: always @(posedge clk or negedge rst_n) begin
758:     if (!rst_n)
759:         o_req_addr[63:32] <= 32'd0;
760:     else if (!dma_wr_rd_cmd_flag && chunk_loop_active)
761:         o_req_addr[63:32] <= h2f_chunk_host_high;
762:     else if (l_addr_cfg_done)
763:         o_req_addr[63:32] <= device_ep ? dma_cmd_h_addr : apb_cmd_h_addr;
764: end
765: 
766: //o_req_data
767: always@(posedge clk or negedge rst_n)
768: begin
769:     if(!rst_n)
770:         o_req_data <= 32'd0;
771:     else if(apb_data_cfg_done)
772:         o_req_data[31:0]  <= apb_cmd_data;
773: end
774: 
775: 
776: 
777: 
778: // [\xe6\x96\xb0\xe5\xa2\x9e] DDR3 address \xe7\xbb\xbc\xe5\x90\x88 (\xe5\xb7\xb2\xe5\x9c\xa8 Chunk FSM \xe4\xb8\xad\xe5\xae\x9e\xe7\x8e\xb0\xef\xbc\x8c\xe6\xad\xa4\xe5\xa4\x84\xe5\x88\xa0\xe9\x99\xa4\xe4\xbb\xa5\xe9\x81\xbf\xe5\x85\x8d\xe5\x86\xb2\xe7\xaa\x81)
779: 
780: 
781: //******************************************************************tx request*************************************************************************
782: assign user_define_data_flag     = device_rc ? apb_cmd_reg[8]  : 1'b0;  //0:use ram data; 1:use user define data
783: assign dma_32_64_addr_cmd_flag   = device_rc ? apb_cmd_reg[16] : (device_ep ? dma_cmd_reg[16] : 1'b0);  //0:32; 1:64;
784: assign dma_wr_rd_cmd_flag        = device_rc ? apb_cmd_reg[24] : (device_ep ? dma_cmd_reg[24] : 1'b0);  //0:read; 1:write;
785: 
786: always@(posedge clk or negedge rst_n)
787: begin
788:     if(!rst_n)
789:         o_user_define_data_flag <= 1'd0;
790:     else
791:         o_user_define_data_flag <= user_define_data_flag;
792: end
793: 
794: //gen req valid
795: assign mwr32_req_vld = !dma_32_64_addr_cmd_flag &&  dma_wr_rd_cmd_flag && cmd_reg_cfg_done && l_addr_cfg_done && !cross_4kb_boundary;
796: assign mwr64_req_vld =  dma_32_64_addr_cmd_flag &&  dma_wr_rd_cmd_flag && cmd_reg_cfg_done && l_addr_cfg_done && h_addr_cfg_done && !cross_4kb_boundary;
797: assign mrd32_req_vld = !dma_32_64_addr_cmd_flag && !dma_wr_rd_cmd_flag && cmd_reg_cfg_done && l_addr_cfg_done && !cross_4kb_boundary;
798: assign mrd64_req_vld =  dma_32_64_addr_cmd_flag && !dma_wr_rd_cmd_flag && cmd_reg_cfg_done && l_addr_cfg_done && h_addr_cfg_done && !cross_4kb_boundary;
799: 
800: //mwr_32_req
801: always@(posedge clk or negedge rst_n)
802: begin
803:     if(!rst_n)
804:         o_mwr32_req <= 1'b0;
805:     else if(i_mwr32_req_ack)
806:         o_mwr32_req <= 1'b0;
807:     else if(mwr32_req_vld)
808:     begin
809:         if(!user_define_data_flag)              ////\xe8\xbf\x99\xe9\x87\x8c\xe5\xb0\xb1\xe5\x8f\xaf\xe4\xbb\xa5\xe6\x94\xbealmost_full
810:             o_mwr32_req  <= 1'b1;
811:         else if(apb_data_cfg_done)
812:             o_mwr32_req  <= 1'b1;
813:         else
814:             o_mwr32_req  <= 1'b0;
815:     end
816: end
817: 
818: //mwr_64_req
819: always@(posedge clk or negedge rst_n)
820: begin
821:     if(!rst_n)
822:         o_mwr64_req <= 1'b0;
823:     else if(i_mwr64_req_ack)
824:         o_mwr64_req <= 1'b0;
825:     else if(mwr64_req_vld)
826:     begin
827:         if(!user_define_data_flag)
828:             o_mwr64_req  <= 1'b1;
829:         else if(apb_data_cfg_done)
830:             o_mwr64_req  <= 1'b1;
831:         else
832:             o_mwr64_req  <= 1'b0;
833:     end
834: end
835: //mrd_32_req
836: always@(posedge clk or negedge rst_n)
837: begin
838:     if(!rst_n)
839:         o_mrd32_req <= 1'b0;
840:     else if(i_mrd32_req_ack)
841:         o_mrd32_req <= 1'b0;
842:     else if(mrd32_req_vld)
843:         o_mrd32_req  <= 1'b1;
844: end
845: 
846: //mrd_64_req
847: always@(posedge clk or negedge rst_n)
848: begin
849:     if(!rst_n)
850:         o_mrd64_req <= 1'b0;
851:     else if(i_mrd64_req_ack)
852:         o_mrd64_req <= 1'b0;
853:     else if(mrd64_req_vld)
854:         o_mrd64_req  <= 1'b1;
855: end
856: 
857: //**********************************************************************apb_read***************************************************************************
858: // \xe5\x85\xb3\xe9\x94\xae\xe4\xbf\xae\xe5\xa4\x8d: \xe5\x9c\xa8 chunk \xe8\xbe\xb9\xe7\x95\x8c\xe5\xa4\x84, ack_rcv \xe4\xbc\x9a\xe5\xb0\x86\xe6\x89\x80\xe6\x9c\x89 cfg_done \xe6\xb8\x85\xe9\x9b\xb6, \xe5\xaf\xbc\xe8\x87\xb4\xe8\xaf\xb7\xe6\xb1\x82 FSM \xe6\x97\xa0\xe6\xb3\x95
859: // \xe5\x9c\xa8\xe4\xb8\x8b\xe4\xb8\x80\xe4\xb8\xaa\xe5\x91\xa8\xe6\x9c\x9f\xe9\x87\x8d\xe6\x96\xb0\xe5\x8f\x91\xe8\xb5\xb7\xe8\xaf\xb7\xe6\xb1\x82.
860: // \xe8\xa7\xa3\xe5\x86\xb3\xe6\x96\xb9\xe6\xa1\x88: \xe5\xb0\x86 cfg_done \xe7\x9a\x84"\xe9\x87\x8d\xe7\xbd\xae"\xe5\x92\x8c"\xe9\x87\x8d\xe7\xbd\xae\xe5\x90\x8e\xe7\xab\x8b\xe5\x8d\xb3\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d"\xe5\x88\x86\xe6\x88\x90\xe4\xb8\xa4\xe4\xb8\xaa always \xe5\x9d\x97\xe6\x89\xa7\xe8\xa1\x8c.
861: // chunk_done_d1 \xe8\x84\x89\xe5\x86\xb2\xe6\x97\xb6\xe8\xa7\xa6\xe5\x8f\x91\xe9\x87\x8d\xe6\x96\xb0\xe7\xbd\xae\xe4\xbd\x8d, \xe8\xae\xa9\xe8\xaf\xb7\xe6\xb1\x82 FSM \xe5\x9c\xa8\xe5\x90\x8c\xe4\xb8\x80\xe6\x97\xb6\xe9\x92\x9f\xe5\x91\xa8\xe6\x9c\x9f\xe5\x86\x85\xe8\xaf\x86\xe5\x88\xab\xe5\x88\xb0\xe6\x89\x80\xe6\x9c\x89\xe9\x85\x8d\xe7\xbd\xae\xe5\xb0\xb1\xe7\xbb\xaa,
862: // \xe5\xb9\xb6\xe7\x94\xa8\xe6\x96\xb0\xe7\x9a\x84 req_length/req_addr/ddr3_addr/ddr3_length \xe5\x8f\x91\xe8\xb5\xb7\xe4\xb8\x8b\xe4\xb8\x80\xe4\xb8\xaa chunk \xe7\x9a\x84\xe8\xaf\xb7\xe6\xb1\x82.
863: //**************************************************************************************************************************************
864: assign apb_read  = i_apb_psel && i_apb_penable && ~i_apb_pwrite ;
865: 
866: assign dma_check_success = ~(|i_dma_check_result);
867: 
868: assign dma_check_success = ~(|i_dma_check_result);
869: 
870: always@(posedge clk or negedge rst_n)
871: begin
872:     if(!rst_n)
873:         o_apb_prdata <= 32'd0;
874:     else if(apb_read)
875:         case(i_apb_paddr)
876:             9'h100: o_apb_prdata <= dma_cmd_reg;
877:             9'h110: o_apb_prdata <= dma_cmd_l_addr;
878:             9'h120: o_apb_prdata <= dma_cmd_h_addr;
879:             
880:             9'h140: o_apb_prdata <= apb_cmd_reg;
881:             9'h150: o_apb_prdata <= {22'b0,apb_cmd_length};
882:             9'h160: o_apb_prdata <= apb_cmd_l_addr;
883:             9'h170: o_apb_prdata <= apb_cmd_h_addr;
884:             9'h180: o_apb_prdata <= apb_cmd_data;
885:             9'h190: o_apb_prdata <= i_dma_check_result[31:0];
886:             9'h1A0: o_apb_prdata <= i_dma_check_result[63:32];
887:             9'h1B0: o_apb_prdata <= {31'b0,dma_check_success};
888:             9'h1C0: o_apb_prdata <= apb_ddr3_addr;      // RC DDR3 \xe5\x9c\xb0\xe5\x9d\x80\xe5\x9b\x9e\xe8\xaf\xbb
889:             9'h1D0: o_apb_prdata <= apb_total_length;  // RC TOTAL_LENGTH
890: 
891:             // EP \xe5\xaf\x84\xe5\xad\x98\xe5\x99\xa8 (BAR1 \xe5\x9c\xb0\xe5\x9d\x80\xef\xbc\x8c\xe4\xbb\x8e APB \xe5\x9b\x9e\xe8\xaf\xbb\xe6\x97\xb6\xe4\xb9\x9f\xe7\x94\xa8\xe5\x90\x8c\xe4\xb8\x80\xe5\x9c\xb0\xe5\x9d\x80\xe6\x95\xb0\xe5\xad\x97)
892:             // 0x1E0 = dma_ddr3_addr (\xe4\xbb\x8d\xe5\x9c\xa8\xe4\xbd\xbf\xe7\x94\xa8\xef\xbc\x8c\xe5\x91\x8a\xe7\x9f\xa5 FPGA DDR3 \xe8\xaf\xbb\xe5\x86\x99\xe8\xb5\xb7\xe5\xa7\x8b\xe5\x9c\xb0\xe5\x9d\x80)
893:             // 0x1F0 = \xe5\x8e\x9f ddr3_length \xe5\xaf\x84\xe5\xad\x98\xe5\x99\xa8\xef\xbc\x8c\xe5\xb7\xb2\xe5\x88\xa0\xe9\x99\xa4\xef\xbc\x88\xe7\x94\xb1 total_length \xe6\x8e\xa8\xe5\xaf\xbc\xef\xbc\x89
894:             10'h200: o_apb_prdata <= dma_total_length;   // EP TOTAL_LENGTH (BAR1 0x200)
895:             10'h210: o_apb_prdata <= chunk_rem_bytes;   // chunk \xe5\x89\xa9\xe4\xbd\x99\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0
896:             10'h220: o_apb_prdata <= {chunk_loop_active, 15'b0, chunk_count}; // chunk FSM \xe7\x8a\xb6\xe6\x80\x81
897:             10'h230: o_apb_prdata <= o_ddr3_addr;      // \xe5\xbd\x93\xe5\x89\x8d DDR3 \xe5\x9c\xb0\xe5\x9d\x80
898:             10'h240: o_apb_prdata <= o_ddr3_length;    // \xe5\xbd\x93\xe5\x89\x8d DDR3 chunk \xe9\x95\xbf\xe5\xba\xa6
899:             10'h250: o_apb_prdata <= {22'b0, o_req_length}; // \xe5\xbd\x93\xe5\x89\x8d TLP \xe9\x95\xbf\xe5\xba\xa6 DW
900: 
901:             default: o_apb_prdata <= 32'd0;
902:         endcase
903: end
904: //apb_rdy
905: always@(posedge clk or negedge rst_n)
906: begin
907:     if(!rst_n)
908:         o_apb_prdy <= 1'b0;
909:     else if(i_apb_psel && i_apb_penable && !o_apb_prdy)
910:         o_apb_prdy <= 1'b1;
911:     else
912:         o_apb_prdy <= 1'b0;
913: end
914: 
915: assign o_tx_restart = i_bar1_wr_en && (i_bar1_wr_addr[9:0] == 9'h110);
916: 
917: //detect 4-KB boundary
918: assign req_l_addr = device_rc ? apb_cmd_l_addr[12:0] : dma_cmd_l_addr[12:0];
919: 
920: assign total_data   = ~((device_rc && apb_length_cfg_done) || (device_ep && dma_ctrl_cfg_done)) ? 13'd0 :
921:                         {1'b0, o_req_length[9:0], 2'b0}; // o_req_length = \xe4\xbc\xa0\xe8\xbe\x93 DW \xe6\x95\xb0\xef\xbc\x8c\xe4\xb9\x984\xe5\xbe\x97\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0
922: 
923: assign target_addr  = ~l_addr_cfg_done ? 13'd0 : (req_l_addr[12:0] + total_data);
924: 
925: assign cross_4kb_boundary = (!dma_wr_rd_cmd_flag && chunk_loop_active) ?
926:         ((chunk_host_addr[1:0] != 0) || (chunk_cur_size == 0) ||
927:          (chunk_cur_size > chunk_boundary_limit)) :
928:                             ~l_addr_cfg_done ? 1'b0 :
929:                             (target_addr[12] == req_l_addr[12]) ? 1'b0 : |target_addr[11:0];
930: 
931: //4-KB boundary flag
932: always@(posedge clk or negedge rst_n)
933: begin
934:     if(!rst_n)
935:         o_cross_4kb_boundary <= 1'b0;
936:     else if(cross_4kb_boundary)
937:         o_cross_4kb_boundary <= 1'b1;
938:     else if(cmd_reg_cfg_done)
939:         o_cross_4kb_boundary <= 1'b0;
940: end
941: 
942: 
943: 
944: 
945: 
946: 
947: 
948: //**********************************************************************
949: // MSI Interrupt Generation Logic (Supports both TX/MWr and RX/MRd)
950: //**********************************************************************
951: 
952: // 1. \xe6\x89\x93\xe4\xb8\xa4\xe6\x8b\x8d\xe9\x98\xb2\xe4\xba\x9a\xe7\xa8\xb3\xe6\x80\x81\xe5\xb9\xb6\xe6\x8f\x90\xe5\x8f\x96 TX (\xe5\x86\x99 DDR3 -> CPU) \xe5\xbf\x99\xe4\xbf\xa1\xe5\x8f\xb7\xe7\x9a\x84\xe4\xb8\x8b\xe9\x99\x8d\xe6\xb2\xbf
953: reg mwr_tx_busy_d1, mwr_tx_busy_d2;
954: always @(posedge clk or negedge rst_n) begin
955:     if (!rst_n) begin
956:         mwr_tx_busy_d1 <= 1'b0;
957:         mwr_tx_busy_d2 <= 1'b0;
958:     end else begin
959:         mwr_tx_busy_d1 <= i_mwr_tx_busy;
960:         mwr_tx_busy_d2 <= mwr_tx_busy_d1;
961:     end
962: end
963: wire tx_done_pulse = ~mwr_tx_busy_d1 & mwr_tx_busy_d2;
964: 
965: // 2. \xe6\x89\x93\xe4\xb8\xa4\xe6\x8b\x8d\xe9\x98\xb2\xe4\xba\x9a\xe7\xa8\xb3\xe6\x80\x81\xe5\xb9\xb6\xe6\x8f\x90\xe5\x8f\x96 RX (\xe8\xaf\xbb CPU -> DDR3) \xe5\xbf\x99\xe4\xbf\xa1\xe5\x8f\xb7\xe7\x9a\x84\xe4\xb8\x8b\xe9\x99\x8d\xe6\xb2\xbf
966: reg mrd_rx_busy_d1, mrd_rx_busy_d2;
967: always @(posedge clk or negedge rst_n) begin
968:     if (!rst_n) begin
969:         mrd_rx_busy_d1 <= 1'b0;
970:         mrd_rx_busy_d2 <= 1'b0;
971:     end else begin
972:         mrd_rx_busy_d1 <= i_mrd_rx_busy;
973:         mrd_rx_busy_d2 <= mrd_rx_busy_d1;
974:     end
975: end
976: wire rx_done_pulse = ~mrd_rx_busy_d1 & mrd_rx_busy_d2;
977: 
978: // 3. DMA \xe6\xb4\xbb\xe8\xb7\x83\xe7\x8a\xb6\xe6\x80\x81\xe8\xb7\x9f\xe8\xb8\xaa (\xe9\x98\xb2\xe6\xad\xa2\xe6\x84\x8f\xe5\xa4\x96\xe8\xb7\xb3\xe5\x8f\x98\xe5\xbc\x95\xe8\xb5\xb7\xe8\x99\x9a\xe5\x81\x87\xe4\xb8\xad\xe6\x96\xad)
979: reg tx_active, rx_active;
980: always @(posedge clk or negedge rst_n) begin
981:     if (!rst_n) begin
982:         tx_active <= 1'b0;
983:         rx_active <= 1'b0;
984:     end else begin
985:         // \xe7\x9b\x91\xe6\x8e\xa7 TX \xe7\x8a\xb6\xe6\x80\x81
986:         if (o_mwr32_req || o_mwr64_req) tx_active <= 1'b1;
987:         else if (tx_done_pulse)         tx_active <= 1'b0;
988:         
989:         // \xe7\x9b\x91\xe6\x8e\xa7 RX \xe7\x8a\xb6\xe6\x80\x81
990:         if (o_mrd32_req || o_mrd64_req) rx_active <= 1'b1;
991:         else if (rx_done_pulse)         rx_active <= 1'b0;
992:     end
993: end
994: 
995: 
996: 
997: // 5. \xe5\x88\xa4\xe6\x96\xad\xe6\x98\xaf\xe5\x90\xa6\xe4\xb8\xba\xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80\xe4\xb8\xaachunk
998: // \xe6\xb3\xa8\xe6\x84\x8f: \xe5\x9c\xa8 chunk_done \xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf\xe6\x97\xb6\xe5\x88\xbb, chunk_rem_bytes \xe5\xb0\x9a\xe6\x9c\xaa\xe8\xa2\xab\xe6\x9b\xb4\xe6\x96\xb0 (always\xe5\x9d\x97\xe6\x8c\x89\xe9\xa1\xba\xe5\xba\x8f\xe6\x89\xa7\xe8\xa1\x8c)
999: // \xe6\xad\xa4\xe6\x97\xb6 chunk_rem_bytes \xe4\xbb\x8d\xe8\xa1\xa8\xe7\xa4\xba\xe5\xbd\x93\xe5\x89\x8d chunk \xe7\x9a\x84\xe5\x89\xa9\xe4\xbd\x99\xe5\xad\x97\xe8\x8a\x82\xe6\x95\xb0.
1000: // \xe5\xbd\x93 (chunk_rem_bytes <= CHUNK_SIZE_MAX) \xe6\x97\xb6, \xe5\xbd\x93\xe5\x89\x8d chunk \xe5\xb0\xb1\xe6\x98\xaf\xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80\xe4\xb8\xaa.
1001: wire is_final_chunk = !dma_wr_rd_cmd_flag ? (chunk_rem_bytes <= chunk_cur_size) :
1002:                                           (chunk_rem_bytes <= CHUNK_SIZE_MAX);
1003: 
1004: // 5b. is_final_chunk \xe5\xbb\xb6\xe8\xbf\x9f\xe4\xb8\x80\xe6\x8b\x8d: \xe5\x9c\xa8 chunk_done \xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf\xe6\x89\x80\xe5\x9c\xa8\xe5\x91\xa8\xe6\x9c\x9f, is_final_chunk \xe5\xb7\xb2\xe7\xbb\x8f\xe5\x9c\xa8
1005: // \xe5\x90\x8c\xe4\xb8\x80\xe9\x9d\x9e\xe9\x98\xbb\xe5\xa1\x9e\xe8\xb5\x8b\xe5\x80\xbc\xe7\x9a\x84\xe5\x90\x8c\xe4\xb8\x80 always \xe5\x9d\x97\xe4\xb8\xad\xe5\x8f\x98\xe4\xb8\xba false.
1006: // \xe6\x89\x80\xe4\xbb\xa5 o_fpga_msi \xe7\x9a\x84\xe6\x9d\xa1\xe4\xbb\xb6\xe5\x88\xa4\xe6\x96\xad\xe9\x87\x8c\xe5\xbf\x85\xe9\xa1\xbb\xe7\x94\xa8\xe4\xb8\x8a\xe4\xb8\x80\xe5\x91\xa8\xe6\x9c\x9f\xe7\x9a\x84 is_final_chunk \xe5\x80\xbc.
1007: // \xe5\x8d\xb3: "\xe4\xb8\x8a\xe4\xb8\x80\xe4\xb8\xaachunk\xe6\x98\xaf\xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80\xe4\xb8\xaachunk" = is_final_chunk_d1.
1008: reg is_final_chunk_d1;
1009: always @(posedge clk or negedge rst_n) begin
1010:     if (!rst_n)
1011:         is_final_chunk_d1 <= 1'b0;
1012:     else
1013:         is_final_chunk_d1 <= is_final_chunk;
1014: end
1015: 
1016: // 6. \xe8\xa7\xa6\xe5\x8f\x91 MSI \xe8\x84\x89\xe5\x86\xb2\xef\xbc\x9a\xe5\x8f\xaa\xe5\x9c\xa8\xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80chunk\xe5\xae\x8c\xe6\x88\x90\xe6\x97\xb6\xe5\x8f\x91\xe4\xb8\x80\xe6\xac\xa1MSI
1017: // is_final_chunk_d1 = 1 means "the chunk that just completed (chunk_done) was the last one"
1018: always @(posedge clk or negedge rst_n) begin
1019:     if (!rst_n) begin
1020:         o_fpga_msi <= 1'b0;
1021:     end
1022:     else if (chunk_loop_active && chunk_done && is_final_chunk_d1) begin
1023:         o_fpga_msi <= 1'b1;  // \xe6\x9c\x80\xe5\x90\x8e\xe4\xb8\x80chunk\xe5\xae\x8c\xe6\x88\x90 -> \xe5\x8f\x91MSI
1024:     end
1025:     else if (!chunk_loop_active && ((tx_done_pulse && tx_active) || (rx_done_pulse && rx_active))) begin
1026:         o_fpga_msi <= 1'b1;  // \xe5\x8d\x95chunk\xe6\xa8\xa1\xe5\xbc\x8f\xef\xbc\x8c\xe5\x85\xbc\xe5\xae\xb9\xe6\x97\xa7\xe6\xb5\x81\xe7\xa8\x8b
1027:     end
1028:     else begin
1029:         o_fpga_msi <= 1'b0;
1030:     end
1031: end
1032: 
1033: 
1034: 
1035: 
1036: 
1037: 
1038: endmodule
