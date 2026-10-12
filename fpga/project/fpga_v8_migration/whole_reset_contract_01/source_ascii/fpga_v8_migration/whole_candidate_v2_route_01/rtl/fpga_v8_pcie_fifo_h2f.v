1: module fpga_v8_pcie_fifo_h2f #(
2:     parameter ADDR_WIDTH = 12,
3:               MSI_NUM = 5,
4: 
5:     parameter   AXI_ID_LEN      = 4, 
6: 		        AXI_DATA_LEN    = 128, 
7: 		        AXI_DATA_SIZE   = $clog2(AXI_DATA_LEN/8), 	        
8: 		        AXI_STRB_LEN    = AXI_DATA_LEN / 8               
9: 
10: 
11: )(    
12: 
13:     input                       button_rst_n    ,
14: 
15:     ////////////////// PCIE ////////////////
16:     input                       perst_n         ,
17:     input                       ref_clk_n       ,      
18:     input                       ref_clk_p       ,      
19:     input           [1:0]       rxn             ,
20:     input           [1:0]       rxp             ,
21:     output wire     [1:0]       txn             ,
22:     output wire     [1:0]       txp             ,
23:     output wire                 ref_led         ,
24:     output wire                 pclk_led        ,
25:     output wire                 smlh_link_up    ,
26:     output wire                 rdlh_link_up    ,
27: 
28:     output wire                 fifo_pcie_clk   ,
29:     output wire                 fifo_pcie_rst   , 
30: 
31:     input  [MSI_NUM-2 : 0]      i_msi_req       ,
32:     output [MSI_NUM-2 : 0]      o_msi_grant     ,
33: 
34:     ///////////////// AXI FOR DDR3 //////////////////////////////
35:     input                               axi_clk,
36:     input                               axi_rst,
37: 
38:     output       [AXI_ID_LEN-1:0]       axi_awid        /* synthesis PAP_MARK_DEBUG="true" */,
39:     output       [31:0]                 axi_awaddr      /* synthesis PAP_MARK_DEBUG="true" */,
40:     output       [ 3:0]                 axi_awlen       /* synthesis PAP_MARK_DEBUG="true" */,
41:     output       [ 2:0]                 axi_awsize      /* synthesis PAP_MARK_DEBUG="true" */,
42:     output       [ 1:0]                 axi_awburst     /* synthesis PAP_MARK_DEBUG="true" */,
43:     output                              axi_awlock      /* synthesis PAP_MARK_DEBUG="true" */,
44:     output       [ 3:0]                 axi_awcache     /* synthesis PAP_MARK_DEBUG="true" */,
45:     output       [ 2:0]                 axi_awprot      /* synthesis PAP_MARK_DEBUG="true" */,
46:     output       [ 3:0]                 axi_awqos       /* synthesis PAP_MARK_DEBUG="true" */,
47:     output                              axi_awvalid     /* synthesis PAP_MARK_DEBUG="true" */,
48:     input                               axi_awready     /* synthesis PAP_MARK_DEBUG="true" */,
49:     
50:     output       [AXI_DATA_LEN-1:0]     axi_wdata       /* synthesis PAP_MARK_DEBUG="true" */,
51:     output       [AXI_STRB_LEN-1:0]     axi_wstrb       /* synthesis PAP_MARK_DEBUG="true" */,
52:     output                              axi_wlast       /* synthesis PAP_MARK_DEBUG="true" */,
53:     output                              axi_wvalid      /* synthesis PAP_MARK_DEBUG="true" */,
54:     input                               axi_wready      /* synthesis PAP_MARK_DEBUG="true" */,
55:     
56:     input        [AXI_ID_LEN-1:0]       axi_bid         /* synthesis PAP_MARK_DEBUG="true" */,
57:     input        [ 1:0]                 axi_bresp       /* synthesis PAP_MARK_DEBUG="true" */,
58:     input                               axi_bvalid      /* synthesis PAP_MARK_DEBUG="true" */,
59:     output                              axi_bready      /* synthesis PAP_MARK_DEBUG="true" */,
60:     
61:     output       [AXI_ID_LEN-1:0]       axi_arid        /* synthesis PAP_MARK_DEBUG="true" */,
62:     output       [31:0]                 axi_araddr      /* synthesis PAP_MARK_DEBUG="true" */,
63:     output       [ 3:0]                 axi_arlen       /* synthesis PAP_MARK_DEBUG="true" */,
64:     output       [ 2:0]                 axi_arsize      /* synthesis PAP_MARK_DEBUG="true" */,
65:     output       [ 1:0]                 axi_arburst     /* synthesis PAP_MARK_DEBUG="true" */,
66:     output                              axi_arlock      /* synthesis PAP_MARK_DEBUG="true" */,
67:     output       [ 3:0]                 axi_arcache     /* synthesis PAP_MARK_DEBUG="true" */,
68:     output       [ 2:0]                 axi_arprot      /* synthesis PAP_MARK_DEBUG="true" */,
69:     output       [ 3:0]                 axi_arqos       /* synthesis PAP_MARK_DEBUG="true" */,
70:     output                              axi_arvalid     /* synthesis PAP_MARK_DEBUG="true" */,
71:     input                               axi_arready     /* synthesis PAP_MARK_DEBUG="true" */,
72:     
73:     input        [AXI_ID_LEN-1:0]       axi_rid         /* synthesis PAP_MARK_DEBUG="true" */,
74:     input        [AXI_DATA_LEN-1:0]     axi_rdata       /* synthesis PAP_MARK_DEBUG="true" */,
75:     input        [ 1:0]                 axi_rresp       /* synthesis PAP_MARK_DEBUG="true" */,
76:     input                               axi_rlast       /* synthesis PAP_MARK_DEBUG="true" */,
77:     input                               axi_rvalid      /* synthesis PAP_MARK_DEBUG="true" */,
78:     output                              axi_rready      /* synthesis PAP_MARK_DEBUG="true" */
79: 
80:         
81: );
82: // Included as text by the isolated candidate generator, after the FIFO ports.
83: // This handshake requires COORDINATED PCIe + AXI fabric/endpoint reset.
84: // Independent link/CPU reset is not a supported pending-DMA cleanup path.
85: wire rx_retirement_epoch_rst = axi_rst | fifo_pcie_rst;
86: // Assert both new handshake domains asynchronously, release in each clock.
87: (* ASYNC_REG = "TRUE" *) reg rx_retire_axi_rst1, rx_retire_axi_rst2;
88: (* ASYNC_REG = "TRUE" *) reg rx_retire_pcie_rst1, rx_retire_pcie_rst2;
89: always @(posedge axi_clk or posedge rx_retirement_epoch_rst) begin
90:     if (rx_retirement_epoch_rst) begin
91:         rx_retire_axi_rst1 <= 1'b1;
92:         rx_retire_axi_rst2 <= 1'b1;
93:     end else begin
94:         rx_retire_axi_rst1 <= 1'b0;
95:         rx_retire_axi_rst2 <= rx_retire_axi_rst1;
96:     end
97: end
98: always @(posedge fifo_pcie_clk or posedge rx_retirement_epoch_rst) begin
99:     if (rx_retirement_epoch_rst) begin
100:         rx_retire_pcie_rst1 <= 1'b1;
101:         rx_retire_pcie_rst2 <= 1'b1;
102:     end else begin
103:         rx_retire_pcie_rst1 <= 1'b0;
104:         rx_retire_pcie_rst2 <= rx_retire_pcie_rst1;
105:     end
106: end
107: reg rx_retired_toggle;
108: (* ASYNC_REG = "TRUE" *) reg rx_retired_sync1, rx_retired_sync2;
109: reg rx_retired_seen;
110: 
111: // One persistent credit for each complete H2F transaction. Intermediate
112: // chunks and intermediate bursts cannot produce a credit. BRESP errors still
113: // retire: the host sees DeliveryKnownUnknownResponse and must read back state.
114: always @(posedge axi_clk or posedge rx_retire_axi_rst2) begin
115:     if (rx_retire_axi_rst2)
116:         rx_retired_toggle <= 1'b0;
117:     else if ((state == S_BRESP_WAIT) && (beats_remain == 32'd0) &&
118:              axi_bvalid && axi_bready && (axi_bid == {AXI_ID_LEN{1'b0}}))
119:         rx_retired_toggle <= ~rx_retired_toggle;
120: end
121: 
122: always @(posedge fifo_pcie_clk or posedge rx_retire_pcie_rst2) begin
123:     if (rx_retire_pcie_rst2) begin
124:         rx_retired_sync1 <= 1'b0;
125:         rx_retired_sync2 <= 1'b0;
126:     end else begin
127:         rx_retired_sync1 <= rx_retired_toggle;
128:         rx_retired_sync2 <= rx_retired_sync1;
129:     end
130: end
131: 
132: // Consume only at final total completion; never consume at an intermediate
133: // chunk. The completed toggle remains different from seen until consumed.
134: // Previously consumed retirement cannot authorize a later command.
135: always @(posedge fifo_pcie_clk or posedge rx_retire_pcie_rst2) begin
136:     if (rx_retire_pcie_rst2)
137:         rx_retired_seen <= 1'b0;
138:     else if (!fpga_data_valid && !fpga_rx_done && rx_transaction_complete &&
139:              (rx_cnt == dma_total_beats) && fifo_rx_empty &&
140:              (rx_retired_sync2 != rx_retired_seen))
141:         rx_retired_seen <= rx_retired_sync2;
142: end
143: 
144: 
145: 
146: //----------------------------------------
147: // CPU --> FPGA RX FIFO
148: //----------------------------------------
149: 
150: wire    [31:0]              fpga_ddr3_addr   ;              //rx
151: wire    [31:0]              fpga_ddr3_length ;              //rx
152: wire    [31:0]              fpga_ddr3_total_length ;        //tx
153: 
154: wire                        mrd_rx_busy;
155: wire                        fpga_rx_clk_en   ;
156: wire     [ADDR_WIDTH-1:0]   fpga_rx_addr     ;
157: wire     [127:0]            fpga_rx_data     ;
158: reg                         mrd_rx_busy_r    ;
159: wire                        mrd_rx_falling   ;
160: // reg                         mrd_rx_rase      ;
161: reg                         fpga_rx_clk_en_r ;
162: reg     [ADDR_WIDTH-1:0]    fpga_rx_addr_r   ;
163: 
164: 
165: // mrd_rx_busy falling edge detection
166: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
167:     if (fifo_pcie_rst) begin
168:         mrd_rx_busy_r <= 1'b0;
169:     end 
170:     else begin
171:         mrd_rx_busy_r <= mrd_rx_busy;
172:         // mrd_rx_rase   <= ~mrd_rx_busy_r & mrd_rx_busy;
173:     end
174: end
175: assign mrd_rx_falling = mrd_rx_busy_r & ~mrd_rx_busy;
176: 
177: ////////////////////////////////////////
178: localparam S_DATA_WRY_IDLE   = 1'd0;
179: localparam S_DATA_WRY_CHECK  = 1'd1;
180: reg  data_wry_state;
181: reg  data_wry_state_next;
182: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
183:     if (fifo_pcie_rst) begin
184:         data_wry_state <= S_DATA_WRY_IDLE;
185:     end else begin
186:         data_wry_state <= data_wry_state_next;
187:     end
188: end
189: 
190: always @(*) begin
191:     case (data_wry_state)
192:         S_DATA_WRY_IDLE:  data_wry_state_next = mrd_rx_falling  ? S_DATA_WRY_CHECK : S_DATA_WRY_IDLE;
193:         S_DATA_WRY_CHECK: data_wry_state_next = fifo_rx_almost_full ? S_DATA_WRY_CHECK : S_DATA_WRY_IDLE;
194:         default:          data_wry_state_next = S_DATA_WRY_IDLE;
195:     endcase
196: end
197: 
198: reg fpga_data_valid_pulse;
199: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
200:     if (fifo_pcie_rst) begin
201:         fpga_data_valid_pulse <= 1'b0;
202:     end 
203:     else begin
204:         fpga_data_valid_pulse <= ((data_wry_state == S_DATA_WRY_CHECK) && !fifo_rx_almost_full) ;
205:     end
206: end
207: wire fpga_data_valid;
208: assign fpga_data_valid = fpga_data_valid_pulse;
209: 
210: ///////////////////////////////////////////////
211: wire [31:0] total_beats    /* synthesis PAP_MARK_DEBUG="true" */;
212: assign total_beats     = (fpga_ddr3_length[31:4] + |fpga_ddr3_length[3:0]);  // ceil(len/16)
213: wire [31:0] dma_total_beats/* synthesis PAP_MARK_DEBUG="true" */;
214: assign dma_total_beats = (fpga_ddr3_total_length[31:4] + |fpga_ddr3_total_length[3:0]);  // ceil(len/16)
215: // H2F chunk RAM reads have one clock latency. Keep partial 128-bit words
216: // across chunks, so a 4092-byte intermediate chunk contributes 255 full words
217: // and 12 carry bytes, never a padded word in the middle of a transfer.
218: reg [31:0] rx_cnt;
219: reg [31:0] rx_bytes_total, rx_chunk_bytes;
220: reg [127:0] rx_pack_data, rx_fifo_write_data;
221: reg [4:0] rx_pack_bytes;
222: reg rx_fifo_write_en, rx_copy_active, rx_transaction_complete;
223: reg fpga_rx_clk_en_d;
224: reg fpga_rx_done;
225: wire [31:0] rx_input_bytes = ((fpga_ddr3_length - rx_chunk_bytes) >= 16) ?
226:                             32'd16 : fpga_ddr3_length - rx_chunk_bytes;
227: wire [127:0] rx_input_mask = {128{1'b1}} >> ((32'd16-rx_input_bytes)*8);
228: wire [255:0] rx_merge_data = {128'd0,rx_pack_data} |
229:     ({128'd0,(fpga_rx_data & rx_input_mask)} << (rx_pack_bytes*8));
230: wire [5:0] rx_merge_bytes = {1'b0,rx_pack_bytes}+rx_input_bytes[5:0];
231: assign fpga_rx_clk_en = fpga_rx_clk_en_r;
232: assign fpga_rx_addr = fpga_rx_addr_r;
233: 
234: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
235:     if (fifo_pcie_rst) begin
236:         fpga_rx_clk_en_r <= 0; fpga_rx_clk_en_d <= 0;
237:         fpga_rx_addr_r <= 0; rx_cnt <= 0;
238:         rx_bytes_total <= 0; rx_chunk_bytes <= 0;
239:         rx_pack_data <= 0; rx_pack_bytes <= 0;
240:         rx_fifo_write_en <= 0; rx_fifo_write_data <= 0;
241:         rx_copy_active <= 0; rx_transaction_complete <= 0;
242:         fpga_rx_done <= 0;
243:     end else begin
244:         fpga_rx_clk_en_d <= fpga_rx_clk_en_r;
245:         rx_fifo_write_en <= 0;
246:         if (rx_fifo_write_en) rx_cnt <= rx_cnt + 1'b1;
247:         if (fpga_data_valid) begin
248:             fpga_rx_clk_en_r <= 1;
249:             fpga_rx_addr_r <= 0;
250:             rx_chunk_bytes <= 0;
251:             rx_copy_active <= 1;
252:             fpga_rx_done <= 0;
253:             if (rx_transaction_complete) begin
254:                 rx_cnt <= 0; rx_bytes_total <= 0;
255:                 rx_pack_data <= 0; rx_pack_bytes <= 0;
256:             end
257:             rx_transaction_complete <= 0;
258:         end else begin
259:             if (fpga_rx_clk_en_r) begin
260:                 if (fpga_rx_addr_r == total_beats-1)
261:                     fpga_rx_clk_en_r <= 0;
262:                 fpga_rx_addr_r <= fpga_rx_addr_r + 1'b1;
263:             end
264:             if (fpga_rx_clk_en_d) begin
265:                 rx_chunk_bytes <= rx_chunk_bytes + rx_input_bytes;
266:                 rx_bytes_total <= rx_bytes_total + rx_input_bytes;
267:                 if (rx_merge_bytes >= 16) begin
268:                     rx_fifo_write_en <= 1;
269:                     rx_fifo_write_data <= rx_merge_data[127:0];
270:                     rx_pack_data <= rx_merge_data[255:128];
271:                     rx_pack_bytes <= rx_merge_bytes-16;
272:                 end else begin
273:                     rx_pack_data <= rx_merge_data[127:0];
274:                     rx_pack_bytes <= rx_merge_bytes;
275:                 end
276:             end else if (rx_copy_active && !fpga_rx_clk_en_r && !rx_fifo_write_en) begin
277:                 if ((rx_bytes_total == fpga_ddr3_total_length) && (rx_pack_bytes != 0)) begin
278:                     // Only the final transaction word is zero padded.
279:                     rx_fifo_write_en <= 1;
280:                     rx_fifo_write_data <= rx_pack_data;
281:                     rx_pack_data <= 0; rx_pack_bytes <= 0;
282:                 end else begin
283:                     rx_copy_active <= 0;
284:                     if (rx_bytes_total == fpga_ddr3_total_length)
285:                         rx_transaction_complete <= 1;
286:                     else
287:                         fpga_rx_done <= 1;
288:                 end
289:             end
290:             if (rx_transaction_complete && (rx_cnt == dma_total_beats) &&
291:                 fifo_rx_empty && (rx_retired_sync2 != rx_retired_seen))
292:                 fpga_rx_done <= 1;
293:         end
294:     end
295: end
296: 
297: 
298: //////////////tx/////////////////
299: wire                        mwr_tx_busy                ;
300: wire                        fpga_data_ready            ;
301: wire                        fpga_tx_done               ;
302: wire                        fpga_tx_clk_en             ;
303: wire     [ADDR_WIDTH-1:0]   fpga_tx_addr               /* synthesis PAP_MARK_DEBUG="true" */;
304: wire     [127:0]            fpga_tx_data               ;
305: 
306: 
307: fpga_v8_pango_pcie_top_h2f #(
308:     .ADDR_WIDTH(ADDR_WIDTH),
309:     .MSI_NUM(MSI_NUM)
310: )
311: pango_pcie_top(
312:     .button_rst_n(button_rst_n)    ,
313:     .perst_n     (perst_n     )    ,
314:     .ref_clk_n   (ref_clk_n)      ,
315:     .ref_clk_p   (ref_clk_p)      ,
316:     .rxn         (rxn)        ,
317:     .rxp         (rxp)        ,
318:     .txn         (txn)        ,
319:     .txp         (txp)        ,
320:     .ref_led     (ref_led     )    ,
321:     .pclk_led    (pclk_led    )    ,
322:     .smlh_link_up(smlh_link_up)    ,
323:     .rdlh_link_up(rdlh_link_up)    ,
324: 
325:     .i_msi_req  (i_msi_req    )    ,
326:     .o_msi_grant(o_msi_grant  )    ,
327: 
328:     .fpga_ddr3_addr   (fpga_ddr3_addr   ),
329:     .fpga_ddr3_length (fpga_ddr3_length ),
330:     .fpga_ddr3_total_length(fpga_ddr3_total_length),
331:     //FPGA --> CPU
332:     .fpga_tx_done     (fpga_tx_done     ),     
333:     .mwr_tx_busy      (mwr_tx_busy      ),
334:     .fpga_data_ready  (fpga_data_ready  ),     
335:     .fpga_tx_clk_en   (fpga_tx_clk_en   ),
336:     .fpga_tx_addr     (fpga_tx_addr     ),      //\xe6\xb2\xa1\xe7\x94\xa8
337:     .fpga_tx_data     (fpga_tx_data     ),
338:     //CPU --> FPGA
339:     .fpga_rx_done     (fpga_rx_done     ),     
340:     .mrd_rx_busy      (mrd_rx_busy      ),
341:     .fpga_rx_clk_en   (fpga_rx_clk_en   ),
342:     .fpga_rx_addr     (fpga_rx_addr     ),
343:     .fpga_rx_data     (fpga_rx_data     ),
344: 
345:     .fifo_pcie_clk    (fifo_pcie_clk)    ,
346:     .fifo_pcie_rst    (fifo_pcie_rst)
347: );
348: 
349: 
350: 
351: 
352: wire [127:0] fifo_rx_data /* synthesis PAP_MARK_DEBUG="true" */;
353: wire         fifo_rx_empty/* synthesis PAP_MARK_DEBUG="true" */;
354: wire         fifo_rx_rd_en/* synthesis PAP_MARK_DEBUG="true" */;
355: wire [9 : 0] fifo_rx_water_level;
356: 
357: pcie_rx_fifo pcie_rx_fifo (
358:   .wr_clk       (fifo_pcie_clk      ),
359:   .wr_rst       (fifo_pcie_rst      ),
360:   .wr_en        (rx_fifo_write_en   ),
361:   .wr_data      (rx_fifo_write_data ),
362:   .wr_full      (                   ),
363:   .almost_full  (fifo_rx_almost_full),
364:   .rd_clk       (axi_clk            ),
365:   .rd_rst       (axi_rst            ),
366:   .rd_en        (fifo_rx_rd_en      ),
367:   .rd_data      (fifo_rx_data       ),
368:   .rd_empty     (fifo_rx_empty      ),
369:   .rd_water_level(fifo_rx_water_level),    // output [9:0]
370:   .almost_empty (                   )
371: );
372: 
373: 
374: 
375: // \xe7\xaa\x81\xe5\x8f\x91\xe5\x8f\x82\xe6\x95\xb0\xe8\xae\xa1\xe7\xae\x97
376: 
377: wire [31:0] last_beat_bytes/* synthesis PAP_MARK_DEBUG="true" */;
378: wire [15:0] last_beat_strb /* synthesis PAP_MARK_DEBUG="true" */;
379: 
380: assign last_beat_bytes = |fpga_ddr3_total_length[3:0] ? fpga_ddr3_total_length[3:0] : 32'd16;
381: 
382: // \xe6\x9c\x80\xe5\x90\x8e beat \xe7\x9a\x84\xe5\xad\x97\xe8\x8a\x82\xe6\x8e\xa9\xe7\xa0\x81
383: assign last_beat_strb  = (last_beat_bytes == 32'd1)  ? 16'b0000_0000_0000_0001 :
384:                          (last_beat_bytes == 32'd2)  ? 16'b0000_0000_0000_0011 :
385:                          (last_beat_bytes == 32'd3)  ? 16'b0000_0000_0000_0111 :
386:                          (last_beat_bytes == 32'd4)  ? 16'b0000_0000_0000_1111 :
387:                          (last_beat_bytes == 32'd5)  ? 16'b0000_0000_0001_1111 :
388:                          (last_beat_bytes == 32'd6)  ? 16'b0000_0000_0011_1111 :
389:                          (last_beat_bytes == 32'd7)  ? 16'b0000_0000_0111_1111 :
390:                          (last_beat_bytes == 32'd8)  ? 16'b0000_0000_1111_1111 :
391:                          (last_beat_bytes == 32'd9)  ? 16'b0000_0001_1111_1111 :
392:                          (last_beat_bytes == 32'd10) ? 16'b0000_0011_1111_1111 :
393:                          (last_beat_bytes == 32'd11) ? 16'b0000_0111_1111_1111 :
394:                          (last_beat_bytes == 32'd12) ? 16'b0000_1111_1111_1111 :
395:                          (last_beat_bytes == 32'd13) ? 16'b0001_1111_1111_1111 :
396:                          (last_beat_bytes == 32'd14) ? 16'b0011_1111_1111_1111 :
397:                          (last_beat_bytes == 32'd15) ? 16'b0111_1111_1111_1111 :
398:                                                        16'b1111_1111_1111_1111 ;
399: 
400: 
401: 
402: 
403: //====================================================
404: // AXI Write Interface Logic (With B channel)
405: //====================================================
406: 
407: // One outstanding AXI burst. Every FIFO read reserves a response slot before
408: // the synchronous RAM is clocked. The pending bit is the one-clock read
409: // latency; the two-word queue holds returned data across arbitrary W stalls.
410: localparam S_IDLE=3'd0, S_ADDR_SEND=3'd1, S_WDATA_SEND=3'd2;
411: localparam S_BRESP_WAIT=3'd3, S_WRITW_DATA=3'd4;
412: reg [2:0] state;
413: reg [31:0] cur_addr, beats_remain;
414: reg [15:0] cur_strb;
415: reg [4:0] burst_beats, reads_issued, wbeat_cnt;
416: reg [1:0] rx_w_queue_count;
417: reg [127:0] rx_w_q0, rx_w_q1;
418: reg rx_read_pending, axi_b_resp_error;
419: wire rx_w_fire = axi_wvalid && axi_wready;
420: wire rx_b_fire = axi_bvalid && axi_bready && (axi_bid == {AXI_ID_LEN{1'b0}});
421: wire [2:0] rx_reserved_after_pop = {1'b0,rx_w_queue_count} +
422:                                 {2'b0,rx_read_pending} - {2'b0,rx_w_fire};
423: assign fifo_rx_rd_en = (state == S_WDATA_SEND) && !fifo_rx_empty &&
424:                       (reads_issued < burst_beats) && (rx_reserved_after_pop < 2);
425: assign axi_awid = {AXI_ID_LEN{1'b0}};
426: assign axi_awaddr = cur_addr;
427: assign axi_awlen = burst_beats - 1'b1;
428: assign axi_awsize = AXI_DATA_SIZE;
429: assign axi_awburst = 2'b01;
430: assign axi_awlock = 0;
431: assign axi_awcache = 4'b0010;
432: assign axi_awprot = 0;
433: assign axi_awqos = 0;
434: assign axi_awvalid = (state == S_ADDR_SEND);
435: assign axi_wdata = rx_w_q0;
436: assign axi_wvalid = (state == S_WDATA_SEND) && (rx_w_queue_count != 0);
437: assign axi_wlast = (wbeat_cnt == burst_beats-1'b1);
438: assign axi_wstrb = (axi_wlast && (beats_remain <= {27'd0,burst_beats})) ? cur_strb : 16'hffff;
439: assign axi_bready = (state == S_BRESP_WAIT);
440: 
441: always @(posedge axi_clk) begin
442:     if (axi_rst) begin
443:         state <= S_IDLE; cur_addr <= 0; cur_strb <= 16'hffff;
444:         beats_remain <= 0; burst_beats <= 1;
445:         reads_issued <= 0; wbeat_cnt <= 0;
446:         rx_read_pending <= 0; rx_w_queue_count <= 0;
447:         rx_w_q0 <= 0; rx_w_q1 <= 0; axi_b_resp_error <= 0;
448:     end else begin
449:         rx_read_pending <= fifo_rx_rd_en;
450:         if (fifo_rx_rd_en) reads_issued <= reads_issued + 1'b1;
451:         case ({rx_read_pending,rx_w_fire})
452:             2'b10: begin
453:                 if (rx_w_queue_count == 0) rx_w_q0 <= fifo_rx_data;
454:                 else rx_w_q1 <= fifo_rx_data;
455:                 rx_w_queue_count <= rx_w_queue_count + 1'b1;
456:             end
457:             2'b01: begin
458:                 if (rx_w_queue_count == 2) rx_w_q0 <= rx_w_q1;
459:                 rx_w_queue_count <= rx_w_queue_count - 1'b1;
460:             end
461:             2'b11: begin
462:                 if (rx_w_queue_count == 1) rx_w_q0 <= fifo_rx_data;
463:                 else begin rx_w_q0 <= rx_w_q1; rx_w_q1 <= fifo_rx_data; end
464:             end
465:         endcase
466:         case (state)
467:             S_IDLE: if (!fifo_rx_empty) begin
468:                 cur_addr <= {(fpga_ddr3_addr >> AXI_DATA_SIZE),{AXI_DATA_SIZE{1'b0}}};
469:                 cur_strb <= last_beat_strb;
470:                 beats_remain <= dma_total_beats;
471:                 burst_beats <= (dma_total_beats >= 16) ? 5'd16 : dma_total_beats[4:0];
472:                 reads_issued <= 0; wbeat_cnt <= 0; axi_b_resp_error <= 0;
473:                 state <= S_ADDR_SEND;
474:             end
475:             S_ADDR_SEND: if (axi_awvalid && axi_awready) state <= S_WDATA_SEND;
476:             S_WDATA_SEND: if (rx_w_fire) begin
477:                 wbeat_cnt <= wbeat_cnt + 1'b1;
478:                 if (axi_wlast) begin
479:                     // Widen before arithmetic: a 16-beat burst is 256 bytes.
480:                     cur_addr <= cur_addr + ({27'd0,burst_beats} << 4);
481:                     beats_remain <= beats_remain - {27'd0,burst_beats};
482:                     state <= S_BRESP_WAIT;
483:                 end
484:             end
485:             S_BRESP_WAIT: if (rx_b_fire) begin
486:                 axi_b_resp_error <= (axi_bresp != 0);
487:                 state <= (beats_remain == 0) ? S_IDLE : S_WRITW_DATA;
488:             end
489:             S_WRITW_DATA: if (!axi_b_resp_error) begin
490:                 burst_beats <= (beats_remain >= 16) ? 5'd16 : beats_remain[4:0];
491:                 reads_issued <= 0; wbeat_cnt <= 0;
492:                 state <= S_ADDR_SEND;
493:             end
494:         endcase
495:     end
496: end
497: 
498: 
499: ////////////////////////////////////////////////////////////////////////
500: wire         fifo_tx_empty/* synthesis PAP_MARK_DEBUG="true" */;
501: wire [9 : 0] fifo_tx_water_level/* synthesis PAP_MARK_DEBUG="true" */;
502: wire         fifo_tx_almost_full/* synthesis PAP_MARK_DEBUG="true" */;
503: wire full/* synthesis PAP_MARK_DEBUG="true" */;
504: pcie_tx_fifo pcie_tx_fifo (
505:   .wr_clk       (axi_clk            ),
506:   .wr_rst       (axi_rst            ),
507:   .wr_en        (fifo_tx_wr_en      ),
508:   .wr_data      (fifo_tx_wr_data    ),
509:   .wr_full      (full                ),
510:   .almost_full  (fifo_tx_almost_full ),
511:   .rd_clk       (fifo_pcie_clk       ),
512:   .rd_rst       (fifo_pcie_rst       ),
513:   .rd_en        (fpga_tx_clk_en      ),
514:   .rd_data      (fpga_tx_data        ),
515:   .rd_empty     (fifo_tx_empty       ),
516:   .rd_water_level(fifo_tx_water_level),
517:   .almost_empty (                    )
518: );
519: 
520: 
521: 
522: 
523: 
524: ////////////////////////////////////////////////////////////////////////
525: // FPGA --> CPU TX Data Ready Logic
526: ////////////////////////////////////////////////////////////////////////
527: wire  mwr_tx_busy_rising /* synthesis PAP_MARK_DEBUG="true" */;
528: reg  mwr_tx_busy_d;
529: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
530:     if (fifo_pcie_rst) begin
531:         mwr_tx_busy_d <= 1'b0;
532:     end else begin
533:         mwr_tx_busy_d <= mwr_tx_busy;
534:     end
535: end
536: assign mwr_tx_busy_rising = ~mwr_tx_busy_d & mwr_tx_busy;
537: 
538: localparam S_DATA_RDY_IDLE   = 1'd0;
539: localparam S_DATA_RDY_CHECK  = 1'd1;
540: reg  data_rdy_state;
541: reg  data_rdy_state_next;
542: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
543:     if (fifo_pcie_rst) begin
544:         data_rdy_state <= S_DATA_RDY_IDLE;
545:     end else begin
546:         data_rdy_state <= data_rdy_state_next;
547:     end
548: end
549: 
550: always @(*) begin
551:     case (data_rdy_state)
552:         S_DATA_RDY_IDLE:  data_rdy_state_next = mwr_tx_busy_rising  ? S_DATA_RDY_CHECK : S_DATA_RDY_IDLE;
553:         S_DATA_RDY_CHECK: data_rdy_state_next = (!fifo_tx_empty && (fifo_tx_water_level >= total_beats[9:0]))
554:                                                ? S_DATA_RDY_IDLE : S_DATA_RDY_CHECK;
555:         default:          data_rdy_state_next = S_DATA_RDY_IDLE;
556:     endcase
557: end
558: 
559: reg fpga_data_ready_r;
560: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
561:     if (fifo_pcie_rst) begin
562:         fpga_data_ready_r <= 1'b0;
563:     end
564:     else if(mwr_tx_busy_rising) begin
565:         fpga_data_ready_r <= 1'b0;
566:     end
567:     else if(data_rdy_state == S_DATA_RDY_CHECK) begin
568:         fpga_data_ready_r <= (!fifo_tx_empty && (fifo_tx_water_level >= total_beats[9:0])) ;
569:     end
570: end
571: 
572: assign fpga_data_ready = fpga_data_ready_r;
573: 
574: ////////////////////////////////////////////////////////////////////////
575: // FPGA --> CPU TX Done Logic
576: ////////////////////////////////////////////////////////////////////////
577: reg  [31:0] tx_cnt/* synthesis PAP_MARK_DEBUG="true" */;  //\xe6\x80\xbb\xe6\x93\x8d\xe4\xbd\x9cbeat\xe6\x95\xb0
578: reg  [31:0] tx_beat_cnt/* synthesis PAP_MARK_DEBUG="true" */;
579: reg        fpga_tx_done_r;
580: 
581: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
582:     if (fifo_pcie_rst) begin
583:         tx_beat_cnt    <= 32'd0;
584:     end 
585:     else if(tx_beat_cnt == total_beats) begin
586:         tx_beat_cnt <= 32'd0;
587:     end
588:     else if (fpga_tx_clk_en) begin
589:         tx_beat_cnt  <= tx_beat_cnt + 1'd1; 
590:     end
591: end
592: 
593: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
594:     if (fifo_pcie_rst) begin
595:         fpga_tx_done_r <= 1'b0;
596:     end
597:     else if(tx_beat_cnt == total_beats) begin
598:         fpga_tx_done_r <= 1'b1;
599:     end
600:     else if(mwr_tx_busy_rising) begin
601:         fpga_tx_done_r <= 1'b0;
602:     end
603: end
604: assign fpga_tx_done = fpga_tx_done_r;
605: 
606: 
607: 
608: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
609:     if (fifo_pcie_rst) begin
610:         tx_cnt <= 32'd0;
611:     end 
612:     else if (tx_cnt == dma_total_beats) begin
613:         tx_cnt <= 32'd0;
614:     end 
615:     else if (fpga_tx_clk_en) begin
616:         tx_cnt <= tx_cnt + 1'd1; 
617:     end
618: end
619: 
620: ///////////////////////// AXI_read ////////////////////////////////
621: 
622: //====================================================
623: // AXI Read Interface Logic
624: //====================================================
625: reg tx_runing;
626: always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
627:     if (fifo_pcie_rst) begin
628:         tx_runing <= 1'b0;
629:     end
630:     else if(tx_cnt == dma_total_beats) begin
631:         tx_runing <= 1'b0;
632:     end
633:     else if(mwr_tx_busy_rising) begin
634:         tx_runing <= 1'b1;
635:     end
636: end
637: 
638: 
639: //----------- CDC: tx_runing from fifo_pcie_clk to axi_clk ----------
640: reg tx_runing_axi;
641: reg tx_runing_axi_d1;
642: reg tx_runing_axi_d2;
643: always @(posedge axi_clk or posedge axi_rst) begin
644:     if (axi_rst) begin
645:         tx_runing_axi   <= 1'b0;
646:         tx_runing_axi_d1 <= 1'b0;
647:         tx_runing_axi_d2 <= 1'b0;
648:     end else begin
649:         tx_runing_axi    <= tx_runing;
650:         tx_runing_axi_d1 <= tx_runing_axi;
651:         tx_runing_axi_d2 <= tx_runing_axi_d1;
652:     end
653: end
654: 
655: wire tx_runing_axi_rising = tx_runing_axi_d1 && ~tx_runing_axi_d2;
656: 
657: //----------- Read Start & Base Address Latch ----------
658: reg [31:0] r_cur_addr;
659: reg [31:0] read_beats_remain /* synthesis PAP_MARK_DEBUG="true" */;
660: reg        read_started /* synthesis PAP_MARK_DEBUG="true" */;
661: 
662: always @(posedge axi_clk or posedge axi_rst) begin
663:     if (axi_rst) begin
664:         read_beats_remain <= 32'd0;
665:         read_started      <= 1'b0;
666:     end
667:     else if (tx_runing_axi_rising) begin
668:         read_beats_remain <= dma_total_beats;
669:         read_started      <= 1'b1;
670:     end
671:     else if (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) begin
672:         read_beats_remain <= read_beats_remain - (axi_arlen + 4'd1);
673:     end
674:     else if (read_started && read_beats_remain == 32'd0) begin
675:         read_started <= 1'b0;
676:     end
677: end
678: 
679: 
680: /////////////////////////////////////////
681: // reg test /* synthesis PAP_MARK_DEBUG="true" */;
682: // always @(posedge axi_clk or posedge axi_rst) begin
683: //     if (axi_rst) begin
684: //         test <= 1'b0;
685: //     end
686: //     else if(axi_rvalid && axi_rready && (axi_araddr > 32'h1c2000 + 32'h003F8400)) begin
687: //         test <= 1'b1;
688: //     end
689: // end
690: //////////////////////////////////////////
691: 
692: // Current address update
693: always @(posedge axi_clk or posedge axi_rst) begin
694:     if (axi_rst) begin
695:         r_cur_addr <= 32'd0;
696:     end
697:     else if (tx_runing_axi_rising) begin
698:         r_cur_addr <= {(fpga_ddr3_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}};
699:     end
700:     else if (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) begin
701:         r_cur_addr <= r_cur_addr + ((axi_arlen + 4'd1) << 4);  // Advance by beats * 16 bytes
702:     end
703: end
704: 
705: //----------- Read Address State Machine ----------
706: localparam R_IDLE       = 2'd0;
707: localparam R_ADDR_SEND  = 2'd1;
708: localparam R_DATA_WAIT  = 2'd2;
709: localparam R_DONE       = 2'd3;
710: 
711: reg [1:0] r_state/* synthesis PAP_MARK_DEBUG="true" */;
712: reg [1:0] r_next;
713: 
714: 
715: always @(posedge axi_clk or posedge axi_rst) begin
716:     if (axi_rst)
717:         r_state <= R_IDLE;
718:     else
719:         r_state <= r_next;
720: end
721: 
722: always @(*) begin
723:     case (r_state)
724:         R_IDLE:      r_next = (read_started && !fifo_tx_almost_full) ? R_ADDR_SEND : R_IDLE;
725:         R_ADDR_SEND: r_next = (axi_arvalid && axi_arready) ? R_DATA_WAIT : R_ADDR_SEND;
726:         R_DATA_WAIT: r_next = (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) ? R_DONE : R_DATA_WAIT;
727:         R_DONE:      r_next = (read_beats_remain == 32'd0) ? R_IDLE : (fifo_tx_almost_full ? R_DONE : R_ADDR_SEND);
728:         default:     r_next = R_IDLE;
729:     endcase
730: end
731: 
732: 
733: //----------- Burst Length Calculation ----------
734: wire [3:0] r_burst_len = (read_beats_remain >= 32'd16) ? 4'd15 :
735:                           (read_beats_remain[3:0] == 4'd0) ? 4'd15 :
736:                           (read_beats_remain[3:0] - 4'd1);
737: 
738: //----------- AR Signal Assignments ----------
739: assign axi_arlen      = r_burst_len;
740: assign axi_araddr     = r_cur_addr;
741: assign axi_arsize     = AXI_DATA_SIZE;   // 4 (16 bytes per beat)
742: assign axi_arburst    = 2'b01;           // INCR burst
743: assign axi_arlock     = 1'b0;
744: assign axi_arcache    = 4'b0010;         // Normal non-cacheable
745: assign axi_arprot     = 3'b000;
746: assign axi_arqos      = 4'd0;
747: assign axi_aruser_ap  = 1'b0;
748: assign axi_aruser_id  = 4'd0;
749: assign axi_arid       = 4'd0;
750: 
751: // reg ar_sent;
752: // always @(posedge axi_clk or posedge axi_rst) begin
753: //     if (axi_rst)
754: //         ar_sent <= 1'b0;
755: //     else if (r_state == R_INIT)
756: //         ar_sent <= 1'b0;
757: //     else if (r_state == R_ADDR_SEND && axi_arvalid && axi_arready)
758: //         ar_sent <= 1'b1;
759: // end
760: 
761: assign axi_arvalid = (r_state == R_ADDR_SEND);// && !ar_sent;
762: 
763: //----------- RREADY & FIFO Write ----------
764: assign axi_rready = (r_state == R_DATA_WAIT);
765: 
766: //----------- FIFO Write Interface ----------
767: reg  fifo_tx_wr_en;
768: reg  [127:0] fifo_tx_wr_data;
769: 
770: 
771: always @(posedge axi_clk or posedge axi_rst) begin
772:     if (axi_rst) begin
773:         fifo_tx_wr_en    <= 1'b0;
774:         fifo_tx_wr_data  <= 128'd0;
775:     end
776:     else begin
777:         fifo_tx_wr_en    <= axi_rvalid && axi_rready && (axi_rid == 4'b0000);
778:         fifo_tx_wr_data  <= axi_rdata;
779:     end
780: end
781: 
782: // //----------- Read Done Tracking ----------
783: // reg read_done_r;
784: // always @(posedge axi_clk or posedge axi_rst) begin
785: //     if (axi_rst)
786: //         read_done_r <= 1'b0;
787: //     else if (r_state == R_DATA_WAIT && axi_rvalid && axi_rready && axi_rlast && (read_beats_remain == 32'd0))
788: //         read_done_r <= 1'b1;
789: //     else
790: //         read_done_r <= 1'b0;
791: // end
792: 
793: //====================================================
794: // AXI Read Interface Logic - END
795: //====================================================
796: 
797: endmodule
