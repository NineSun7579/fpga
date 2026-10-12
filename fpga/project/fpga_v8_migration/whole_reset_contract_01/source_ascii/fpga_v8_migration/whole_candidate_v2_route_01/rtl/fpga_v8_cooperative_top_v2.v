1: // ==========================================
2: // \xef\xbf\xbd\xef\xbf\xbd\xc6\xb5\xd4\xb4\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd1\xa1\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xeb\xb1\xa3\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd2\xbb\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd7\xa2\xef\xbf\xbd\xcd\xb5\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd2\xbb\xef\xbf\xbd\xef\xbf\xbd
3: // ==========================================
4:  `define USE_OV5640
5: //`define USE_HDMI
6: 
7: 
8: module fpga_v8_cooperative_top_v2 #(
9:     parameter   MSI_NUM = 5,
10:     parameter   AXI_ID_LEN      = 4, 
11:                 AXI_ID_M_LEN    = $clog2(7) + AXI_ID_LEN,
12: 		        AXI_DATA_LEN    = 128, 
13: 		        AXI_DATA_SIZE   = $clog2(AXI_DATA_LEN/8), 	        
14: 		        AXI_STRB_LEN    = AXI_DATA_LEN / 8, 
15:                 AXI_ADDR_WIDTH  = 32,  
16:                 BURST_LEN = 16, // [ZEROFIX 2026-09-19] 16-beat bursts = IP max awlen+1 = FIFO depth;
17:                                 // the staging gate then requires a FULL FIFO before the AW
18:                                 // is presented, so the IP can never consume an empty slot
19:                                 // (that produced the 8-on/8-off zero blocks in DDR).
20:                                 // prior: BURST_LEN = 8,  // [WATERFIX2 2026-09-19] 16-beat bursts into the 16-deep ddr_fifo16_w
21:                                 // had zero slack: one stalled drain cycle dropped a W beat and
22:                                 // the DDR3 IP (never seeing awlen+1 beats) killed the whole M00
23:                                 // write path. 8-beat bursts + the free-space AW gate leave 2x room.
24:                                 // with single-beat bursts (every beat needs its own B
25:                                 // before the next is issued). 16-beat bursts cut the B
26:                                 // demand 16x and keep one outstanding txn per master.
27:                                 // [ZDIAG 2026-09-18] old '=16 stripes unchanged' verdict
28:                                 // predates the ledger fix and is not applicable.
29: 
30:     //DDR3
31:     parameter  MEM_ROW_WIDTH    = 15         ,
32:                MEM_COLUMN_WIDTH = 10         ,
33:                MEM_BANK_WIDTH   = 3          ,
34:                MEM_DQ_WIDTH     = 16         ,
35:                MEM_DQS_WIDTH    = 2          ,
36:                CTRL_ADDR_WIDTH  = MEM_ROW_WIDTH + MEM_BANK_WIDTH + MEM_COLUMN_WIDTH
37: )(
38: 
39:     input                       free_clk         /* synthesis PAP_MARK_DEBUG="<3/c0/0>" */,       //25MHZ
40:     input                       button_rst_n    ,
41: 
42:     ////////////////// PCIE ////////////////
43:     input                       perst_n         ,
44:     input                       ref_clk_n       ,      
45:     input                       ref_clk_p       ,      
46:     input           [1:0]       rxn             ,
47:     input           [1:0]       rxp             ,
48:     output  wire    [1:0]       txn             ,
49:     output  wire    [1:0]       txp             ,
50:     output wire                 ref_led         ,
51:     output wire                 pclk_led        ,
52: 
53:     ////////////////// SFP fiber RX (QR3 HSST CH2) [SFP 2026-09-29] ////////////////
54:     // ref clock shared with PCIe (ref_clk_p/n F6/E6, 100MHz)
55:     input                       sfp_l2rxn       ,
56:     input                       sfp_l2rxp       ,
57:     output wire                 sfp_l2txn       ,
58:     output wire                 sfp_l2txp       ,
59:     output wire                 sfp_tx_disable  ,
60:     // output wire                 smlh_link_up     ,
61:     // output wire                 rdlh_link_up     ,
62: 
63: 
64: 
65:     ////////////DDR3
66:     output                               mem_cs_n                  ,  
67:     output                               mem_rst_n                 ,
68:     output                               mem_ck                    ,
69:     output                               mem_ck_n                  ,
70:     output                               mem_cke                   ,
71:     output                               mem_ras_n                 ,
72:     output                               mem_cas_n                 ,
73:     output                               mem_we_n                  ,
74:     output                               mem_odt                   ,
75:     output      [MEM_ROW_WIDTH-1:0]      mem_a                     ,
76:     output      [MEM_BANK_WIDTH-1:0]     mem_ba                    ,
77:     inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs                   ,
78:     inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs_n                 ,
79:     inout       [MEM_DQ_WIDTH-1:0]       mem_dq                    ,
80:     output      [MEM_DQ_WIDTH/8-1:0]     mem_dm                    ,
81: 
82:     output reg                           heart_beat_led            ,
83: 
84: `ifdef USE_OV5640
85:     /////////////CAM
86:     input                                cmos1_pclk               /* synthesis PAP_MARK_DEBUG="<1/c0/0>,<3/t0/0>" */, 
87:     input                                cmos1_vsync              /* synthesis PAP_MARK_DEBUG="<1/t0/0>,<3/t0/1>" */, 
88:     input                                cmos1_href               /* synthesis PAP_MARK_DEBUG="<1/t0/1>,<3/t0/2>" */, 
89:     input       [7 : 0]                  cmos1_data              , 
90:     output                               cmos1_rst_n             , 
91:     // output                               cmos1_pwdn              , 
92:     output                               cmos1_scl               , 
93:     inout                                cmos1_sda               ,                 
94: 
95: 
96: 
97:     /////////////CAM2 (FMC 2nd DVP camera)
98:     input                                cmos2_pclk               /* synthesis PAP_MARK_DEBUG="<2/c0/0>,<3/t0/3>" */, 
99:     input                                cmos2_vsync              /* synthesis PAP_MARK_DEBUG="<2/t0/0>,<3/t0/4>" */, 
100:     input                                cmos2_href               /* synthesis PAP_MARK_DEBUG="<2/t0/1>,<3/t0/5>" */, 
101:     input       [7 : 0]                  cmos2_data              , 
102:     output                               cmos2_rst_n             , 
103:     output                               cmos2_scl               , 
104:     inout                                cmos2_sda                 , 
105: 
106:     // ---- CAM3 (FMC 3rd OV5640) ----
107:     input                                cmos3_pclk               , 
108:     input                                cmos3_vsync              , 
109:     input                                cmos3_href               , 
110:     input       [7 : 0]                  cmos3_data              , 
111:     output                               cmos3_rst_n             , 
112:     output                               cmos3_scl               , 
113:     inout                                cmos3_sda               , 
114:     ///////////// CAM4 (FMC 4th DVP camera)
115:     input                                cmos4_pclk               , 
116:     input                                cmos4_vsync              , 
117:     input                                cmos4_href               , 
118:     input       [7 : 0]                  cmos4_data              , 
119:     output                               cmos4_rst_n             , 
120:     output                               cmos4_scl               , 
121:     inout                                cmos4_sda
122: `elsif USE_HDMI
123:     /////////////////////////  HDMI
124:     //ms72XX
125:     output            rstn_out,
126: 
127:     // FMC I2C 
128:     output            iic_scl,
129:     inout             iic_sda, 
130: 
131:     // output            iic_tx_scl,
132:     // inout             iic_tx_sda, 
133: 
134:     //HDMI IN
135:     input             pixclk_in ,                            
136:     input             vs_in     , 
137:     input             hs_in     , 
138:     input             de_in     ,
139:     input     [7:0]   r_in      , 
140:     input     [7:0]   g_in      , 
141:     input     [7:0]   b_in      
142: `endif
143: );
144: 
145:     wire clk_50m, clk_150m, clk_10m, locked;
146: 
147: 
148: ///////////////////////////// AXI wires between crossbar and DDR3 ///////////////////////////
149: wire [27:0]                 ddr_axi_awaddr     /* synthesis PAP_MARK_DEBUG="true" */;
150: wire                        ddr_axi_awuser_ap  ;
151: wire [AXI_ID_M_LEN-1:0]     ddr_axi_awuser_id  /* synthesis PAP_MARK_DEBUG="true" */;
152: wire [3:0]                  ddr_axi_awlen      /* synthesis PAP_MARK_DEBUG="true" */;
153: wire                        ddr_axi_awready    /* synthesis PAP_MARK_DEBUG="true" */;
154: wire                        ddr_axi_awvalid    /* synthesis PAP_MARK_DEBUG="true" */;
155: wire [2:0]                  ddr_axi_awsize     /* synthesis PAP_MARK_DEBUG="true" */;
156: wire [1:0]                  ddr_axi_awburst    /* synthesis PAP_MARK_DEBUG="true" */;
157: wire                        ddr_axi_awlock     ;
158: wire [3:0]                  ddr_axi_awcache    ;
159: wire [2:0]                  ddr_axi_awprot     ;
160: wire [3:0]                  ddr_axi_awqos      ;
161: 
162: wire [15:0] cam_s_data_available, cam2_s_data_available, cam3_s_data_available, cam4_s_data_available;
163: wire [AXI_DATA_LEN-1:0]     ddr_axi_wdata      /* synthesis PAP_MARK_DEBUG="true" */;
164: wire [AXI_DATA_LEN-1:0]     ddr_axi_wdata_ddr3      ;
165: wire [AXI_STRB_LEN-1:0]     ddr_axi_wstrb      /* synthesis PAP_MARK_DEBUG="true" */;
166: wire [AXI_STRB_LEN-1:0]     ddr_axi_wstrb_ddr3      ;
167: wire                        ddr_axi_fifo_full/* synthesis PAP_MARK_DEBUG="true" */;
168: wire                        ddr_axi_wvalid     /* synthesis PAP_MARK_DEBUG="true" */;
169: wire                        ddr_axi_wready_ddr3    ;
170: wire [AXI_ID_LEN-1:0]       ddr_axi_wusero_id  /* synthesis PAP_MARK_DEBUG="true" */;
171: wire                        ddr_axi_wusero_last_ddr3;
172: wire                        ddr_axi_wlast      /* synthesis PAP_MARK_DEBUG="true" */;
173: 
174: wire [1:0]                  ddr_axi_bresp      /* synthesis PAP_MARK_DEBUG="true" */;
175: wire                        ddr_axi_bvalid     /* synthesis PAP_MARK_DEBUG="true" */;
176: wire                        ddr_axi_bready     /* synthesis PAP_MARK_DEBUG="true" */;
177: wire [AXI_ID_M_LEN-1:0]     ddr_axi_bid        /* synthesis PAP_MARK_DEBUG="true" */;
178: 
179: 
180: 
181: wire [31:0]                 ddr_axi_araddr     ;
182: wire                        ddr_axi_aruser_ap  ;
183: wire [AXI_ID_M_LEN-1:0]     ddr_axi_aruser_id  ;
184: wire [AXI_DATA_LEN-1:0]     ddr_axi_aruser     ;
185: wire [7:0]                  ddr_axi_arlen      ;
186: wire                        ddr_axi_arready    /* synthesis PAP_MARK_DEBUG="true" */;
187: wire                        ddr_axi_arvalid    ;
188: 
189: wire [AXI_DATA_LEN-1:0]     ddr_axi_rdata      /* synthesis PAP_MARK_DEBUG="true" */;
190: wire [AXI_DATA_LEN-1:0]     ddr_axi_rdata_ddr3;
191: wire [AXI_ID_M_LEN-1:0]     ddr_axi_rid        /* synthesis PAP_MARK_DEBUG="true" */;
192: wire [AXI_ID_LEN-1:0]       ddr_axi_rid_ddr3;
193: wire                        ddr_axi_rlast      /* synthesis PAP_MARK_DEBUG="true" */;
194: wire                        ddr_axi_rlast_ddr3;
195: wire                        ddr_axi_rvalid     /* synthesis PAP_MARK_DEBUG="true" */;
196: wire                        ddr_axi_rvalid_ddr3;
197: wire                        ddr_axi_rready     /* synthesis PAP_MARK_DEBUG="true" */;
198: wire                        ddr_axi_fifo_empty;
199: 
200: 
201: 
202: 
203: 
204: wire [2:0]                  ddr_axi_arsize     /* synthesis PAP_MARK_DEBUG="true" */;
205: wire [1:0]                  ddr_axi_arburst    /* synthesis PAP_MARK_DEBUG="true" */;
206: wire                        ddr_axi_arlock     /* synthesis PAP_MARK_DEBUG="true" */;
207: wire [3:0]                  ddr_axi_arcache    /* synthesis PAP_MARK_DEBUG="true" */;
208: wire [2:0]                  ddr_axi_arprot     /* synthesis PAP_MARK_DEBUG="true" */;
209: wire [3:0]                  ddr_axi_arqos      /* synthesis PAP_MARK_DEBUG="true" */;
210: wire [1:0]                  ddr_axi_rresp      /* synthesis PAP_MARK_DEBUG="true" */;
211: 
212: 
213: wire [1:0]                  ddr_axi_buser      ;
214: wire [1:0]                  ddr_axi_ruser      ;
215: wire [1:0]                  ddr_axi_awuser     ;
216: wire [1:0]                  ddr_axi_wuser      ;
217: 
218: 
219: /////////////////////////////     DDR3   ///////////////////////////////////////////////////
220: parameter TH_1S = 27'd33000000;
221: reg  [26:0]                 cnt                        ;
222: always@(posedge core_clk or negedge ddr_init_done) begin
223:    if (!ddr_init_done)
224:       cnt <= 27'd0;
225:    else if ( cnt >= TH_1S )
226:       cnt <= 27'd0;
227:    else
228:       cnt <= cnt + 27'd1;
229: end
230: 
231: always @(posedge core_clk or negedge ddr_init_done) begin
232:    if (!ddr_init_done)
233:       heart_beat_led <= 1'd1;
234:    else if ( cnt >= TH_1S )
235:       heart_beat_led <= ~heart_beat_led;
236: end
237: 
238: // Cooperative DDR contract instances are declared below.
239: 
240: ddr3 #(
241:     .MEM_ROW_WIDTH              (MEM_ROW_WIDTH                ),
242:     .MEM_COLUMN_WIDTH           (MEM_COLUMN_WIDTH             ),
243:     .MEM_BANK_WIDTH             (MEM_BANK_WIDTH               ),
244:     .MEM_DQ_WIDTH               (MEM_DQ_WIDTH                 ),
245:     .MEM_DM_WIDTH               (MEM_DQS_WIDTH                ),
246:     .MEM_DQS_WIDTH              (MEM_DQS_WIDTH                ),
247:     .CTRL_ADDR_WIDTH            (CTRL_ADDR_WIDTH              )
248:   )
249: ddr3(
250:     .ref_clk                    (free_clk                     ),
251:     .resetn                     (button_rst_n                 ),
252: 
253:     .core_clk                   (core_clk                     ),
254:     .ddr_init_done              (ddr_init_done                ),
255: 
256:     .pll_lock                   (                             ),
257:     .phy_pll_lock               (                             ),
258:     .gpll_lock                  (                             ),
259:     .rst_gpll_lock              (                             ),
260:     .ddrphy_cpd_lock            (                             ),
261: 
262:     .axi_awaddr                 (ddr3_aw_addr                  ), // [AWFIX]
263:     .axi_awuser_ap              (ddr3_aw_ap                    ),
264:     .axi_awuser_id              (ddr3_aw_id                    ),
265:     .axi_awlen                  (ddr3_aw_len                   ),
266:     .axi_awready                (ddr_axi_awready               ),
267:     .axi_awvalid                (ddr3_aw_v                     ),
268: 
269:     .axi_wdata                  (ddr_axi_wdata_ddr3            ),
270:     .axi_wstrb                  (ddr_axi_wstrb_ddr3            ),
271:     .axi_wready                 (ddr_axi_wready_ddr3           ),
272:     .axi_wusero_id              (ddr_axi_wusero_id             ),
273:     .axi_wusero_last            (ddr_axi_wusero_last_ddr3      ),
274: 
275:     .axi_araddr                 (ddr3_ar_addr                  ), // [ARFIX]
276:     .axi_aruser_ap              (ddr3_ar_ap                    ),
277:     .axi_aruser_id              (ddr3_ar_id                    ),
278:     .axi_arlen                  (ddr3_ar_len                   ),
279:     .axi_arready                (ddr_axi_arready               ),
280:     .axi_arvalid                (ddr3_ar_v                     ),
281: 
282:     .axi_rdata                  (ddr_axi_rdata_ddr3                 ),
283:     .axi_rid                    (ddr_axi_rid_ddr3                   ),
284:     .axi_rlast                  (ddr_axi_rlast_ddr3                 ),
285:     .axi_rvalid                 (ddr_axi_rvalid_ddr3                ),
286: 
287:     .apb_clk                    (1'b0                         ),
288:     .apb_rst_n                  (1'b0                         ),
289:     .apb_sel                    (1'b0                         ),
290:     .apb_enable                 (1'b0                         ),
291:     .apb_addr                   (8'd0                         ),
292:     .apb_write                  (1'b0                         ),
293:     .apb_ready                  (                             ),
294:     .apb_wdata                  (16'd0                        ),
295:     .apb_rdata                  (                             ),
296: 
297:     .mem_cs_n                   (mem_cs_n                     ),
298:     .mem_rst_n                  (mem_rst_n                    ),
299:     .mem_ck                     (mem_ck                       ),
300:     .mem_ck_n                   (mem_ck_n                     ),
301:     .mem_cke                    (mem_cke                      ),
302:     .mem_ras_n                  (mem_ras_n                    ),
303:     .mem_cas_n                  (mem_cas_n                    ),
304:     .mem_we_n                   (mem_we_n                     ),
305:     .mem_odt                    (mem_odt                      ),
306:     .mem_a                      (mem_a                        ),
307:     .mem_ba                     (mem_ba                       ),
308:     .mem_dqs                    (mem_dqs                      ),
309:     .mem_dqs_n                  (mem_dqs_n                    ),
310:     .mem_dq                     (mem_dq                       ),
311:     .mem_dm                     (mem_dm                       ),
312: 
313:     .dbg_gate_start             (1'b0                         ),
314:     .dbg_cpd_start              (1'b0                         ),
315:     .dbg_ddrphy_rst_n           (1'b1                         ),
316:     .dbg_gpll_scan_rst          (1'b0                         ),
317: 
318:     .samp_position_dyn_adj      (1'b0                         ),
319:     .init_samp_position_even    (16'd0                        ),
320:     .init_samp_position_odd     (16'd0                        ),
321: 
322:     .wrcal_position_dyn_adj     (1'b0                         ),
323:     .init_wrcal_position        (16'd0                        ),
324: 
325:     .force_read_clk_ctrl        (1'b0                         ),
326:     .init_slip_step             (8'd0                         ),
327:     .init_read_clk_ctrl         (6'd0                         ),
328: 
329:     .debug_calib_ctrl           (                             ),
330:     .dbg_dll_upd_state          (                             ),
331:     .dbg_slice_status           (                             ),
332:     .dbg_slice_state            (                             ),
333:     .debug_data                 (                             ),
334:     .debug_gpll_dps_phase       (                             ),
335: 
336:     .dbg_rst_dps_state          (                             ),
337:     .dbg_tran_err_rst_cnt       (                             ),
338:     .dbg_ddrphy_init_fail       (                             ),
339: 
340:     .debug_cpd_offset_adj       (1'b0                         ),
341:     .debug_cpd_offset_dir       (1'b0                         ),
342:     .debug_cpd_offset           (10'd0                        ),
343:     .debug_dps_cnt_dir0         (                             ),
344:     .debug_dps_cnt_dir1         (                             ),
345: 
346:     .ck_dly_en                  (1'b0                         ),
347:     .init_ck_dly_step           (8'd0                         ),
348:     .ck_dly_set_bin             (                             ),
349: 
350:     .align_error                (                             ),
351:     .debug_rst_state            (                             ),
352:     .debug_cpd_state            (                             )
353:   );
354: 
355: wire axi_clk;
356: wire axi_rst;
357: assign axi_clk = core_clk;
358: assign axi_rst = ~ddr_init_done;
359: 
360: /////////////////////////////////////// [WARB 2026-09-19] camera write arbiter ///////
361: // Single-outstanding 2-master arbiter replacing the crossbar M00 write path.
362: // Bench-proven: 9741 consecutive bursts, zero wedge (sim/wedge/tb_wedge.v).
363: wire [3:0]   arb_s_awid;
364: wire [31:0]  arb_s_awaddr;
365: wire [7:0]   arb_s_awlen;
366: wire [2:0]   arb_s_awsize, arb_s_awprot;
367: wire [1:0]   arb_s_awburst;
368: wire         arb_s_awlock;
369: wire [3:0]   arb_s_awcache;
370: wire         arb_s_awvalid, arb_s_awready;
371: wire [127:0] arb_s_wdata;
372: wire [15:0]  arb_s_wstrb;
373: wire         arb_s_wlast, arb_s_wvalid, arb_s_wready;
374: wire [3:0]   arb_s_bid;
375: wire [1:0]   arb_s_bresp;
376: wire         arb_s_bvalid, arb_s_bready;
377: // parked crossbar M00 write ports
378: wire [6:0]   arb2x_awid;
379: wire [31:0]  arb2x_awaddr;
380: wire [7:0]   arb2x_awlen;
381: wire [2:0]   arb2x_awsize, arb2x_awprot;
382: wire [1:0]   arb2x_awburst;
383: wire         arb2x_awlock;
384: wire [3:0]   arb2x_awcache;
385: wire [3:0]   arb2x_awqos;
386: wire [1:0]   arb2x_awuser;
387: wire         arb2x_awvalid;
388: wire [127:0] arb2x_wdata;
389: wire [15:0]  arb2x_wstrb;
390: wire         arb2x_wlast, arb2x_wvalid;
391: wire [1:0]   arb2x_wuser;
392: // Seven-writer cooperative core and DDR adapter instantiated below.
393: 
394: /////////////////////////////     DDR3   ///////////////////////////////////////////////////
395:     wire       [AXI_ID_LEN-1:0]       pcie_axi_awid   ;
396:     wire       [31:0]                 pcie_axi_awaddr ;
397:     wire       [ 3:0]                 pcie_axi_awlen  ;
398:     wire       [ 2:0]                 pcie_axi_awsize ;
399:     wire       [ 1:0]                 pcie_axi_awburst;
400:     wire                              pcie_axi_awlock ;
401:     wire       [ 3:0]                 pcie_axi_awcache;
402:     wire       [ 2:0]                 pcie_axi_awprot ;
403:     wire       [ 3:0]                 pcie_axi_awqos  ;
404:     wire                              pcie_axi_awvalid;
405:     wire                              pcie_axi_awready;
406: 
407:     wire       [AXI_DATA_LEN-1:0]     pcie_axi_wdata  ;
408:     wire       [AXI_STRB_LEN-1:0]     pcie_axi_wstrb  ;
409:     wire                              pcie_axi_wlast  ;
410:     wire                              pcie_axi_wvalid ;
411:     wire                              pcie_axi_wready ;
412: 
413:     wire       [AXI_ID_LEN-1:0]       pcie_axi_bid    ;
414:     wire       [ 1:0]                 pcie_axi_bresp  ;
415:     wire                              pcie_axi_bvalid ;
416:     wire                              pcie_axi_bready ;
417: 
418:     wire       [AXI_ID_LEN-1:0]       pcie_axi_arid   ;
419:     wire       [31:0]                 pcie_axi_araddr ;
420:     wire       [ 3:0]                 pcie_axi_arlen  ;
421:     wire       [ 2:0]                 pcie_axi_arsize ;
422:     wire       [ 1:0]                 pcie_axi_arburst;
423:     wire                              pcie_axi_arlock ;
424:     wire       [ 3:0]                 pcie_axi_arcache;
425:     wire       [ 2:0]                 pcie_axi_arprot ;
426:     wire       [ 3:0]                 pcie_axi_arqos  ;
427:     wire                              pcie_axi_arvalid;
428:     wire                              pcie_axi_arready;
429: 
430:     wire       [AXI_ID_LEN-1:0]       pcie_axi_rid    ;
431:     wire       [AXI_DATA_LEN-1:0]     pcie_axi_rdata  ;
432:     wire       [ 1:0]                 pcie_axi_rresp  ;
433:     wire                              pcie_axi_rlast  ;
434:     wire                              pcie_axi_rvalid ;
435:     wire                              pcie_axi_rready ;
436: 
437:     wire                              pcie_clk        ;
438:     wire                              pcie_rst        ;
439: 
440:     wire [MSI_NUM-2 : 0]      msi_req       ;
441:     wire [MSI_NUM-2 : 0]      msi_grant     ;
442: 
443: 
444:     assign msi_req = {1'd0, 1'b0, 2'b00}; //[MSIFIX 2026-09-13] freerun: xdma_req stuck high = MSI storm, camera MSI off
445: 
446: fpga_v8_pcie_fifo_h2f #(
447:     .MSI_NUM(MSI_NUM)
448: )
449: pcie_fifo(    
450: 
451:     .button_rst_n(button_rst_n)    ,
452: 
453:     ////////////////// PCIE ////////////////
454:     .perst_n     (perst_n     )    ,
455:     .ref_clk_n   (ref_clk_n   )    ,      
456:     .ref_clk_p   (ref_clk_p   )    ,      
457:     .rxn         (rxn         )    ,
458:     .rxp         (rxp         )    ,
459:     .txn         (txn         )    ,
460:     .txp         (txp         )    ,
461:     .ref_led     (ref_led     )    ,
462:     .pclk_led    (pclk_led    )    ,
463:     // .smlh_link_up(smlh_link_up)    ,
464:     // .rdlh_link_up(rdlh_link_up)    ,
465: 
466:     .fifo_pcie_clk(pcie_clk   )    ,
467:     .fifo_pcie_rst(pcie_rst   )    ,
468: 
469:     .i_msi_req  (msi_req     )     ,
470:     .o_msi_grant(msi_grant   )     ,
471:     ///////////////// AXI FOR DDR3 //////////////////////////////
472:     .axi_clk(axi_clk),
473:     .axi_rst(axi_rst),
474: 
475:     .axi_awid   (pcie_axi_awid   )     ,
476:     .axi_awaddr (pcie_axi_awaddr )     ,
477:     .axi_awlen  (pcie_axi_awlen  )     ,
478:     .axi_awsize (pcie_axi_awsize )     ,
479:     .axi_awburst(pcie_axi_awburst)     ,
480:     .axi_awlock (pcie_axi_awlock )     ,
481:     .axi_awcache(pcie_axi_awcache)     ,
482:     .axi_awprot (pcie_axi_awprot )     ,
483:     .axi_awqos  (pcie_axi_awqos  )     ,
484:     .axi_awvalid(pcie_axi_awvalid)     ,
485:     .axi_awready(pcie_axi_awready)     ,
486:     
487:     .axi_wdata  (pcie_axi_wdata  )     ,
488:     .axi_wstrb  (pcie_axi_wstrb  )     ,
489:     .axi_wlast  (pcie_axi_wlast  )     ,
490:     .axi_wvalid (pcie_axi_wvalid )     ,
491:     .axi_wready (pcie_axi_wready )     ,
492:     
493:     .axi_bid    (pcie_axi_bid    )     ,
494:     .axi_bresp  (pcie_axi_bresp  )     ,
495:     .axi_bvalid (pcie_axi_bvalid )     ,
496:     .axi_bready (pcie_axi_bready )     ,
497:     
498:     .axi_arid   (pcie_axi_arid   )     ,
499:     .axi_araddr (pcie_axi_araddr )     ,
500:     .axi_arlen  (pcie_axi_arlen  )     ,
501:     .axi_arsize (pcie_axi_arsize )     ,
502:     .axi_arburst(pcie_axi_arburst)     ,
503:     .axi_arlock (pcie_axi_arlock )     ,
504:     .axi_arcache(pcie_axi_arcache)     ,
505:     .axi_arprot (pcie_axi_arprot )     ,
506:     .axi_arqos  (pcie_axi_arqos  )     ,
507:     .axi_arvalid(pcie_axi_arvalid)     ,
508:     .axi_arready(pcie_axi_arready)     ,
509:     
510:     .axi_rid    (pcie_axi_rid    )     ,
511:     .axi_rdata  (pcie_axi_rdata  )     ,
512:     .axi_rresp  (pcie_axi_rresp  )     ,
513:     .axi_rlast  (pcie_axi_rlast  )     ,
514:     .axi_rvalid (pcie_axi_rvalid )     ,
515:     .axi_rready (pcie_axi_rready )           
516: );
517: 
518: 
519: /////////////////////////////////   CMD    ////////////////////////////////////////////////
520: ov5640_clk ov5640_clk(
521:   .clkout2(clk_10m),
522:   .clkout1(clk_150m),      // output 150M
523:   .clkout0(),             //[CLKFIX 2026-09-13] PLL bypassed (never locks @25MHz in)
524: 
525:   .lock(locked),          // output
526:   .clkin1(free_clk)         // input
527: );
528: 
529: //[CLKFIX 2026-09-13] i2c domain runs on free_clk directly (25MHz)
530: assign clk_50m = free_clk;
531: 
532: ///////////////////////////// AXI-Lite wires for ovreg ///////////////////////////
533: wire [31:0]                 ovreg_axil_awaddr   ;
534: wire                        ovreg_axil_awvalid  ;
535: wire                        ovreg_axil_awready  ;
536: wire [31:0]                 ovreg_axil_wdata    ;
537: wire [3:0]                  ovreg_axil_wstrb    ;
538: wire                        ovreg_axil_wvalid   ;
539: wire                        ovreg_axil_wready   ;
540: wire [1:0]                  ovreg_axil_bresp    ;
541: wire                        ovreg_axil_bvalid   ;
542: wire                        ovreg_axil_bready   ;
543: wire [31:0]                 ovreg_axil_araddr   ;
544: wire                        ovreg_axil_arvalid  ;
545: wire                        ovreg_axil_arready  ;
546: wire [31:0]                 ovreg_axil_rdata    ;
547: wire [1:0]                  ovreg_axil_rresp    ;
548: wire                        ovreg_axil_rvalid   ;
549: wire                        ovreg_axil_rready   ;
550: 
551: // --- CAM segment (decoder m0, addr[8]=0: 0x2000_0000~0x2000_00FF -> ov5640_reg) ---
552: wire                        cam_axil_awvalid, cam_axil_awready;
553: wire [31:0]                 cam_axil_awaddr;
554: wire                        cam_axil_wvalid, cam_axil_wready;
555: wire [31:0]                 cam_axil_wdata;
556: wire [3:0]                  cam_axil_wstrb;
557: wire                        cam_axil_bvalid, cam_axil_bready;
558: wire [1:0]                  cam_axil_bresp;
559: wire                        cam_axil_arvalid, cam_axil_arready;
560: wire [31:0]                 cam_axil_araddr;
561: wire                        cam_axil_rvalid, cam_axil_rready;
562: wire [31:0]                 cam_axil_rdata;
563: wire [1:0]                  cam_axil_rresp;
564: 
565: // --- cam2 register window (M01 sub-window 0x2000_0200~0x02FF) ---
566: wire                        cam2_axil_awvalid, cam2_axil_awready;
567: wire [31:0]                 cam2_axil_awaddr;
568: wire                        cam2_axil_wvalid, cam2_axil_wready;
569: wire [31:0]                 cam2_axil_wdata;
570: wire [3:0]                  cam2_axil_wstrb;
571: wire                        cam2_axil_bvalid, cam2_axil_bready;
572: wire [1:0]                  cam2_axil_bresp;
573: wire                        cam2_axil_arvalid, cam2_axil_arready;
574: wire [31:0]                 cam2_axil_araddr;
575: wire                        cam2_axil_rvalid, cam2_axil_rready;
576: wire [31:0]                 cam2_axil_rdata;
577: wire [1:0]                  cam2_axil_rresp;
578: 
579: // --- cam3 register window (M01 sub-window 0x2000_0400~0x04FF) ---
580: wire                        cam3_axil_awvalid, cam3_axil_awready;
581: wire [31:0]                 cam3_axil_awaddr;
582: wire                        cam3_axil_wvalid, cam3_axil_wready;
583: wire [31:0]                 cam3_axil_wdata;
584: wire [3:0]                  cam3_axil_wstrb;
585: wire                        cam3_axil_bvalid, cam3_axil_bready;
586: wire [1:0]                  cam3_axil_bresp;
587: wire                        cam3_axil_arvalid, cam3_axil_arready;
588: wire [31:0]                 cam3_axil_araddr;
589: wire                        cam3_axil_rvalid, cam3_axil_rready;
590: wire [31:0]                 cam3_axil_rdata;
591: wire [1:0]                  cam3_axil_rresp;
592: 
593: // --- cam4 register window (M01 sub-window 0x2000_0600~0x07FF) ---
594: wire                        cam4_axil_awvalid, cam4_axil_awready;
595: wire [31:0]                 cam4_axil_awaddr;
596: wire                        cam4_axil_wvalid, cam4_axil_wready;
597: wire [31:0]                 cam4_axil_wdata;
598: wire [3:0]                  cam4_axil_wstrb;
599: wire                        cam4_axil_bvalid, cam4_axil_bready;
600: wire [1:0]                  cam4_axil_bresp;
601: wire                        cam4_axil_arvalid, cam4_axil_arready;
602: wire [31:0]                 cam4_axil_araddr;
603: wire                        cam4_axil_rvalid, cam4_axil_rready;
604: wire [31:0]                 cam4_axil_rdata;
605: wire [1:0]                  cam4_axil_rresp;
606: 
607: 
608: // --- cam2 capture / write stream (S04) ---
609: wire [31 : 0]               cam2_cmd_addr    ;
610: wire [31 : 0]               cam2_cmd_len     ;
611: wire                        cam2_cmd_valid   ;
612: wire                        cam2_cmd_ready   ;
613: wire [AXI_DATA_LEN-1 : 0]   cam2_s_data      ;
614: wire                        cam2_s_data_valid;
615: wire                        cam2_s_data_last ;
616: wire                        cam2_s_data_ready;
617: wire [AXI_ID_LEN-1:0]   cam2_axi_awid    ;
618: wire [31:0]             cam2_axi_awaddr  ;
619: wire [3:0]              cam2_axi_awlen   ;
620: wire [2:0]              cam2_axi_awsize  ;
621: wire [1:0]              cam2_axi_awburst ;
622: wire                    cam2_axi_awlock  ;
623: wire [3:0]              cam2_axi_awcache ;
624: wire [2:0]              cam2_axi_awprot  ;
625: wire                    cam2_axi_awvalid ;
626: wire                    cam2_axi_awready ;
627: wire [AXI_DATA_LEN-1:0] cam2_axi_wdata   ;
628: wire [AXI_STRB_LEN-1:0] cam2_axi_wstrb   ;
629: wire                    cam2_axi_wlast   ;
630: wire                    cam2_axi_wvalid  ;
631: wire                    cam2_axi_wready  ;
632: wire [AXI_ID_LEN-1:0]   cam2_axi_bid     ;
633: wire [1:0]              cam2_axi_bresp   ;
634: wire                    cam2_axi_bvalid  ;
635: wire                    cam2_axi_bready  ;
636: 
637: // --- PREP segment (decoder m1, addr[8]=1: 0x2000_0100~0x2000_01FF -> prep_regs) ---
638: wire                        prep_axil_awvalid, prep_axil_awready;
639: wire [31:0]                 prep_axil_awaddr;
640: wire                        prep_axil_wvalid, prep_axil_wready;
641: wire [31:0]                 prep_axil_wdata;
642: wire [3:0]                  prep_axil_wstrb;
643: wire                        prep_axil_bvalid, prep_axil_bready;
644: wire [1:0]                  prep_axil_bresp;
645: wire                        prep_axil_arvalid, prep_axil_arready;
646: wire [31:0]                 prep_axil_araddr;
647: wire                        prep_axil_rvalid, prep_axil_rready;
648: wire [31:0]                 prep_axil_rdata;
649: wire [1:0]                  prep_axil_rresp;
650: 
651: ///////////////////////////// ovreg_axi signals ///////////////////////////
652: wire [AXI_ID_M_LEN-1:0]     ovreg_axi_awid     ;
653: wire [31:0]                 ovreg_axi_awaddr   ;
654: wire [3:0]                  ovreg_axi_awlen    ;
655: wire [2:0]                  ovreg_axi_awsize   ;
656: wire [1:0]                  ovreg_axi_awburst  ;
657: wire                        ovreg_axi_awlock   ;
658: wire [3:0]                  ovreg_axi_awcache  ;
659: wire [2:0]                  ovreg_axi_awprot   ;
660: wire [3:0]                  ovreg_axi_awqos    ;
661: wire [3:0]                  ovreg_axi_awregion ;
662: wire                        ovreg_axi_awvalid  ;
663: wire                        ovreg_axi_awready  ;
664: 
665: wire [AXI_DATA_LEN-1:0]     ovreg_axi_wdata     ;
666: wire [AXI_STRB_LEN-1:0]     ovreg_axi_wstrb     ;
667: wire                        ovreg_axi_wlast     ;
668: wire                        ovreg_axi_wvalid    ;
669: wire                        ovreg_axi_wready    ;
670: 
671: wire [AXI_ID_M_LEN-1:0]     ovreg_axi_bid       ;
672: wire [1:0]                  ovreg_axi_bresp     ;
673: wire                        ovreg_axi_bvalid    ;
674: wire                        ovreg_axi_bready    ;
675: 
676: wire [AXI_ID_M_LEN-1:0]     ovreg_axi_arid     ;
677: wire [31:0]                 ovreg_axi_araddr   ;
678: wire [3:0]                  ovreg_axi_arlen    ;
679: wire [2:0]                  ovreg_axi_arsize   ;
680: wire [1:0]                  ovreg_axi_arburst  ;
681: wire                        ovreg_axi_arlock   ;
682: wire [3:0]                  ovreg_axi_arcache  ;
683: wire [2:0]                  ovreg_axi_arprot   ;
684: wire [3:0]                  ovreg_axi_arqos    ;
685: wire [3:0]                  ovreg_axi_arregion ;
686: wire                        ovreg_axi_arvalid  ;
687: wire                        ovreg_axi_arready  ;
688: 
689: wire [AXI_DATA_LEN-1:0]     ovreg_axi_rdata    ;
690: wire [AXI_ID_M_LEN-1:0]     ovreg_axi_rid      ;
691: wire [1:0]                  ovreg_axi_rresp    ;
692: wire                        ovreg_axi_rlast    ;
693: wire                        ovreg_axi_rvalid   ;
694: wire                        ovreg_axi_rready   ;
695: 
696: 
697: axi_to_axi_lite #(
698:     .AXI_ID_LEN(AXI_ID_M_LEN)
699: )
700: axi_to_axi_lite(
701:     .axi_clk(axi_clk),
702:     .axi_rst(axi_rst),
703:     // ==========================================
704:     // ??? AXI Slave  (128-bit)
705:     // ==========================================
706:     .s_axi_awid    (ovreg_axi_awid    ),
707:     .s_axi_awaddr  (ovreg_axi_awaddr  ),
708:     .s_axi_awlen   (ovreg_axi_awlen   ),
709:     .s_axi_awsize  (ovreg_axi_awsize  ),
710:     .s_axi_awburst (ovreg_axi_awburst ),
711:     .s_axi_awlock  (ovreg_axi_awlock  ),
712:     .s_axi_awcache (ovreg_axi_awcache ),
713:     .s_axi_awprot  (ovreg_axi_awprot  ),
714:     .s_axi_awqos   (ovreg_axi_awqos   ),
715:     .s_axi_awregion(ovreg_axi_awregion),
716:     .s_axi_awvalid (ovreg_axi_awvalid ),
717:     .s_axi_awready (ovreg_axi_awready ),
718: 
719:     .s_axi_wdata   (ovreg_axi_wdata  ),
720:     .s_axi_wstrb   (ovreg_axi_wstrb  ),
721:     .s_axi_wlast   (ovreg_axi_wlast  ),
722:     .s_axi_wvalid  (ovreg_axi_wvalid ),
723:     .s_axi_wready  (ovreg_axi_wready ),
724: 
725:     .s_axi_bid     (ovreg_axi_bid    ),
726:     .s_axi_bresp   (ovreg_axi_bresp  ),
727:     .s_axi_bvalid  (ovreg_axi_bvalid ),
728:     .s_axi_bready  (ovreg_axi_bready ),
729: 
730:     .s_axi_arid    (ovreg_axi_arid   ),
731:     .s_axi_araddr  (ovreg_axi_araddr ),
732:     .s_axi_arlen   (ovreg_axi_arlen  ),
733:     .s_axi_arsize  (ovreg_axi_arsize ),
734:     .s_axi_arburst (ovreg_axi_arburst),
735:     .s_axi_arlock  (ovreg_axi_arlock ),
736:     .s_axi_arcache (ovreg_axi_arcache),
737:     .s_axi_arprot  (ovreg_axi_arprot ),
738:     .s_axi_arqos   (ovreg_axi_arqos  ),
739:     .s_axi_arregion(ovreg_axi_arregion),
740:     .s_axi_arvalid (ovreg_axi_arvalid),
741:     .s_axi_arready (ovreg_axi_arready),
742: 
743:     .s_axi_rid     (ovreg_axi_rid    ),
744:     .s_axi_rdata   (ovreg_axi_rdata  ),
745:     .s_axi_rresp   (ovreg_axi_rresp  ),
746:     .s_axi_rlast   (ovreg_axi_rlast  ),
747:     .s_axi_rvalid  (ovreg_axi_rvalid ),
748:     .s_axi_rready  (ovreg_axi_rready ),
749: 
750: 
751:     // ==========================================
752:     // AXI-Lite Master  (32-bit)
753:     // ==========================================
754:     .m_axil_awaddr (ovreg_axil_awaddr ),
755:     .m_axil_awvalid(ovreg_axil_awvalid),
756:     .m_axil_awready(ovreg_axil_awready),
757: 
758:     .m_axil_wdata  (ovreg_axil_wdata  ),
759:     .m_axil_wstrb  (ovreg_axil_wstrb  ),
760:     .m_axil_wvalid (ovreg_axil_wvalid ),
761:     .m_axil_wready (ovreg_axil_wready ),
762: 
763:     .m_axil_bresp  (ovreg_axil_bresp  ),
764:     .m_axil_bvalid (ovreg_axil_bvalid ),
765:     .m_axil_bready (ovreg_axil_bready ),
766: 
767:     .m_axil_araddr (ovreg_axil_araddr ),
768:     .m_axil_arvalid(ovreg_axil_arvalid),
769:     .m_axil_arready(ovreg_axil_arready),
770: 
771:     .m_axil_rdata  (ovreg_axil_rdata  ),
772:     .m_axil_rresp  (ovreg_axil_rresp  ),
773:     .m_axil_rvalid (ovreg_axil_rvalid ),
774:     .m_axil_rready (ovreg_axil_rready )
775: );
776: 
777: 
778: wire [31 : 0]               cam_cmd_addr    /*synthesis PAP_MARK_DEBUG="1"*/;
779: wire [31 : 0]               cam_cmd_len     /*synthesis PAP_MARK_DEBUG="1"*/;
780: wire                        cam_cmd_valid   /*synthesis PAP_MARK_DEBUG="1"*/;
781: wire                        cam_cmd_ready   /*synthesis PAP_MARK_DEBUG="1"*/;
782: 
783: wire [AXI_DATA_LEN-1 : 0]   cam_s_data      /*synthesis PAP_MARK_DEBUG="1"*/;
784: // preprocess tap (camera raw stream -> preprocess -> processed write)
785: wire [AXI_DATA_LEN-1 : 0]   cam_tap_data    ;
786: wire                        cam_tap_data_valid;
787: wire                        cam_tap_data_last ;
788: wire                        cam_tap_data_ready;
789: wire                        cam_s_data_valid/*synthesis PAP_MARK_DEBUG="1"*/;
790: wire                        cam_s_data_last /*synthesis PAP_MARK_DEBUG="1"*/;
791: wire                        cam_s_data_ready/*synthesis PAP_MARK_DEBUG="1"*/;
792: 
793: wire [1 : 0]                cam_irq;     
794: 
795: // --- AXI-Lite address decoder: splits M01 window by addr[8] ---
796: //   addr[8]=0 -> ov5640_reg segment (CAM regs)
797: //   addr[8]=1 -> prep_regs segment  (PREP/INJ regs, doc +0x100~0x17C)
798: ovreg_axil_decode ovreg_axil_decode_u (
799:     .clk        (axi_clk),
800:     .rst        (axi_rst),
801:     .s_awvalid  (ovreg_axil_awvalid),
802:     .s_awready  (ovreg_axil_awready),
803:     .s_awaddr   (ovreg_axil_awaddr),
804:     .s_wvalid   (ovreg_axil_wvalid),
805:     .s_wready   (ovreg_axil_wready),
806:     .s_wdata    (ovreg_axil_wdata),
807:     .s_wstrb    (ovreg_axil_wstrb),
808:     .s_bvalid   (ovreg_axil_bvalid),
809:     .s_bready   (ovreg_axil_bready),
810:     .s_bresp    (ovreg_axil_bresp),
811:     .s_arvalid  (ovreg_axil_arvalid),
812:     .s_arready  (ovreg_axil_arready),
813:     .s_araddr   (ovreg_axil_araddr),
814:     .s_rvalid   (ovreg_axil_rvalid),
815:     .s_rready   (ovreg_axil_rready),
816:     .s_rdata    (ovreg_axil_rdata),
817:     .s_rresp    (ovreg_axil_rresp),
818:     .m0_awvalid (cam_axil_awvalid),
819:     .m0_awready (cam_axil_awready),
820:     .m0_awaddr  (cam_axil_awaddr),
821:     .m0_wvalid  (cam_axil_wvalid),
822:     .m0_wready  (cam_axil_wready),
823:     .m0_wdata   (cam_axil_wdata),
824:     .m0_wstrb   (cam_axil_wstrb),
825:     .m0_bvalid  (cam_axil_bvalid),
826:     .m0_bready  (cam_axil_bready),
827:     .m0_bresp   (cam_axil_bresp),
828:     .m0_arvalid (cam_axil_arvalid),
829:     .m0_arready (cam_axil_arready),
830:     .m0_araddr  (cam_axil_araddr),
831:     .m0_rvalid  (cam_axil_rvalid),
832:     .m0_rready  (cam_axil_rready),
833:     .m0_rdata   (cam_axil_rdata),
834:     .m0_rresp   (cam_axil_rresp),
835:     .m1_awvalid (prep_axil_awvalid),
836:     .m1_awready (prep_axil_awready),
837:     .m1_awaddr  (prep_axil_awaddr),
838:     .m1_wvalid  (prep_axil_wvalid),
839:     .m1_wready  (prep_axil_wready),
840:     .m1_wdata   (prep_axil_wdata),
841:     .m1_wstrb   (prep_axil_wstrb),
842:     .m1_bvalid  (prep_axil_bvalid),
843:     .m1_bready  (prep_axil_bready),
844:     .m1_bresp   (prep_axil_bresp),
845:     .m1_arvalid (prep_axil_arvalid),
846:     .m1_arready (prep_axil_arready),
847:     .m1_araddr  (prep_axil_araddr),
848:     .m1_rvalid  (prep_axil_rvalid),
849:     .m1_rready  (prep_axil_rready),
850:     .m1_rdata   (prep_axil_rdata),
851:     .m1_rresp   (prep_axil_rresp),
852: 
853:     .m2_awvalid (cam2_axil_awvalid),
854:     .m2_awready (cam2_axil_awready),
855:     .m2_awaddr  (cam2_axil_awaddr),
856:     .m2_wvalid  (cam2_axil_wvalid),
857:     .m2_wready  (cam2_axil_wready),
858:     .m2_wdata   (cam2_axil_wdata),
859:     .m2_wstrb   (cam2_axil_wstrb),
860:     .m2_bvalid  (cam2_axil_bvalid),
861:     .m2_bready  (cam2_axil_bready),
862:     .m2_bresp   (cam2_axil_bresp),
863:     .m2_arvalid (cam2_axil_arvalid),
864:     .m2_arready (cam2_axil_arready),
865:     .m2_araddr  (cam2_axil_araddr),
866:     .m2_rvalid  (cam2_axil_rvalid),
867:     .m2_rready  (cam2_axil_rready),
868:     .m2_rdata   (cam2_axil_rdata),
869:     .m2_rresp   (cam2_axil_rresp),
870: 
871:     .m3_awvalid (cam3_axil_awvalid),
872:     .m3_awready (cam3_axil_awready),
873:     .m3_awaddr  (cam3_axil_awaddr),
874:     .m3_wvalid  (cam3_axil_wvalid),
875:     .m3_wready  (cam3_axil_wready),
876:     .m3_wdata   (cam3_axil_wdata),
877:     .m3_wstrb   (cam3_axil_wstrb),
878:     .m3_bvalid  (cam3_axil_bvalid),
879:     .m3_bready  (cam3_axil_bready),
880:     .m3_bresp   (cam3_axil_bresp),
881:     .m3_arvalid (cam3_axil_arvalid),
882:     .m3_arready (cam3_axil_arready),
883:     .m3_araddr  (cam3_axil_araddr),
884:     .m3_rvalid  (cam3_axil_rvalid),
885:     .m3_rready  (cam3_axil_rready),
886:     .m3_rdata   (cam3_axil_rdata),
887:     .m3_rresp   (cam3_axil_rresp),
888:     .m4_awvalid (cam4_axil_awvalid),
889:     .m4_awready (cam4_axil_awready),
890:     .m4_awaddr  (cam4_axil_awaddr),
891:     .m4_wvalid  (cam4_axil_wvalid),
892:     .m4_wready  (cam4_axil_wready),
893:     .m4_wdata   (cam4_axil_wdata),
894:     .m4_wstrb   (cam4_axil_wstrb),
895:     .m4_bvalid  (cam4_axil_bvalid),
896:     .m4_bready  (cam4_axil_bready),
897:     .m4_bresp   (cam4_axil_bresp),
898:     .m4_arvalid (cam4_axil_arvalid),
899:     .m4_arready (cam4_axil_arready),
900:     .m4_araddr  (cam4_axil_araddr),
901:     .m4_rvalid  (cam4_axil_rvalid),
902:     .m4_rready  (cam4_axil_rready),
903:     .m4_rdata   (cam4_axil_rdata),
904:     .m4_rresp   (cam4_axil_rresp)
905: );
906: 
907: // --- prep datapath wiring ---
908: wire                        prep_bypass_w;
909: wire [1:0]                  prep_mode_w;
910: wire [11:0]                 prep_img_width_w;
911: wire [7:0]                  prep_thr_sat_w, prep_thr_hue_w, prep_thr_val_w, prep_thr_low_w;
912: wire [10:0]                 prep_thr_edge_w;
913: wire [7:0]                  prep_lane_roi_top_w, prep_lane_roi_bot_w, prep_lane_row_thr_w, prep_lane_dash_thr_w;
914: wire cam_dma_abort, cam_dma_abort_req;
915: wire cam2_dma_abort, cam2_dma_abort_req;
916: wire cam3_dma_abort, cam3_dma_abort_req;
917: wire cam4_dma_abort, cam4_dma_abort_req;
918: wire [7:0]                  prep_frame_cnt;
919: wire [15:0]                 inj_addr_w, inj_len_w, inj_fid_w;
920: wire                        inj_start_w, inj_done_clr_w;
921: wire [3:0]                  btn_sticky_w, btn_sticky_clr_w, led_ctrl_w;
922: wire [31:0]                 ts0_w, ts1_w, ts2_w, ts3_w;
923: 
924: // --- PREP/INJ registers (doc +0x100~0x17C). Register stage only: datapath
925: //     inputs tied to defaults until the preprocess pipeline is integrated.
926: wire [319:0] cam1_motion_record, cam2_motion_record, cam3_motion_record;
927: // Four local CAM1-4 motion detectors; SFP CAM5/6 record slots stay reserved.
928: wire [319:0] cam4_motion_record;
929: wire [319:0] cam5_motion_record = 320'b0;
930: wire [319:0] cam6_motion_record = 320'b0;
931: wire [1919:0] motion_records = {cam6_motion_record, cam5_motion_record,
932:     cam4_motion_record, cam3_motion_record, cam2_motion_record, cam1_motion_record};
933: prep_regs #(.TICK_DIV(50), .SFP_DIAG_EN(1)) prep_regs_u (
934:     .motion_records(motion_records),
935:     .sfp_diag_status(sfp_diag_status),
936:     .sfp_diag_fault5(cam5_diag_fault),
937:     .sfp_diag_fault6(cam6_diag_fault),
938:     .sfp_diag_pixels5(cam5_diag_pixels),
939:     .sfp_diag_pixels6(cam6_diag_pixels),
940:     .sfp_diag_states({cam6_diag_state[15:0], cam5_diag_state[15:0]}),
941:     .sfp_diag_rejects({cam6_diag_rejects[15:0], cam5_diag_rejects[15:0]}),
942:     .clk              (axi_clk),
943:     .rst_n            (~axi_rst),
944:     .s_axi_awvalid    (prep_axil_awvalid),
945:     .s_axi_awready    (prep_axil_awready),
946:     .s_axi_awaddr     (prep_axil_awaddr),
947:     .s_axi_wvalid     (prep_axil_wvalid),
948:     .s_axi_wready     (prep_axil_wready),
949:     .s_axi_wdata      (prep_axil_wdata),
950:     .s_axi_wstrb      (prep_axil_wstrb),
951:     .s_axi_bvalid     (prep_axil_bvalid),
952:     .s_axi_bready     (prep_axil_bready),
953:     .s_axi_bresp      (prep_axil_bresp),
954:     .s_axi_arvalid    (prep_axil_arvalid),
955:     .s_axi_arready    (prep_axil_arready),
956:     .s_axi_araddr     (prep_axil_araddr),
957:     .s_axi_rvalid     (prep_axil_rvalid),
958:     .s_axi_rready     (prep_axil_rready),
959:     .s_axi_rdata      (prep_axil_rdata),
960:     .s_axi_rresp      (prep_axil_rresp),
961:     .prep_bypass      (prep_bypass_w),
962:     .prep_mode        (prep_mode_w),
963:     .prep_img_width   (prep_img_width_w),
964:     .prep_thr_sat     (prep_thr_sat_w),
965:     .prep_thr_hue     (prep_thr_hue_w),
966:     .prep_thr_val     (prep_thr_val_w),
967:     .prep_thr_low     (prep_thr_low_w),
968:     .prep_thr_edge    (prep_thr_edge_w),
969:     .prep_lane_roi_top(prep_lane_roi_top_w),
970:     .prep_lane_roi_bot(prep_lane_roi_bot_w),
971:     .prep_lane_row_thr(prep_lane_row_thr_w),
972:     .prep_lane_dash_thr(prep_lane_dash_thr_w),
973:     .inj_addr         (),
974:     .inj_len          (),
975:     .inj_frame_id     (),
976:     .inj_start        (),
977:     .inj_done_clr     (),
978:     .inj_busy         (1'b0),
979:     .inj_done         (1'b0),
980:     .inj_done_fid     (16'd0),
981:     .pipe_frame_sync  (prep_out_frame_start),
982:     .pipe_fifo_afull  (1'b0),
983:     .npu_busy         (1'b0),
984:     .out_frame_cnt    (prep_frame_cnt),
985:     .btn_toggle_evt   (4'd0),
986:     // [SFP-STATUS 2026-09-30] +0x144 = SFP \xef\xbf\xbd\xef\xbf\xbd\xc2\xb7\xd7\xb4\xcc\xac: bit0=pll_lock1 bit1=txlane_done2 bit2=rxlane_done2 bit3=pcs_synced2
987:     .btn_level_sync   (sfp_status_bits),
988:     .btn_sticky       (),
989:     .btn_sticky_clr   (),
990:     .led_ctrl         (),
991:     .lane_left_type   (lane_left_type_w),
992:     .lane_right_type  (lane_right_type_w),
993:     .lane_left_valid  (lane_left_valid_w),
994:     .lane_right_valid (lane_right_valid_w),
995:     .lane_frame_upd   (lane_frame_upd_w),
996:     .ts_cap_pulse     (1'b0),
997:     .ts_prep_pulse    (1'b0),
998:     .ts_npu_pulse     (1'b0),
999:     .ts_dma_pulse     (1'b0),
1000:     .ts_value0        (),
1001:     .ts_value1        (),
1002:     .ts_value2        (),
1003:     .ts_value3        ()
1004: );
1005: 
1006: reg [15:0] camera_startup_count = 16'd0;
1007: reg camera_ctrl_rst_n = 1'b0;
1008: always @(posedge clk_50m) begin
1009:     if (!camera_ctrl_rst_n) begin
1010:         if (&camera_startup_count)
1011:             camera_ctrl_rst_n <= 1'b1;
1012:         else
1013:             camera_startup_count <= camera_startup_count + 1'b1;
1014:     end
1015: end
1016: 
1017: `ifdef USE_OV5640
1018: ov5640_top #(
1019:     .IODELAY_STEP  (8'd140),
1020:     .MEDIAN_EN     (1'b0)        , // [MEDIAN] disabled; cam1 uses FIR below
1021:     .MEDIAN_RSVD   (3'd0),
1022:     .KF_EN         (1'b0)         , // [VKFS] disabled; cam1 uses FIR
1023:     .KF_RD_EN      (1'b0)         // [VKFS] no previous-frame DDR read
1024: ) ov5640_top(
1025:     .motion_record(cam1_motion_record),
1026:     .clk_50m       (clk_50m)        ,
1027:     .clk_50m_rst_n (camera_ctrl_rst_n),
1028:     .dbg_locked    (locked)         ,
1029:     .dbg_btn_rst_n (button_rst_n)   ,
1030:     .dbg_axi_awvalid(ov5640_axi_awvalid),
1031:     .dbg_axi_awready(ov5640_axi_awready),
1032:     .dbg_axi_wvalid (ov5640_axi_wvalid ),
1033:     .dbg_axi_wready (ov5640_axi_wready ),
1034:     .dbg_axi_bvalid (ov5640_axi_bvalid ),
1035:     .dbg_axi_bready (ov5640_axi_bready ),
1036:         
1037:     .cam_pclk (cmos1_pclk )             ,  
1038:     .cam_vsync(cmos1_vsync)             ,  
1039:     .cam_href (cmos1_href )             ,  
1040:     .cam_data (cmos1_data )             ,  
1041:     .cam_rst_n(cmos1_rst_n)             ,  
1042:     // .cam_pwdn (cmos1_pwdn )             ,  
1043:     .cam_scl  (cmos1_scl  )             ,  
1044:     .cam_sda  (cmos1_sda  )             ,  
1045: 
1046: 
1047:     
1048:     .s_axi_awvalid(cam_axil_awvalid)        ,
1049:     .s_axi_awready(cam_axil_awready)        ,
1050:     .s_axi_awaddr (cam_axil_awaddr )        ,
1051: 
1052:     .s_axi_wvalid (cam_axil_wvalid)         ,
1053:     .s_axi_wready (cam_axil_wready)         ,
1054:     .s_axi_wdata  (cam_axil_wdata )         ,
1055:     .s_axi_wstrb  (cam_axil_wstrb )         ,
1056: 
1057:     .s_axi_bvalid (cam_axil_bvalid)         ,
1058:     .s_axi_bready (cam_axil_bready)         ,
1059:     .s_axi_bresp  (cam_axil_bresp )         ,
1060: 
1061:     .s_axi_arvalid(cam_axil_arvalid)        ,
1062:     .s_axi_arready(cam_axil_arready)        ,
1063:     .s_axi_araddr (cam_axil_araddr )        ,
1064: 
1065:     .s_axi_rvalid (cam_axil_rvalid )        ,
1066:     .s_axi_rready (cam_axil_rready )        ,
1067:     .s_axi_rdata  (cam_axil_rdata  )        ,
1068:     .s_axi_rresp  (cam_axil_rresp  )        ,
1069: 
1070: 
1071: 
1072:     //AXI_stream
1073:     .video_clk(axi_clk)      ,
1074:     .video_rst(axi_rst)      ,
1075:     .cam_cmd_addr (cam_cmd_addr )  ,
1076:     .cam_cmd_len  (cam_cmd_len  )  ,
1077:     .cam_cmd_valid(cam_cmd_valid)  ,
1078:     .cam_cmd_ready(cam_cmd_ready)  ,
1079: 
1080:     .cam_s_data      (cam_tap_data      ),
1081:     .cam_s_data_valid(cam_tap_data_valid),
1082:     .cam_s_data_last (cam_tap_data_last ),
1083:     .cam_s_data_ready(cam_tap_data_ready),
1084: 
1085:     //DMA?
1086:     .cam_dma_abort(cam_dma_abort),
1087:     .cam_s_data_available(cam_s_data_available),
1088:     .cam_dma_abort_req(cam_dma_abort_req),
1089:     .cam_dma_done(cam_dma_done),
1090:     .xdma_clk (pcie_clk) ,
1091:     .xdma_irq (cam_irq ) ,
1092: 
1093:     // [VKFS 2026-09-25] previous-frame read master -> crossbar S05 (npu_s3_*)
1094:     .kf_arvalid (npu_s3_axi_arvalid),
1095:     .kf_arready (npu_s3_axi_arready),
1096:     .kf_araddr  (npu_s3_axi_araddr ),
1097:     .kf_arlen   (npu_s3_axi_arlen  ),
1098:     .kf_arsize  (npu_s3_axi_arsize ),
1099:     .kf_arburst (npu_s3_axi_arburst),
1100:     .kf_arlock  (npu_s3_axi_arlock ),
1101:     .kf_arcache (npu_s3_axi_arcache),
1102:     .kf_arprot  (npu_s3_axi_arprot ),
1103:     .kf_arid    (npu_s3_axi_arid   ),
1104:     .kf_rready  (npu_s3_axi_rready ),
1105:     .kf_rid     (npu_s3_axi_rid    ),
1106:     .kf_rdata   (npu_s3_axi_rdata  ),
1107:     .kf_rresp   (npu_s3_axi_rresp  ),
1108:     .kf_rlast   (npu_s3_axi_rlast  ),
1109:     .kf_rvalid  (npu_s3_axi_rvalid )
1110: 
1111: );
1112: 
1113: // [LEDGER 2026-09-19] DMA transaction-done pulses (single beat ledger)
1114: wire cam_dma_done;
1115: // [SFP-STATUS 2026-09-30] SFP link status -> prep_regs +0x144 (btn_level_sync slot)
1116: wire sfp_st_pll_lock, sfp_st_txlane_done, sfp_st_rxlane_done, sfp_st_pcs_synced;
1117: wire sfp_st_sigdet;
1118: wire [31:0] cam5_diag_fault, cam6_diag_fault;
1119: wire [31:0] cam5_diag_pixels, cam6_diag_pixels;
1120: wire [31:0] cam5_diag_state, cam6_diag_state;
1121: wire [31:0] cam5_diag_rejects, cam6_diag_rejects;
1122: reg [1:0] sfp_sigdet_sync = 0;
1123: reg [1:0] sfp_enable_sync = 0;
1124: wire [31:0] sfp_diag_status = {26'd0, sfp_enable_sync[1], sfp_sigdet_sync[1], sfp_status_bits};
1125: always @(posedge axi_clk) begin
1126:     sfp_sigdet_sync <= {sfp_sigdet_sync[0], sfp_st_sigdet};
1127:     sfp_enable_sync <= {sfp_enable_sync[0], sfp_rx_en};
1128: end
1129: reg [3:0] sfp_status_bits = 4'b0;
1130: reg [1:0] st_pll1_q, st_txd2_q, st_rxd2_q, st_pcs_q;
1131: always @(posedge axi_clk) begin
1132:     st_pll1_q <= {st_pll1_q[0], sfp_st_pll_lock};
1133:     st_txd2_q <= {st_txd2_q[0], sfp_st_txlane_done};
1134:     st_rxd2_q <= {st_rxd2_q[0], sfp_st_rxlane_done};
1135:     st_pcs_q  <= {st_pcs_q[0],  sfp_st_pcs_synced};
1136:     sfp_status_bits <= {st_pcs_q[1], st_rxd2_q[1], st_txd2_q[1], st_pll1_q[1]};
1137: end
1138: wire cam2_dma_done;
1139: wire cam3_dma_done;
1140: wire cam4_dma_done;
1141: 
1142: // ---- [SFP 2026-09-29] fiber RX link / cam5 / cam6 signals ----
1143: wire        sfp_rx_clk, sfp_rx_rst_n, sfp_rx_en;
1144: wire t4_awready, t4_wready; wire [3:0] t4_bid; wire [1:0] t4_bresp; wire t4_bvalid;
1145: wire t5_awready, t5_wready; wire [3:0] t5_bid; wire [1:0] t5_bresp; wire t5_bvalid;
1146: wire [31:0] sfp_rxd;
1147: wire [3:0]  sfp_rxk;
1148: wire        sfp_vs, sfp_hs, sfp_de;
1149: wire [15:0] sfp_pix;
1150: wire        cam5_vs, cam5_hs, cam5_de;
1151: wire [15:0] cam5_pix;
1152: wire        cam6_vs, cam6_hs, cam6_de;
1153: wire [15:0] cam6_pix;
1154: wire [31:0] cam5_cmd_addr, cam5_cmd_len;
1155: wire        cam5_cmd_valid, cam5_cmd_ready;
1156: wire [AXI_DATA_LEN-1:0] cam5_s_data;
1157: wire        cam5_s_data_valid, cam5_s_data_last, cam5_s_data_ready;
1158: wire [15:0] cam5_s_data_available;
1159: wire [AXI_ID_LEN-1:0]   cam5_axi_awid;
1160: wire [31:0]             cam5_axi_awaddr;
1161: wire [3:0]              cam5_axi_awlen;
1162: wire [2:0]              cam5_axi_awsize;
1163: wire [1:0]              cam5_axi_awburst;
1164: wire                    cam5_axi_awlock;
1165: wire [3:0]              cam5_axi_awcache;
1166: wire [2:0]              cam5_axi_awprot;
1167: wire                    cam5_axi_awvalid, cam5_axi_awready;
1168: wire [AXI_DATA_LEN-1:0] cam5_axi_wdata;
1169: wire [AXI_STRB_LEN-1:0] cam5_axi_wstrb;
1170: wire                    cam5_axi_wlast, cam5_axi_wvalid, cam5_axi_wready;
1171: wire [AXI_ID_LEN-1:0]   cam5_axi_bid;
1172: wire [1:0]              cam5_axi_bresp;
1173: wire                    cam5_axi_bvalid, cam5_axi_bready;
1174: wire [31:0] cam6_cmd_addr, cam6_cmd_len;
1175: wire        cam6_cmd_valid, cam6_cmd_ready;
1176: wire [AXI_DATA_LEN-1:0] cam6_s_data;
1177: wire        cam6_s_data_valid, cam6_s_data_last, cam6_s_data_ready;
1178: wire [15:0] cam6_s_data_available;
1179: wire [AXI_ID_LEN-1:0]   cam6_axi_awid;
1180: wire [31:0]             cam6_axi_awaddr;
1181: wire [3:0]              cam6_axi_awlen;
1182: wire [2:0]              cam6_axi_awsize;
1183: wire [1:0]              cam6_axi_awburst;
1184: wire                    cam6_axi_awlock;
1185: wire [3:0]              cam6_axi_awcache;
1186: wire [2:0]              cam6_axi_awprot;
1187: wire                    cam6_axi_awvalid, cam6_axi_awready;
1188: wire [AXI_DATA_LEN-1:0] cam6_axi_wdata;
1189: wire [AXI_STRB_LEN-1:0] cam6_axi_wstrb;
1190: wire                    cam6_axi_wlast, cam6_axi_wvalid, cam6_axi_wready;
1191: wire [AXI_ID_LEN-1:0]   cam6_axi_bid;
1192: wire [1:0]              cam6_axi_bresp;
1193: wire                    cam6_axi_bvalid, cam6_axi_bready;
1194: 
1195: // --- CAM3 (FMC 3rd OV5640, BASE_ADDR 0x2000_0400, 640x480, raw passthrough) ---
1196: wire                        cam3_axil_awvalid_unused;
1197: wire [AXI_DATA_LEN-1 : 0]   cam3_s_data      ;
1198: wire                        cam3_s_data_valid;
1199: wire                        cam3_s_data_last ;
1200: wire                        cam3_s_data_ready;
1201: wire [31:0]                 cam3_cmd_addr    ;
1202: wire [31:0]                 cam3_cmd_len     ;
1203: wire                        cam3_cmd_valid   ;
1204: wire                        cam3_cmd_ready   ;
1205: wire [3:0]                  cam3_axi_awid    ;
1206: wire [31:0]                 cam3_axi_awaddr  ;
1207: wire [7:0]                  cam3_axi_awlen   ;
1208: wire [2:0]                  cam3_axi_awsize  ;
1209: wire [1:0]                  cam3_axi_awburst ;
1210: wire [3:0]                  cam3_axi_awcache ;
1211: wire [2:0]                  cam3_axi_awprot  ;
1212: wire                        cam3_axi_awvalid ;
1213: wire                        cam3_axi_awready ;
1214: wire [127:0]                cam3_axi_wdata   ;
1215: wire [15:0]                 cam3_axi_wstrb   ;
1216: wire                        cam3_axi_awlock  ;
1217: wire                        cam3_axi_wlast   ;
1218: wire                        cam3_axi_wvalid  ;
1219: wire                        cam3_axi_wready  ;
1220: wire [3:0]                  cam3_axi_bid     ;
1221: wire [1:0]                  cam3_axi_bresp   ;
1222: wire                        cam3_axi_bvalid  ;
1223: wire                        cam3_axi_bready  ;
1224: wire [31:0]                 cam3_dbg_dummy;
1225: 
1226: // ---- CAM2 (FMC 2nd OV5640, BASE_ADDR 0x2000_0200, 640x480) ----
1227: ov5640_top #(
1228:     .BASE_ADDR       (32'h2000_0200),
1229:     .CAM_ADDR_1_DEF  (32'h00C0_0000),
1230:     .CAM_ADDR_2_DEF  (32'h00E0_0000),
1231:     .CAM_EN_DEF      (1'b1),   // [DUALCAM] keep both camera engines enabled
1232:     .H_CMOS_DISP     (11'd640),
1233:     .V_CMOS_DISP     (11'd480),
1234:     .TOTAL_H_PIXEL   (12'd1896),
1235:     .TOTAL_V_PIXEL   (12'd984)
1236: ) cam2_ov5640_top (
1237:     .motion_record(cam2_motion_record),
1238:     .clk_50m       (clk_50m),
1239:     .clk_50m_rst_n (camera_ctrl_rst_n),
1240:     .dbg_locked    (locked),
1241:     .dbg_btn_rst_n (button_rst_n),
1242:     .dbg_axi_awvalid(cam2_axi_awvalid),
1243:     .dbg_axi_awready(cam2_axi_awready),
1244:     .dbg_axi_wvalid (cam2_axi_wvalid ),
1245:     .dbg_axi_wready (cam2_axi_wready ),
1246:     .dbg_axi_bvalid (cam2_axi_bvalid ),
1247:     .dbg_axi_bready (cam2_axi_bready ),
1248: 
1249:     .cam_pclk (cmos2_pclk ),
1250:     .cam_vsync(cmos2_vsync),
1251:     .cam_href (cmos2_href ),
1252:     .cam_data (cmos2_data ),
1253:     .cam_rst_n(cmos2_rst_n),
1254:     .cam_scl  (cmos2_scl  ),
1255:     .cam_sda  (cmos2_sda  ),
1256: 
1257:     .s_axi_awvalid(cam2_axil_awvalid),
1258:     .s_axi_awready(cam2_axil_awready),
1259:     .s_axi_awaddr (cam2_axil_awaddr ),
1260:     .s_axi_wvalid (cam2_axil_wvalid ),
1261:     .s_axi_wready (cam2_axil_wready ),
1262:     .s_axi_wdata  (cam2_axil_wdata  ),
1263:     .s_axi_wstrb  (cam2_axil_wstrb  ),
1264:     .s_axi_bvalid (cam2_axil_bvalid ),
1265:     .s_axi_bready (cam2_axil_bready ),
1266:     .s_axi_bresp  (cam2_axil_bresp  ),
1267:     .s_axi_arvalid(cam2_axil_arvalid),
1268:     .s_axi_arready(cam2_axil_arready),
1269:     .s_axi_araddr (cam2_axil_araddr ),
1270:     .s_axi_rvalid (cam2_axil_rvalid ),
1271:     .s_axi_rready (cam2_axil_rready ),
1272:     .s_axi_rdata  (cam2_axil_rdata  ),
1273:     .s_axi_rresp  (cam2_axil_rresp  ),
1274: 
1275:     .video_clk(axi_clk),
1276:     .video_rst(axi_rst),
1277:     .cam_cmd_addr (cam2_cmd_addr ),
1278:     .cam_cmd_len  (cam2_cmd_len  ),
1279:     .cam_cmd_valid(cam2_cmd_valid),
1280:     .cam_cmd_ready(cam2_cmd_ready),
1281: 
1282:     .cam_s_data      (cam2_s_data      ),
1283:     .cam_s_data_valid(cam2_s_data_valid),
1284:     .cam_s_data_last (cam2_s_data_last ),
1285:     .cam_s_data_ready(cam2_s_data_ready),
1286: 
1287:     .cam_dma_abort(cam2_dma_abort),
1288:     .cam_s_data_available(cam2_s_data_available),
1289:     .cam_dma_abort_req(cam2_dma_abort_req),
1290:     .cam_dma_done(cam2_dma_done),
1291:     .xdma_clk (pcie_clk),
1292:     .xdma_irq (          )
1293: );
1294: 
1295: // ---- CAM3 (FMC 3rd OV5640, BASE_ADDR 0x2000_0400, 640x480, raw passthrough:
1296: //      VSYNC qualified for 64 PCLK; pixel-path settings unchanged) ----
1297: ov5640_top #(
1298:     .BASE_ADDR       (32'h2000_0400),
1299:     .SENSOR_PLL_MULT (8'h30), // cam3: initialize PLL for 48 MHz PCLK
1300:     .VSYNC_STABLE_CYCLES(64), // cam3 only: 0.762 us at 84 MHz
1301:     .CAM_ADDR_1_DEF  (32'h0100_0000),
1302:     .CAM_ADDR_2_DEF  (32'h0120_0000),
1303:     .CAM_EN_DEF      (1'b1),
1304:     .H_CMOS_DISP     (11'd640),
1305:     .V_CMOS_DISP     (11'd480),
1306:     .TOTAL_H_PIXEL   (12'd1896),
1307:     .TOTAL_V_PIXEL   (12'd984)
1308: ) cam3_ov5640_top (
1309:     .motion_record(cam3_motion_record),
1310:     .clk_50m       (clk_50m),
1311:     .clk_50m_rst_n (camera_ctrl_rst_n),
1312:     .dbg_locked    (locked),
1313:     .dbg_btn_rst_n (button_rst_n),
1314:     .dbg_axi_awvalid(cam3_axi_awvalid),
1315:     .dbg_axi_awready(cam3_axi_awready),
1316:     .dbg_axi_wvalid (cam3_axi_wvalid ),
1317:     .dbg_axi_wready (cam3_axi_wready ),
1318:     .dbg_axi_bvalid (cam3_axi_bvalid ),
1319:     .dbg_axi_bready (cam3_axi_bready ),
1320: 
1321:     .cam_pclk (cmos3_pclk ),
1322:     .cam_vsync(cmos3_vsync),
1323:     .cam_href (cmos3_href ),
1324:     .cam_data (cmos3_data ),
1325:     .cam_rst_n(cmos3_rst_n),
1326:     .cam_scl  (cmos3_scl  ),
1327:     .cam_sda  (cmos3_sda  ),
1328: 
1329:     .s_axi_awvalid(cam3_axil_awvalid),
1330:     .s_axi_awready(cam3_axil_awready),
1331:     .s_axi_awaddr (cam3_axil_awaddr ),
1332:     .s_axi_wvalid (cam3_axil_wvalid ),
1333:     .s_axi_wready (cam3_axil_wready ),
1334:     .s_axi_wdata  (cam3_axil_wdata  ),
1335:     .s_axi_wstrb  (cam3_axil_wstrb  ),
1336:     .s_axi_bvalid (cam3_axil_bvalid ),
1337:     .s_axi_bready (cam3_axil_bready ),
1338:     .s_axi_bresp  (cam3_axil_bresp  ),
1339:     .s_axi_arvalid(cam3_axil_arvalid),
1340:     .s_axi_arready(cam3_axil_arready),
1341:     .s_axi_araddr (cam3_axil_araddr ),
1342:     .s_axi_rvalid (cam3_axil_rvalid ),
1343:     .s_axi_rready (cam3_axil_rready ),
1344:     .s_axi_rdata  (cam3_axil_rdata  ),
1345:     .s_axi_rresp  (cam3_axil_rresp  ),
1346: 
1347:     .video_clk(axi_clk),
1348:     .video_rst(axi_rst),
1349:     .cam_cmd_addr (cam3_cmd_addr ),
1350:     .cam_cmd_len  (cam3_cmd_len  ),
1351:     .cam_cmd_valid(cam3_cmd_valid),
1352:     .cam_cmd_ready(cam3_cmd_ready),
1353: 
1354:     .cam_s_data      (cam3_s_data      ),
1355:     .cam_s_data_valid(cam3_s_data_valid),
1356:     .cam_s_data_last (cam3_s_data_last ),
1357:     .cam_s_data_ready(cam3_s_data_ready),
1358: 
1359:     .cam_dma_abort(cam3_dma_abort),
1360:     .cam_s_data_available(cam3_s_data_available),
1361:     .cam_dma_abort_req(cam3_dma_abort_req),
1362:     .cam_dma_done(cam3_dma_done),
1363:     .xdma_clk (pcie_clk),
1364:     .xdma_irq (          )
1365: );
1366: 
1367: // --- CAM4 (FMC 4th OV5640, BASE_ADDR 0x2000_0600, 640x480, raw passthrough:
1368: //      same 48 MHz init PLL and VSYNC qualification as CAM3) ---
1369: wire [AXI_DATA_LEN-1 : 0]   cam4_s_data      ;
1370: wire                        cam4_s_data_valid;
1371: wire                        cam4_s_data_last ;
1372: wire                        cam4_s_data_ready;
1373: wire [31:0]                 cam4_cmd_addr    ;
1374: wire [31:0]                 cam4_cmd_len     ;
1375: wire                        cam4_cmd_valid   ;
1376: wire                        cam4_cmd_ready   ;
1377: wire [3:0]                  cam4_axi_awid    ;
1378: wire [31:0]                 cam4_axi_awaddr  ;
1379: wire [7:0]                  cam4_axi_awlen   ;
1380: wire [2:0]                  cam4_axi_awsize  ;
1381: wire [1:0]                  cam4_axi_awburst ;
1382: wire [3:0]                  cam4_axi_awcache ;
1383: wire [2:0]                  cam4_axi_awprot  ;
1384: wire                        cam4_axi_awvalid ;
1385: wire                        cam4_axi_awready ;
1386: wire [127:0]                cam4_axi_wdata   ;
1387: wire [15:0]                 cam4_axi_wstrb   ;
1388: wire                        cam4_axi_awlock  ;
1389: wire                        cam4_axi_wlast   ;
1390: wire                        cam4_axi_wvalid  ;
1391: wire                        cam4_axi_wready  ;
1392: wire [3:0]                  cam4_axi_bid     ;
1393: wire [1:0]                  cam4_axi_bresp   ;
1394: wire                        cam4_axi_bvalid  ;
1395: wire                        cam4_axi_bready  ;
1396: wire [31:0]                 cam4_dbg_dummy;
1397: 
1398: ov5640_top #(
1399:     .BASE_ADDR       (32'h2000_0600),
1400:     .SENSOR_PLL_MULT (8'h30), // cam4: same 48 MHz PCLK init as cam3
1401:     .VSYNC_STABLE_CYCLES(64), // cam4 only: 0.762 us at 84 MHz
1402:     .CAM_ADDR_1_DEF  (32'h0140_0000),
1403:     .CAM_ADDR_2_DEF  (32'h0160_0000),
1404:     .CAM_EN_DEF      (1'b1),
1405:     .H_CMOS_DISP     (11'd640),
1406:     .V_CMOS_DISP     (11'd480),
1407:     .TOTAL_H_PIXEL   (12'd1896),
1408:     .TOTAL_V_PIXEL   (12'd984)
1409: ) cam4_ov5640_top (
1410:     .motion_record(cam4_motion_record),
1411:     .clk_50m       (clk_50m),
1412:     .clk_50m_rst_n (camera_ctrl_rst_n),
1413:     .dbg_locked    (locked),
1414:     .dbg_btn_rst_n (button_rst_n),
1415:     .dbg_axi_awvalid(cam4_axi_awvalid),
1416:     .dbg_axi_awready(cam4_axi_awready),
1417:     .dbg_axi_wvalid (cam4_axi_wvalid ),
1418:     .dbg_axi_wready (cam4_axi_wready ),
1419:     .dbg_axi_bvalid (cam4_axi_bvalid ),
1420:     .dbg_axi_bready (cam4_axi_bready ),
1421: 
1422:     .cam_pclk (cmos4_pclk ),
1423:     .cam_vsync(cmos4_vsync),
1424:     .cam_href (cmos4_href ),
1425:     .cam_data (cmos4_data ),
1426:     .cam_rst_n(cmos4_rst_n),
1427:     .cam_scl  (cmos4_scl  ),
1428:     .cam_sda  (cmos4_sda  ),
1429: 
1430:     .s_axi_awvalid(cam4_axil_awvalid),
1431:     .s_axi_awready(cam4_axil_awready),
1432:     .s_axi_awaddr (cam4_axil_awaddr ),
1433:     .s_axi_wvalid (cam4_axil_wvalid ),
1434:     .s_axi_wready (cam4_axil_wready ),
1435:     .s_axi_wdata  (cam4_axil_wdata  ),
1436:     .s_axi_wstrb  (cam4_axil_wstrb  ),
1437:     .s_axi_bvalid (cam4_axil_bvalid ),
1438:     .s_axi_bready (cam4_axil_bready ),
1439:     .s_axi_bresp  (cam4_axil_bresp  ),
1440:     .s_axi_arvalid(cam4_axil_arvalid),
1441:     .s_axi_arready(cam4_axil_arready),
1442:     .s_axi_araddr (cam4_axil_araddr ),
1443:     .s_axi_rvalid (cam4_axil_rvalid ),
1444:     .s_axi_rready (cam4_axil_rready ),
1445:     .s_axi_rdata  (cam4_axil_rdata  ),
1446:     .s_axi_rresp  (cam4_axil_rresp  ),
1447: 
1448:     .video_clk(axi_clk),
1449:     .video_rst(axi_rst),
1450:     .cam_cmd_addr (cam4_cmd_addr ),
1451:     .cam_cmd_len  (cam4_cmd_len  ),
1452:     .cam_cmd_valid(cam4_cmd_valid),
1453:     .cam_cmd_ready(cam4_cmd_ready),
1454: 
1455:     .cam_s_data      (cam4_s_data      ),
1456:     .cam_s_data_valid(cam4_s_data_valid),
1457:     .cam_s_data_last (cam4_s_data_last ),
1458:     .cam_s_data_ready(cam4_s_data_ready),
1459: 
1460:     .cam_dma_abort(cam4_dma_abort),
1461:     .cam_s_data_available(cam4_s_data_available),
1462:     .cam_dma_abort_req(cam4_dma_abort_req),
1463:     .cam_dma_done(cam4_dma_done),
1464:     .xdma_clk (pcie_clk),
1465:     .xdma_irq (          )
1466: );
1467: 
1468: // =====================================================================
1469: // [SFP 2026-09-29] fiber RX path:
1470: //   SFP(QR3 HSST CH2) -> sfp_rx_link -> sfp_video_rx (1280 wide unpack)
1471: //   -> sfp_rx_cam_if (split 640+640 + CDC to axi_clk)
1472: //   -> cam5/cam6 ov5640_ddr write engines -> axi_dma_write -> ddr_w_arb m4/m5
1473: //   DDR ping-pong: cam5 0x0180_0000/0x01A0_0000, cam6 0x01C0_0000/0x01E0_0000
1474: // =====================================================================
1475: sfp_rx_link u_sfp_rx_link (
1476:     .i_free_clk       (free_clk),
1477:     .i_refckp         (ref_clk_p),      // F6, shared with PCIe
1478:     .i_refckn         (ref_clk_n),      // E6
1479:     .i_l2rxn          (sfp_l2rxn),      // D11
1480:     .i_l2rxp          (sfp_l2rxp),      // C11
1481:     .o_l2txn          (sfp_l2txn),      // D5
1482:     .o_l2txp          (sfp_l2txp),      // C5
1483:     .o_sfp_tx_disable (sfp_tx_disable), // L16
1484:     .o_rx_clk         (sfp_rx_clk),
1485:     .o_rx_rst_n       (sfp_rx_rst_n),
1486:     .o_rxd            (sfp_rxd),
1487:     .o_rxk            (sfp_rxk),
1488:     .o_rx_en          (sfp_rx_en),
1489:     .o_pll_lock       (sfp_st_pll_lock),
1490:     .o_txlane_done    (sfp_st_txlane_done),
1491:     .o_rxlane_done    (sfp_st_rxlane_done),
1492:     .o_pcs_synced     (sfp_st_pcs_synced),
1493:     .o_rx_sigdet      (sfp_st_sigdet)
1494: );
1495: 
1496: sfp_video_rx u_sfp_video_rx (
1497:     .i_clk      (sfp_rx_clk),
1498:     .i_rst_n    (sfp_rx_rst_n),
1499:     .i_en       (sfp_rx_en),
1500:     .i_rxd      (sfp_rxd),
1501:     .i_rxk      (sfp_rxk),
1502:     .o_vs       (sfp_vs),
1503:     .o_hs       (sfp_hs),
1504:     .o_de       (sfp_de),
1505:     .o_pix      (sfp_pix),
1506:     .o_overflow ()
1507: );
1508: 
1509: sfp_rx_cam_if #(
1510:     .IMG_W   (1280),
1511:     .SPLIT_W (640),
1512:     .FIFO_D  (1024)
1513: ) u_sfp_rx_cam_if (
1514:     .i_rx_clk   (sfp_rx_clk),
1515:     .i_rx_rst_n (sfp_rx_rst_n),
1516:     .i_vs       (sfp_vs),
1517:     .i_hs       (sfp_hs),
1518:     .i_de       (sfp_de),
1519:     .i_pix      (sfp_pix),
1520:     .i_axi_clk  (axi_clk),
1521:     .i_axi_rst_n(~axi_rst),
1522:     .o_vs5  (cam5_vs),  .o_hs5 (cam5_hs),  .o_de5 (cam5_de),  .o_pix5 (cam5_pix),
1523:     .o_vs6  (cam6_vs),  .o_hs6 (cam6_hs),  .o_de6 (cam6_de),  .o_pix6 (cam6_pix)
1524: );
1525: 
1526: // [2026-09-30] BISECT3 uncommented: cam5/6 \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd7\xa2\xef\xbf\xbd\xef\xbf\xbd
1527: // SFP CAM5/6 retain video capture and DDR writes; motion uses local CAM1-4.
1528: 
1529: // ---- cam5 write engine (fiber left half = 50K CMOS1) ----
1530: wire cam5_dma_done, cam5_dma_abort, cam5_dma_abort_req;
1531: wire cam6_dma_done, cam6_dma_abort, cam6_dma_abort_req;
1532: fpga_v8_capture_ov5640_ddr #(
1533:     .DATA_WIDTH(16),
1534:     .AXI_DATA_WIDTH(128),
1535:     .CAM_DATA_LEN(38400),
1536:     .BANK0_ADDR(32'h01800000),
1537:     .BANK1_ADDR(32'h01a00000),
1538:     .DEVICE("PG")
1539: ) cam5_ov5640_ddr (
1540:     .axi_clk(axi_clk),
1541:     .axi_rst(axi_rst),
1542:     .epoch_start(v8_cap_epoch_start),
1543:     .lease_block(v8_cap_lease_block),
1544:     .dma_abort(cam5_dma_abort),
1545:     .dma_abort_req(cam5_dma_abort_req),
1546:     .dma_done(cam5_dma_done),
1547:     .axi_data_available(cam5_s_data_available),
1548:     .axi_cam_en(1'b1),
1549:     .s_data(cam5_pix),
1550:     .s_data_valid(cam5_de),
1551:     .s_hsync(cam5_hs),
1552:     .s_vsync(cam5_vs),
1553:     .axi_data(cam5_s_data),
1554:     .axi_data_valid(cam5_s_data_valid),
1555:     .axi_data_last(cam5_s_data_last),
1556:     .axi_data_ready(cam5_s_data_ready),
1557:     .axi_cmd_addr(cam5_cmd_addr),
1558:     .axi_cmd_len(cam5_cmd_len),
1559:     .axi_cmd_valid(cam5_cmd_valid),
1560:     .axi_cmd_ready(cam5_cmd_ready),
1561:     .xdma_req(),
1562:     .xdma_ack(2'b00),
1563:     .admitted_sof(v8_cap_admitted_sof),
1564:     .capture_bank(v8_cap_capture_bank),
1565:     .publish(v8_cap_publish),
1566:     .publish_seq(v8_cap_publish_seq),
1567:     .retired_error(v8_cap_retired_error),
1568:     .engine_idle(v8_cap_engine_idle),
1569:     .capture_flush_o(v8_cap_capture_flush_o),
1570:     .frame_good_o(v8_cap_frame_good_o),
1571:     .capture_overflow_o(v8_cap_capture_overflow_o),
1572:     .dbg_fault_snapshot(cam5_diag_fault),
1573:     .dbg_reject_counts(cam5_diag_rejects),
1574:     .dbg_input_pixels(cam5_diag_pixels),
1575:     .dbg_axi_cnt(),
1576:     .dbg_axi_num(),
1577:     .dbg_zdin(),
1578:     .dbg_zout(),
1579:     .dbg_state(cam5_diag_state),
1580:     .dbg_last_cnt(),
1581:     .dbg_wd_cnt()
1582: );
1583: 
1584: 
1585: axi_dma_write #(
1586:     .WAIT_FOR_DATA(1),
1587:     .BURST_LEN  (BURST_LEN)   ,
1588:     .ID_WIDTH   (AXI_ID_LEN)  ,
1589:     .DATA_WIDTH (AXI_DATA_LEN)
1590: ) cam5_axi_dma_write (
1591:     .data_in_available(cam5_s_data_available),
1592:     .abort_req(cam5_dma_abort_req),
1593:     .data_in_abort(cam5_dma_abort),
1594:     .clk(axi_clk),
1595:     .rst(axi_rst),
1596:     .cmd_valid (cam5_cmd_valid),
1597:     .cmd_addr  (cam5_cmd_addr ),
1598:     .cmd_len   (cam5_cmd_len  ),
1599:     .cmd_id    (4'b0011),
1600:     .cmd_ready (cam5_cmd_ready),
1601:     .data_in       (cam5_s_data),
1602:     .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1603:     .data_in_valid (cam5_s_data_valid),
1604:     .data_in_last  (cam5_dma_done),
1605:     .data_in_ready (cam5_s_data_ready),
1606:     .m_axi_awid    (cam5_axi_awid),
1607:     .m_axi_awaddr  (cam5_axi_awaddr),
1608:     .m_axi_awlen   (cam5_axi_awlen),
1609:     .m_axi_awsize  (cam5_axi_awsize),
1610:     .m_axi_awburst (cam5_axi_awburst),
1611:     .m_axi_awlock  (cam5_axi_awlock),
1612:     .m_axi_awcache (cam5_axi_awcache),
1613:     .m_axi_awprot  (cam5_axi_awprot),
1614:     .m_axi_awvalid (cam5_axi_awvalid),
1615:     .m_axi_awready (cam5_axi_awready),
1616:     .m_axi_wdata   (cam5_axi_wdata),
1617:     .m_axi_wstrb   (cam5_axi_wstrb),
1618:     .m_axi_wlast   (cam5_axi_wlast),
1619:     .m_axi_wvalid  (cam5_axi_wvalid),
1620:     .m_axi_wready  (cam5_axi_wready),
1621:     .m_axi_bid     (cam5_axi_bid),
1622:     .m_axi_bresp   (cam5_axi_bresp),
1623:     .m_axi_bvalid  (cam5_axi_bvalid),
1624:     .m_axi_bready  (cam5_axi_bready)
1625: );
1626: 
1627: // ---- cam6 write engine (fiber right half = 50K CMOS2) ----
1628: ov5640_ddr #(
1629:     .DATA_WIDTH     (16),
1630:     .AXI_ADDR_WIDTH (32),
1631:     .AXI_LEN_WIDTH  (32),
1632:     .AXI_DATA_WIDTH (128),
1633:     .CAM_DATA_LEN   (38400),
1634:     .DEVICE         ("PG")
1635: ) cam6_ov5640_ddr (
1636:     .axi_clk        (axi_clk),
1637:     .axi_rst        (axi_rst),
1638:     .axi_cam_en     (1'b1),   // [2026-09-30] enable cam5/6 DDR write (SFP fiber channels)
1639:     .dbg_fault_snapshot (cam6_diag_fault), .dbg_reject_counts (cam6_diag_rejects), .dbg_input_pixels (cam6_diag_pixels),
1640:     .dma_abort      (cam6_dma_abort),
1641:     .dma_abort_req  (cam6_dma_abort_req),
1642:     .axi_data_available (cam6_s_data_available),
1643:     .dma_done       (cam6_dma_done),
1644:     .cam_data_addr_1(32'h01C0_0000),
1645:     .cam_data_addr_2(32'h01E0_0000),
1646:     .prev_frame_base(),               // [KF-unused]
1647:     .cam_data_len   (38400),
1648:     .s_data         (cam6_pix),
1649:     .s_data_valid   (cam6_de),
1650:     .s_hsync        (cam6_hs),
1651:     .s_vsync        (cam6_vs),
1652:     .axi_data       (cam6_s_data),
1653:     .axi_data_valid (cam6_s_data_valid),
1654:     .axi_data_last  (cam6_s_data_last),
1655:     .axi_data_ready (cam6_s_data_ready),
1656:     .axi_cmd_addr   (cam6_cmd_addr),
1657:     .axi_cmd_len    (cam6_cmd_len),
1658:     .axi_cmd_valid  (cam6_cmd_valid),
1659:     .axi_cmd_ready  (cam6_cmd_ready),
1660:     .dbg_axi_cnt (), .dbg_axi_num (), .dbg_zdin (), .dbg_zout (),
1661:     .dbg_state (cam6_diag_state), .dbg_last_cnt (), .dbg_wd_cnt (),
1662:     .xdma_req  (),
1663:     .xdma_ack  (2'b00)
1664: );
1665: 
1666: axi_dma_write #(
1667:     .WAIT_FOR_DATA(1),
1668:     .BURST_LEN  (BURST_LEN)   ,
1669:     .ID_WIDTH   (AXI_ID_LEN)  ,
1670:     .DATA_WIDTH (AXI_DATA_LEN)
1671: ) cam6_axi_dma_write (
1672:     .data_in_available(cam6_s_data_available),
1673:     .abort_req(cam6_dma_abort_req),
1674:     .data_in_abort(cam6_dma_abort),
1675:     .clk(axi_clk),
1676:     .rst(axi_rst),
1677:     .cmd_valid (cam6_cmd_valid),
1678:     .cmd_addr  (cam6_cmd_addr ),
1679:     .cmd_len   (cam6_cmd_len  ),
1680:     .cmd_id    (4'b1100),
1681:     .cmd_ready (cam6_cmd_ready),
1682:     .data_in       (cam6_s_data),
1683:     .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1684:     .data_in_valid (cam6_s_data_valid),
1685:     .data_in_last  (cam6_dma_done),
1686:     .data_in_ready (cam6_s_data_ready),
1687:     .m_axi_awid    (cam6_axi_awid),
1688:     .m_axi_awaddr  (cam6_axi_awaddr),
1689:     .m_axi_awlen   (cam6_axi_awlen),
1690:     .m_axi_awsize  (cam6_axi_awsize),
1691:     .m_axi_awburst (cam6_axi_awburst),
1692:     .m_axi_awlock  (cam6_axi_awlock),
1693:     .m_axi_awcache (cam6_axi_awcache),
1694:     .m_axi_awprot  (cam6_axi_awprot),
1695:     .m_axi_awvalid (cam6_axi_awvalid),
1696:     .m_axi_awready (cam6_axi_awready),
1697:     .m_axi_wdata   (cam6_axi_wdata),
1698:     .m_axi_wstrb   (cam6_axi_wstrb),
1699:     .m_axi_wlast   (cam6_axi_wlast),
1700:     .m_axi_wvalid  (cam6_axi_wvalid),
1701:     .m_axi_wready  (cam6_axi_wready),
1702:     .m_axi_bid     (cam6_axi_bid),
1703:     .m_axi_bresp   (cam6_axi_bresp),
1704:     .m_axi_bvalid  (cam6_axi_bvalid),
1705:     .m_axi_bready  (cam6_axi_bready)
1706: );
1707: 
1708: 
1709: // */
1710: `elsif USE_HDMI
1711: 
1712: hdmi_top hdmi_top(
1713:     .clk_10m(clk_10m)               ,
1714:     .clk_10m_rst_n(locked & button_rst_n)         ,
1715: 
1716:     //HDMI\xef\xbf\xbd\xd3\xbf\xef\xbf\xbd
1717: 
1718:     //ms72XX
1719:     .rstn_out(rstn_out),
1720: 
1721:     // FMC I2C 
1722:     .iic_scl(iic_scl),
1723:     .iic_sda(iic_sda), 
1724: 
1725:     // .iic_tx_scl(iic_tx_scl),
1726:     // .iic_tx_sda(iic_tx_sda), 
1727: 
1728:     //HDMI IN
1729:     .pixclk_in(pixclk_in),                            
1730:     .vs_in(vs_in) , 
1731:     .hs_in(hs_in) , 
1732:     .de_in(de_in) ,
1733:     .r_in (r_in ) , 
1734:     .g_in (g_in ) , 
1735:     .b_in (b_in ) ,  
1736: 
1737: 
1738: 
1739: 
1740:     //\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xcd\xb7\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc6\xbc\xc4\xb4\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd
1741:     .s_axi_awvalid(cam_axil_awvalid)        ,
1742:     .s_axi_awready(cam_axil_awready)        ,
1743:     .s_axi_awaddr (cam_axil_awaddr )        ,
1744: 
1745:     .s_axi_wvalid (cam_axil_wvalid)         ,
1746:     .s_axi_wready (cam_axil_wready)         ,
1747:     .s_axi_wdata  (cam_axil_wdata )         ,
1748:     .s_axi_wstrb  (cam_axil_wstrb )         ,
1749: 
1750:     .s_axi_bvalid (cam_axil_bvalid)         ,
1751:     .s_axi_bready (cam_axil_bready)         ,
1752:     .s_axi_bresp  (cam_axil_bresp )         ,
1753: 
1754:     .s_axi_arvalid(cam_axil_arvalid)        ,
1755:     .s_axi_arready(cam_axil_arready)        ,
1756:     .s_axi_araddr (cam_axil_araddr )        ,
1757: 
1758:     .s_axi_rvalid (cam_axil_rvalid )        ,
1759:     .s_axi_rready (cam_axil_rready )        ,
1760:     .s_axi_rdata  (cam_axil_rdata  )        ,
1761:     .s_axi_rresp  (cam_axil_rresp  )        ,
1762: 
1763: 
1764: 
1765:     //AXI_stream
1766:     .video_clk(axi_clk)      ,
1767:     .video_rst(axi_rst)      ,
1768:     .cam_cmd_addr (cam_cmd_addr )  ,
1769:     .cam_cmd_len  (cam_cmd_len  )  ,
1770:     .cam_cmd_valid(cam_cmd_valid)  ,
1771:     .cam_cmd_ready(cam_cmd_ready)  ,
1772: 
1773:     .cam_s_data      (cam_tap_data      ),
1774:     .cam_s_data_valid(cam_tap_data_valid),
1775:     .cam_s_data_last (cam_tap_data_last ),
1776:     .cam_s_data_ready(cam_tap_data_ready),
1777: 
1778:     //DMA?
1779:     .xdma_clk (pcie_clk) ,
1780:     .xdma_irq (cam_irq ) 
1781: 
1782: );
1783: `endif
1784: 
1785: wire [AXI_ID_LEN-1:0]   ov5640_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
1786: wire [31:0]             ov5640_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
1787: wire [3:0]              ov5640_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
1788: wire [2:0]              ov5640_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
1789: wire [1:0]              ov5640_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
1790: wire                    ov5640_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
1791: wire [3:0]              ov5640_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
1792: wire [2:0]              ov5640_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
1793: wire                    ov5640_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
1794: wire                    ov5640_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
1795: wire [AXI_DATA_LEN-1:0] ov5640_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
1796: wire [AXI_STRB_LEN-1:0] ov5640_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
1797: wire                    ov5640_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
1798: wire                    ov5640_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
1799: wire                    ov5640_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
1800: wire [AXI_ID_LEN-1:0]   ov5640_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
1801: wire [1:0]              ov5640_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
1802: wire                    ov5640_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
1803: wire                    ov5640_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;
1804: 
1805: axi_dma_write #(
1806:     .WAIT_FOR_DATA(1),
1807: 	.BURST_LEN  (BURST_LEN)   ,
1808: 	.ID_WIDTH   (AXI_ID_LEN)  ,
1809: 	.DATA_WIDTH (AXI_DATA_LEN)
1810: )
1811: ov5640_axi_dma_write(
1812:     .data_in_available(cam_s_data_available),
1813:     .abort_req(cam_dma_abort_req),
1814:     .data_in_abort(cam_dma_abort),
1815: 	.clk(axi_clk)                   ,
1816: 	.rst(axi_rst)                   ,
1817: 
1818: 	.cmd_valid (cam_cmd_valid)      ,
1819: 	.cmd_addr  (cam_cmd_addr )      ,
1820: 	.cmd_len   (cam_cmd_len  )      ,
1821: 	.cmd_id    (4'b0001)            ,
1822: 	.cmd_ready (cam_cmd_ready)      ,
1823: 
1824: 	.data_in       (cam_s_data          ),
1825: 	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1826: 	.data_in_valid (cam_s_data_valid    ),
1827: 	.data_in_last  (cam_dma_done     ),  // [LEDGER 2026-09-19]
1828: 	.data_in_ready (cam_s_data_ready    ),
1829: 
1830: 	.m_axi_awid    (ov5640_axi_awid    ),
1831: 	.m_axi_awaddr  (ov5640_axi_awaddr  ),
1832: 	.m_axi_awlen   (ov5640_axi_awlen   ),
1833: 	.m_axi_awsize  (ov5640_axi_awsize  ),
1834: 	.m_axi_awburst (ov5640_axi_awburst ),
1835: 	.m_axi_awlock  (ov5640_axi_awlock  ),
1836: 	.m_axi_awcache (ov5640_axi_awcache ),
1837: 	.m_axi_awprot  (ov5640_axi_awprot  ),
1838: 	.m_axi_awvalid (ov5640_axi_awvalid ),
1839: 	.m_axi_awready (ov5640_axi_awready ),
1840: 	.m_axi_wdata   (ov5640_axi_wdata   ),
1841: 	.m_axi_wstrb   (ov5640_axi_wstrb   ),
1842: 	.m_axi_wlast   (ov5640_axi_wlast   ),
1843: 	.m_axi_wvalid  (ov5640_axi_wvalid  ),
1844: 	.m_axi_wready  (ov5640_axi_wready  ),
1845: 	.m_axi_bid     (ov5640_axi_bid     ),
1846: 	.m_axi_bresp   (ov5640_axi_bresp   ),
1847: 	.m_axi_bvalid  (ov5640_axi_bvalid  ),
1848: 	.m_axi_bready  (ov5640_axi_bready  )
1849: );
1850: 
1851: axi_dma_write #(
1852:     .WAIT_FOR_DATA(1),
1853: 	.BURST_LEN  (BURST_LEN)   ,
1854: 	.ID_WIDTH   (AXI_ID_LEN)  ,
1855: 	.DATA_WIDTH (AXI_DATA_LEN)
1856: )
1857: cam2_axi_dma_write(
1858:     .data_in_available(cam2_s_data_available),
1859:     .abort_req(cam2_dma_abort_req),
1860:     .data_in_abort(cam2_dma_abort),
1861: 	.clk(axi_clk)                   ,
1862: 	.rst(axi_rst)                   ,
1863: 
1864: 	.cmd_valid (cam2_cmd_valid)     ,
1865: 	.cmd_addr  (cam2_cmd_addr )     ,
1866: 	.cmd_len   (cam2_cmd_len  )     ,
1867: 	.cmd_id    (4'b0100)            ,
1868: 	.cmd_ready (cam2_cmd_ready)     ,
1869: 
1870: 	.data_in       (cam2_s_data          ),
1871: 	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1872: 	.data_in_valid (cam2_s_data_valid    ),
1873: 	.data_in_last  (cam2_dma_done    ),  // [LEDGER 2026-09-19]
1874: 	.data_in_ready (cam2_s_data_ready    ),
1875: 
1876: 	.m_axi_awid    (cam2_axi_awid    ),
1877: 	.m_axi_awaddr  (cam2_axi_awaddr  ),
1878: 	.m_axi_awlen   (cam2_axi_awlen   ),
1879: 	.m_axi_awsize  (cam2_axi_awsize  ),
1880: 	.m_axi_awburst (cam2_axi_awburst ),
1881: 	.m_axi_awlock  (cam2_axi_awlock  ),
1882: 	.m_axi_awcache (cam2_axi_awcache ),
1883: 	.m_axi_awprot  (cam2_axi_awprot  ),
1884: 	.m_axi_awvalid (cam2_axi_awvalid ),
1885: 	.m_axi_awready (cam2_axi_awready ),
1886: 	.m_axi_wdata   (cam2_axi_wdata   ),
1887: 	.m_axi_wstrb   (cam2_axi_wstrb   ),
1888: 	.m_axi_wlast   (cam2_axi_wlast   ),
1889: 	.m_axi_wvalid  (cam2_axi_wvalid  ),
1890: 	.m_axi_wready  (cam2_axi_wready  ),
1891: 	.m_axi_bid     (cam2_axi_bid     ),
1892: 	.m_axi_bresp   (cam2_axi_bresp   ),
1893: 	.m_axi_bvalid  (cam2_axi_bvalid  ),
1894: 	.m_axi_bready  (cam2_axi_bready  )
1895: );
1896: 
1897: axi_dma_write #(
1898:     .WAIT_FOR_DATA(1),
1899: 	.BURST_LEN  (BURST_LEN)   ,
1900: 	.ID_WIDTH   (AXI_ID_LEN)  ,
1901: 	.DATA_WIDTH (AXI_DATA_LEN)
1902: )
1903: cam3_axi_dma_write(
1904:     .data_in_available(cam3_s_data_available),
1905:     .abort_req(cam3_dma_abort_req),
1906:     .data_in_abort(cam3_dma_abort),
1907: 	.clk(axi_clk)                   ,
1908: 	.rst(axi_rst)                   ,
1909: 
1910: 	.cmd_valid (cam3_cmd_valid)     ,
1911: 	.cmd_addr  (cam3_cmd_addr )     ,
1912: 	.cmd_len   (cam3_cmd_len  )     ,
1913: 	.cmd_id    (4'b0010)            ,
1914: 	.cmd_ready (cam3_cmd_ready)     ,
1915: 
1916: 	.data_in       (cam3_s_data          ),
1917: 	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1918: 	.data_in_valid (cam3_s_data_valid    ),
1919: 	.data_in_last  (cam3_dma_done    ),  // [LEDGER] per-camera single-beat marker
1920: 	.data_in_ready (cam3_s_data_ready    ),
1921: 
1922: 	.m_axi_awid    (cam3_axi_awid    ),
1923: 	.m_axi_awaddr  (cam3_axi_awaddr  ),
1924: 	.m_axi_awlen   (cam3_axi_awlen   ),
1925: 	.m_axi_awsize  (cam3_axi_awsize  ),
1926: 	.m_axi_awburst (cam3_axi_awburst ),
1927: 	.m_axi_awlock  (cam3_axi_awlock  ),
1928: 	.m_axi_awcache (cam3_axi_awcache ),
1929: 	.m_axi_awprot  (cam3_axi_awprot  ),
1930: 	.m_axi_awvalid (cam3_axi_awvalid ),
1931: 	.m_axi_awready (cam3_axi_awready ),
1932: 	.m_axi_wdata   (cam3_axi_wdata   ),
1933: 	.m_axi_wstrb   (cam3_axi_wstrb   ),
1934: 	.m_axi_wlast   (cam3_axi_wlast   ),
1935: 	.m_axi_wvalid  (cam3_axi_wvalid  ),
1936: 	.m_axi_wready  (cam3_axi_wready  ),
1937: 	.m_axi_bid     (cam3_axi_bid     ),
1938: 	.m_axi_bresp   (cam3_axi_bresp   ),
1939: 	.m_axi_bvalid  (cam3_axi_bvalid  ),
1940: 	.m_axi_bready  (cam3_axi_bready  )
1941: );
1942: 
1943: axi_dma_write #(
1944:     .WAIT_FOR_DATA(1),
1945: 	.BURST_LEN  (BURST_LEN)   ,
1946: 	.ID_WIDTH   (AXI_ID_LEN)  ,
1947: 	.DATA_WIDTH (AXI_DATA_LEN)
1948: )
1949: cam4_axi_dma_write(
1950:     .data_in_available(cam4_s_data_available),
1951:     .abort_req(cam4_dma_abort_req),
1952:     .data_in_abort(cam4_dma_abort),
1953: 	.clk(axi_clk)                   ,
1954: 	.rst(axi_rst)                   ,
1955: 
1956: 	.cmd_valid (cam4_cmd_valid)     ,
1957: 	.cmd_addr  (cam4_cmd_addr )     ,
1958: 	.cmd_len   (cam4_cmd_len  )     ,
1959: 	.cmd_id    (4'b1000)            ,
1960: 	.cmd_ready (cam4_cmd_ready)     ,
1961: 
1962: 	.data_in       (cam4_s_data          ),
1963: 	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
1964: 	.data_in_valid (cam4_s_data_valid    ),
1965: 	.data_in_last  (cam4_dma_done    ),  // [CAM4] per-camera single-beat marker
1966: 	.data_in_ready (cam4_s_data_ready    ),
1967: 
1968: 	.m_axi_awid    (cam4_axi_awid    ),
1969: 	.m_axi_awaddr  (cam4_axi_awaddr  ),
1970: 	.m_axi_awlen   (cam4_axi_awlen   ),
1971: 	.m_axi_awsize  (cam4_axi_awsize  ),
1972: 	.m_axi_awburst (cam4_axi_awburst ),
1973: 	.m_axi_awlock  (cam4_axi_awlock  ),
1974: 	.m_axi_awcache (cam4_axi_awcache ),
1975: 	.m_axi_awprot  (cam4_axi_awprot  ),
1976: 	.m_axi_awvalid (cam4_axi_awvalid ),
1977: 	.m_axi_awready (cam4_axi_awready ),
1978: 	.m_axi_wdata   (cam4_axi_wdata   ),
1979: 	.m_axi_wstrb   (cam4_axi_wstrb   ),
1980: 	.m_axi_wlast   (cam4_axi_wlast   ),
1981: 	.m_axi_wvalid  (cam4_axi_wvalid  ),
1982: 	.m_axi_wready  (cam4_axi_wready  ),
1983: 	.m_axi_bid     (cam4_axi_bid     ),
1984: 	.m_axi_bresp   (cam4_axi_bresp   ),
1985: 	.m_axi_bvalid  (cam4_axi_bvalid  ),
1986: 	.m_axi_bready  (cam4_axi_bready  )
1987: );
1988: 
1989: // ===================== preprocess datapath (PREP, batch-2) =====================
1990: reg [7:0] prep_frame_cnt;
1991: always @(posedge axi_clk) begin
1992:     if (axi_rst)
1993:         prep_frame_cnt <= 8'd0;
1994:     else if (prep_out_frame_start)
1995:         prep_frame_cnt <= prep_frame_cnt + 8'd1;
1996: end
1997: // camera raw stream -> cam_prep_link (tap) -> preprocess_top -> processed
1998: // write engine (second axi_dma_write, crossbar S03 write channel)
1999: wire [AXI_DATA_LEN-1:0] prep_wr_data;
2000: wire                    prep_wr_valid;
2001: wire                    prep_wr_ready;
2002: wire                    prep_wr_cmd_valid;
2003: wire                    prep_wr_cmd_ready;
2004: wire [31:0]             prep_wr_cmd_addr;
2005: wire [31:0]             prep_wr_cmd_len;
2006: wire [15:0]             prep_pp_data;
2007: wire                    prep_pp_valid;
2008: wire                    prep_pp_ready;
2009: wire                    prep_pp_fsync;
2010: wire [15:0]             prep_out_data;
2011: wire                    prep_out_valid;
2012: wire                    prep_out_ready;
2013: wire                    prep_out_fsync;
2014: wire                    prep_out_frame_start;
2015: wire                    prep_edge_valid;
2016: wire                    prep_edge_bit;
2017: wire [7:0]              prep_edge_center;
2018: wire                    prep_cid_valid;
2019: wire [1:0]              prep_cid;
2020: wire [1:0]              lane_left_type_w, lane_right_type_w;
2021: wire                    lane_left_valid_w, lane_right_valid_w, lane_frame_upd_w;
2022: 
2023: // [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
2024: // cam_prep_link #(
2025: //     .FRAME_H (720),
2026: //     .BUFFER0 (32'h0A00_0000),
2027: //     .BUFFER1 (32'h0A1C_2000)
2028: // ) cam_prep_link_u (
2029: //     .clk            (axi_clk),
2030: //     .rst            (axi_rst),
2031: //     .img_width      (prep_img_width_w),
2032: //     .bypass_mode    (prep_bypass_w),
2033: //     .mode           (prep_mode_w),
2034: //     .cam_data       (cam_tap_data),
2035: //     .cam_valid      (cam_tap_data_valid),
2036: //     .cam_ready      (cam_tap_data_ready),
2037: //     .cam_frame_sync (cam_cmd_valid),
2038: //     .raw_data       (cam_s_data),
2039: //     .raw_valid      (cam_s_data_valid),
2040: //     .raw_ready      (cam_s_data_ready),
2041: //     .pp_data        (prep_pp_data),
2042: //     .pp_valid       (prep_pp_valid),
2043: //     .pp_ready       (prep_pp_ready),
2044: //     .pp_frame_sync  (prep_pp_fsync),
2045: //     .out_data       (prep_out_data),
2046: //     .out_valid      (prep_out_valid),
2047: //     .out_ready      (prep_out_ready),
2048: //     .out_frame_sync (prep_out_fsync),
2049: //     .wr_cmd_valid   (prep_wr_cmd_valid),
2050: //     .wr_cmd_ready   (prep_wr_cmd_ready),
2051: //     .wr_cmd_addr    (prep_wr_cmd_addr),
2052: //     .wr_cmd_len     (prep_wr_cmd_len),
2053: //     .wr_data        (prep_wr_data),
2054: //     .wr_valid       (prep_wr_valid),
2055: //     .wr_ready       (prep_wr_ready)
2056: // );
2057: 
2058: // [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
2059: // preprocess_top #(
2060: //     .MAX_WIDTH   (1920),
2061: //     .FIFO_DEPTH  (512)
2062: // ) preprocess_top_u (
2063: //     .clk            (axi_clk),
2064: //     .rst_n          (~axi_rst),
2065: //     .s_rgb565       (prep_pp_data),
2066: //     .s_valid        (prep_pp_valid),
2067: //     .s_ready        (prep_pp_ready),
2068: //     .s_frame_sync   (prep_pp_fsync),
2069: //     .m_ready        (prep_out_ready),
2070: //     .m_rgb565       (prep_out_data),
2071: //     .m_valid        (prep_out_valid),
2072: //     .m_frame_sync   (prep_out_fsync),
2073: //     .reg_bypass     (prep_bypass_w),
2074: //     .reg_mode       (prep_mode_w),
2075: //     .reg_img_width  (prep_img_width_w),
2076: //     .reg_thr_sat    (prep_thr_sat_w),
2077: //     .reg_thr_hue    (prep_thr_hue_w),
2078: //     .reg_thr_val    (prep_thr_val_w),
2079: //     .reg_thr_low    (prep_thr_low_w),
2080: //     .reg_thr_edge   (prep_thr_edge_w),
2081: //     .out_frame_start(prep_out_frame_start),
2082: //     .edge_stream_valid (prep_edge_valid),
2083: //     .edge_stream_edge  (prep_edge_bit),
2084: //     .edge_stream_center(prep_edge_center),
2085: //     .color_id_valid (prep_cid_valid),
2086: //     .color_id       (prep_cid)
2087: // );
2088: 
2089: // [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
2090: // lane_detect #(
2091: //     .MAX_WIDTH(1920)
2092: // ) lane_detect_u (
2093: //     .clk        (axi_clk),
2094: //     .rst_n      (~axi_rst),
2095: //     .img_width  (prep_img_width_w),
2096: //     .img_height (12'd720),
2097: //     .roi_top_pct(prep_lane_roi_top_w),
2098: //     .roi_bot_pct(prep_lane_roi_bot_w),
2099: //     .row_thr    (prep_lane_row_thr_w),
2100: //     .dash_thr   (prep_lane_dash_thr_w),
2101: //     .s_center   (prep_edge_center),
2102: //     .s_edge     (prep_edge_bit),
2103: //     .s_valid    (prep_edge_valid),
2104: //     .s_frame_sync(prep_out_frame_start),
2105: //     .m_left_type (lane_left_type_w),
2106: //     .m_right_type(lane_right_type_w),
2107: //     .m_left_valid (lane_left_valid_w),
2108: //     .m_right_valid(lane_right_valid_w),
2109: //     .m_frame_upd  (lane_frame_upd_w)
2110: // );
2111: 
2112: 
2113: // ===== [2026-09-12] RAW camera path restored =====
2114: // OptionB commented out cam_prep_link but left cam_s_data undriven, so the
2115: // camera never wrote DDR -> no frames / no MSI. ov5640_top already emits a
2116: // complete raw AXI-stream write request, so wire it straight to the raw write
2117: // engine. The preprocess tap is intentionally NOT used (its TB still fails and
2118: // its dummy-inject can back-pressure/stall the camera).
2119: assign cam_s_data         = cam_tap_data;
2120: assign cam_s_data_valid   = cam_tap_data_valid;
2121: assign cam_s_data_last    = cam_tap_data_last;
2122: assign cam_tap_data_ready = cam_s_data_ready;
2123: 
2124: // preprocess datapath disabled: keep the processed-frame write engine idle
2125: assign prep_wr_cmd_valid = 1'b0;
2126: assign prep_wr_cmd_addr  = 32'b0;
2127: assign prep_wr_cmd_len   = 32'b0;
2128: assign prep_wr_data      = 128'b0;
2129: assign prep_wr_valid     = 1'b0;
2130: 
2131: // processed-frame write engine (second write master -> crossbar S03 AW/W/B)
2132: wire [AXI_ID_LEN-1:0]   prep2_axi_awid;
2133: wire [31:0]             prep2_axi_awaddr;
2134: wire [3:0]              prep2_axi_awlen;
2135: wire [2:0]              prep2_axi_awsize;
2136: wire [1:0]              prep2_axi_awburst;
2137: wire                    prep2_axi_awlock;
2138: wire [3:0]              prep2_axi_awcache;
2139: wire [2:0]              prep2_axi_awprot;
2140: wire                    prep2_axi_awvalid;
2141: wire                    prep2_axi_awready;
2142: wire [AXI_DATA_LEN-1:0] prep2_axi_wdata;
2143: wire [AXI_STRB_LEN-1:0] prep2_axi_wstrb;
2144: wire                    prep2_axi_wlast;
2145: wire                    prep2_axi_wvalid;
2146: wire                    prep2_axi_wready;
2147: wire [AXI_ID_LEN-1:0]   prep2_axi_bid;
2148: wire [1:0]              prep2_axi_bresp;
2149: wire                    prep2_axi_bvalid;
2150: wire                    prep2_axi_bready;
2151: 
2152: axi_dma_write #(
2153:     .BURST_LEN  (BURST_LEN),
2154:     .ID_WIDTH   (AXI_ID_LEN),
2155:     .DATA_WIDTH (AXI_DATA_LEN)
2156: ) prep_axi_dma_write(
2157:     .data_in_available(16'd0),
2158:     .abort_req(1'b0),
2159:     .data_in_abort(),
2160:     .clk(axi_clk),
2161:     .rst(axi_rst),
2162:     .cmd_valid (prep_wr_cmd_valid),
2163:     .cmd_addr  (prep_wr_cmd_addr),
2164:     .cmd_len   (prep_wr_cmd_len),
2165:     .cmd_id    (4'b0111),
2166:     .cmd_ready (prep_wr_cmd_ready),
2167:     .data_in       (prep_wr_data),
2168:     .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
2169:     .data_in_valid (prep_wr_valid),
2170:     .data_in_last  (),
2171:     .data_in_ready (prep_wr_ready),
2172:     .m_axi_awid    (prep2_axi_awid),
2173:     .m_axi_awaddr  (prep2_axi_awaddr),
2174:     .m_axi_awlen   (prep2_axi_awlen),
2175:     .m_axi_awsize  (prep2_axi_awsize),
2176:     .m_axi_awburst (prep2_axi_awburst),
2177:     .m_axi_awlock  (prep2_axi_awlock),
2178:     .m_axi_awcache (prep2_axi_awcache),
2179:     .m_axi_awprot  (prep2_axi_awprot),
2180:     .m_axi_awvalid (prep2_axi_awvalid),
2181:     .m_axi_awready (prep2_axi_awready),
2182:     .m_axi_wdata   (prep2_axi_wdata),
2183:     .m_axi_wstrb   (prep2_axi_wstrb),
2184:     .m_axi_wlast   (prep2_axi_wlast),
2185:     .m_axi_wvalid  (prep2_axi_wvalid),
2186:     .m_axi_wready  (prep2_axi_wready),
2187:     .m_axi_bid     (prep2_axi_bid),
2188:     .m_axi_bresp   (prep2_axi_bresp),
2189:     .m_axi_bvalid  (prep2_axi_bvalid),
2190:     .m_axi_bready  (prep2_axi_bready)
2191: );
2192: // =================== preprocess datapath end ===================
2193: 
2194: 
2195: /////////////////////////////////////////////////////////////////////////////////////////////
2196: wire [AXI_ID_M_LEN-1:0]   npu_reg_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
2197: wire [31:0]             npu_reg_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
2198: wire [7:0]              npu_reg_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
2199: wire [2:0]              npu_reg_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
2200: wire [1:0]              npu_reg_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
2201: wire                    npu_reg_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
2202: wire [3:0]              npu_reg_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
2203: wire [2:0]              npu_reg_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
2204: wire                    npu_reg_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
2205: wire                    npu_reg_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
2206: wire [AXI_DATA_LEN-1:0] npu_reg_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
2207: wire [AXI_STRB_LEN-1:0] npu_reg_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
2208: wire                    npu_reg_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
2209: wire                    npu_reg_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
2210: wire                    npu_reg_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
2211: wire [AXI_ID_M_LEN-1:0]   npu_reg_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
2212: wire [1:0]              npu_reg_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
2213: wire                    npu_reg_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
2214: wire                    npu_reg_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;
2215: 
2216: 
2217: 
2218: 
2219: 
2220: 
2221:     
2222: 
2223: 
2224: 
2225: 
2226: 
2227: 
2228: 
2229: 
2230:     wire [AXI_ID_LEN-1:0]   npu_out_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
2231:     wire [31:0]             npu_out_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
2232:     wire [3:0]              npu_out_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
2233:     wire [2:0]              npu_out_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
2234:     wire [1:0]              npu_out_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
2235:     wire                    npu_out_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
2236:     wire [3:0]              npu_out_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
2237:     wire [2:0]              npu_out_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
2238:     wire                    npu_out_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
2239:     wire                    npu_out_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
2240:     wire [AXI_DATA_LEN-1:0] npu_out_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
2241:     wire [AXI_STRB_LEN-1:0] npu_out_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
2242:     wire                    npu_out_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
2243:     wire                    npu_out_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
2244:     wire                    npu_out_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
2245:     wire [AXI_ID_LEN-1:0]   npu_out_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
2246:     wire [1:0]              npu_out_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
2247:     wire                    npu_out_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
2248:     wire                    npu_out_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;
2249: 
2250: 
2251:     wire    [AXI_ID_LEN-1:0]    npu_s0_axi_arid    ;
2252:     wire    [31:0]              npu_s0_axi_araddr  ;
2253:     wire    [3:0]               npu_s0_axi_arlen   ;
2254:     wire    [2:0]               npu_s0_axi_arsize  ;
2255:     wire    [1:0]               npu_s0_axi_arburst ;
2256:     wire                        npu_s0_axi_arlock  ;
2257:     wire    [3:0]               npu_s0_axi_arcache ;
2258:     wire    [2:0]               npu_s0_axi_arprot  ;
2259:     wire                        npu_s0_axi_arvalid ;
2260:     wire                        npu_s0_axi_arready ;
2261:     wire    [AXI_ID_LEN-1:0]    npu_s0_axi_rid     ;
2262:     wire    [AXI_DATA_LEN-1:0]  npu_s0_axi_rdata   ;
2263:     wire    [1:0]               npu_s0_axi_rresp   ;
2264:     wire                        npu_s0_axi_rlast   ;
2265:     wire                        npu_s0_axi_rvalid  ;
2266:     wire                        npu_s0_axi_rready  ;
2267: 
2268: 
2269:     wire    [AXI_ID_LEN-1:0]    npu_s1_axi_arid    ;
2270:     wire    [31:0]              npu_s1_axi_araddr  ;
2271:     wire    [3:0]               npu_s1_axi_arlen   ;
2272:     wire    [2:0]               npu_s1_axi_arsize  ;
2273:     wire    [1:0]               npu_s1_axi_arburst ;
2274:     wire                        npu_s1_axi_arlock  ;
2275:     wire    [3:0]               npu_s1_axi_arcache ;
2276:     wire    [2:0]               npu_s1_axi_arprot  ;
2277:     wire                        npu_s1_axi_arvalid ;
2278:     wire                        npu_s1_axi_arready ;
2279:     wire    [AXI_ID_LEN-1:0]    npu_s1_axi_rid     ;
2280:     wire    [AXI_DATA_LEN-1:0]  npu_s1_axi_rdata   ;
2281:     wire    [1:0]               npu_s1_axi_rresp   ;
2282:     wire                        npu_s1_axi_rlast   ;
2283:     wire                        npu_s1_axi_rvalid  ;
2284:     wire                        npu_s1_axi_rready  ;
2285: 
2286: 
2287: 
2288: 
2289: 
2290: 
2291:     wire    [AXI_ID_LEN-1:0]    npu_s2_axi_arid    ;
2292:     wire    [31:0]              npu_s2_axi_araddr  ;
2293:     wire    [3:0]               npu_s2_axi_arlen   ;
2294:     wire    [2:0]               npu_s2_axi_arsize  ;
2295:     wire    [1:0]               npu_s2_axi_arburst ;
2296:     wire                        npu_s2_axi_arlock  ;
2297:     wire    [3:0]               npu_s2_axi_arcache ;
2298:     wire    [2:0]               npu_s2_axi_arprot  ;
2299:     wire                        npu_s2_axi_arvalid ;
2300:     wire                        npu_s2_axi_arready ;
2301:     wire    [AXI_ID_LEN-1:0]    npu_s2_axi_rid     ;
2302:     wire    [AXI_DATA_LEN-1:0]  npu_s2_axi_rdata   ;
2303:     wire    [1:0]               npu_s2_axi_rresp   ;
2304:     wire                        npu_s2_axi_rlast   ;
2305:     wire                        npu_s2_axi_rvalid  ;
2306:     wire                        npu_s2_axi_rready  ;
2307: 
2308: 
2309: 
2310: 
2311: 
2312: 
2313:     wire    [AXI_ID_LEN-1:0]    npu_s3_axi_arid    ;
2314:     wire    [31:0]              npu_s3_axi_araddr  ;
2315:     wire    [3:0]               npu_s3_axi_arlen   ;
2316:     wire    [2:0]               npu_s3_axi_arsize  ;
2317:     wire    [1:0]               npu_s3_axi_arburst ;
2318:     wire                        npu_s3_axi_arlock  ;
2319:     wire    [3:0]               npu_s3_axi_arcache ;
2320:     wire    [2:0]               npu_s3_axi_arprot  ;
2321:     wire                        npu_s3_axi_arvalid ;
2322:     wire                        npu_s3_axi_arready ;
2323:     wire    [AXI_ID_LEN-1:0]    npu_s3_axi_rid     ;
2324:     wire    [AXI_DATA_LEN-1:0]  npu_s3_axi_rdata   ;
2325:     wire    [1:0]               npu_s3_axi_rresp   ;
2326:     wire                        npu_s3_axi_rlast   ;
2327:     wire                        npu_s3_axi_rvalid  ;
2328:     wire                        npu_s3_axi_rready  ;
2329: 
2330: 
2331: 
2332: 
2333: 
2334: 
2335:     wire    [AXI_ID_LEN-1:0]    npu_s4_axi_arid    ;
2336:     wire    [31:0]              npu_s4_axi_araddr  ;
2337:     wire    [3:0]               npu_s4_axi_arlen   ;
2338:     wire    [2:0]               npu_s4_axi_arsize  ;
2339:     wire    [1:0]               npu_s4_axi_arburst ;
2340:     wire                        npu_s4_axi_arlock  ;
2341:     wire    [3:0]               npu_s4_axi_arcache ;
2342:     wire    [2:0]               npu_s4_axi_arprot  ;
2343:     wire                        npu_s4_axi_arvalid ;
2344:     wire                        npu_s4_axi_arready ;
2345:     wire    [AXI_ID_LEN-1:0]    npu_s4_axi_rid     ;
2346:     wire    [AXI_DATA_LEN-1:0]  npu_s4_axi_rdata   ;
2347:     wire    [1:0]               npu_s4_axi_rresp   ;
2348:     wire                        npu_s4_axi_rlast   ;
2349:     wire                        npu_s4_axi_rvalid  ;
2350:     wire                        npu_s4_axi_rready  ;
2351: 
2352: 
2353: // ===== NPU removed: tie off crossbar-facing NPU ports =====
2354: // S02 write (npu_out) + S02 read (npu_s0)
2355: assign npu_out_axi_awvalid = 1'b0;
2356: assign npu_out_axi_wvalid  = 1'b0;
2357: assign npu_out_axi_bready  = 1'b1;
2358: 
2359: 
2360: // S03 read (npu_s1) ; S03 write (prep2) stays active
2361: assign npu_s1_axi_arvalid  = 1'b0;
2362: assign npu_s1_axi_rready   = 1'b1;
2363: // S04/S05/S06 read (npu_s2/s3/s4)
2364: assign npu_s2_axi_arvalid  = 1'b0;
2365: assign npu_s2_axi_rready   = 1'b1;
2366: // [VKFS 2026-09-25] S05 (npu_s3) is driven by cam1's vip_kf_stream read master
2367: // (was tied off). Keep S02/S04/S06 tied off.
2368: assign npu_s4_axi_arvalid  = 1'b0;
2369: assign npu_s4_axi_rready   = 1'b1;
2370: // M02 (NPU register window) response inputs
2371: 
2372: 
2373: 
2374: 
2375: 
2376: wire   [AXI_ID_M_LEN-1:0]   npu_reg_axi_rid;
2377: wire   [AXI_DATA_LEN-1:0] npu_reg_axi_rdata;
2378: wire   [1:0]              npu_reg_axi_rresp;
2379: wire                      npu_reg_axi_rlast;
2380: wire                      npu_reg_axi_rvalid;
2381: wire                      npu_reg_axi_arready;
2382: 
2383: 
2384: 
2385: 
2386: 
2387: 
2388: 
2389: ///////////////////////////////////////////////////////////////////////////////////////////
2390: axi_crossbar_7x3 #(
2391:     //.DATA_WIDTH(AXI_DATA_LEN)
2392:     .DATA_WIDTH(AXI_DATA_LEN),
2393:     // M00 (DDR3) \xef\xbf\xbd\xc4\xb7\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc8\xa8\xef\xbf\xbd\xde\xa3\xef\xbf\xbd
2394:     // \xef\xbf\xbd\xef\xbf\xbd DDR: \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd PCIE(S00) \xef\xbf\xbd\xef\xbf\xbd NPU\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xcd\xa8\xef\xbf\xbd\xef\xbf\xbd(S02-S06)\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd6\xb9 Camera(S01)
2395:     .M00_CONNECT_READ  (7'b1111101), 
2396:     // \xd0\xb4 DDR: \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd PCIE(S00), Camera(S01), NPU_S0(S02)\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd6\xb9 NPU_S1~S4(S03-S06)
2397:     .M00_CONNECT_WRITE (7'b0000000),  // [WARB 2026-09-19] write path moved to ddr_w_arb
2398:                                       // (crossbar M00 write leaked its W-channel select
2399:                                       //  across handoffs -> permanent wedge; bench-proven)
2400:     
2401:     // M01 (OV5640 \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc6\xbc\xc4\xb4\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd) \xef\xbf\xbd\xc4\xb7\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc8\xa8\xef\xbf\xbd\xde\xa3\xef\xbf\xbd
2402:     // \xd6\xbb\xef\xbf\xbd\xef\xbf\xbd PCIE (S00) \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd4\xb6\xef\xbf\xbd\xd0\xb4\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd0\xb6\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xcd\xa8\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc4\xb8\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd
2403:     .M01_CONNECT_READ  (7'b0000001),
2404:     .M01_CONNECT_WRITE (7'b0000001),
2405:     
2406:     // M02 (NPU \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc6\xbc\xc4\xb4\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd) \xef\xbf\xbd\xc4\xb7\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xc8\xa8\xef\xbf\xbd\xde\xa3\xef\xbf\xbd
2407:     // \xd6\xbb\xef\xbf\xbd\xef\xbf\xbd PCIE (S00) \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xd4\xb6\xef\xbf\xbd\xd0\xb4
2408:     .M02_CONNECT_READ  (7'b0000001),
2409:     .M02_CONNECT_WRITE (7'b0000001)
2410: )
2411: axi_crossbar_7x3
2412: (
2413:     .clk(axi_clk),
2414:     .rst(axi_rst),
2415: 
2416:     /*
2417:      * AXI slave interface
2418:      */
2419:     .s00_axi_awid   (pcie_axi_awid   ) ,
2420:     .s00_axi_awaddr (pcie_axi_awaddr ) ,
2421:     .s00_axi_awlen  (pcie_axi_awlen  ) ,
2422:     .s00_axi_awsize (pcie_axi_awsize ) ,
2423:     .s00_axi_awburst(pcie_axi_awburst) ,
2424:     .s00_axi_awlock (pcie_axi_awlock ) ,
2425:     .s00_axi_awcache(pcie_axi_awcache) ,
2426:     .s00_axi_awprot (pcie_axi_awprot ) ,
2427:     .s00_axi_awqos  (pcie_axi_awqos  ) ,
2428:     .s00_axi_awvalid(pcie_axi_awvalid) ,
2429:     .s00_axi_awready(pcie_axi_awready) ,
2430:     .s00_axi_awuser () ,
2431: 
2432:     .s00_axi_wdata  (pcie_axi_wdata  ) ,
2433:     .s00_axi_wstrb  (pcie_axi_wstrb  ) ,
2434:     .s00_axi_wlast  (pcie_axi_wlast  ) ,
2435:     .s00_axi_wready (pcie_axi_wready ) ,
2436:     .s00_axi_wvalid (pcie_axi_wvalid ) ,
2437:     .s00_axi_wuser  () ,
2438: 
2439:     .s00_axi_bid     (pcie_axi_bid   ),   
2440:     .s00_axi_bresp   (pcie_axi_bresp ),
2441:     .s00_axi_bvalid  (pcie_axi_bvalid),
2442:     .s00_axi_bready  (pcie_axi_bready),
2443:     .s00_axi_buser   (),
2444: 
2445:     .s00_axi_arid    (pcie_axi_arid   )     ,
2446:     .s00_axi_araddr  (pcie_axi_araddr )     ,
2447:     .s00_axi_arlen   (pcie_axi_arlen  )     ,
2448:     .s00_axi_arsize  (pcie_axi_arsize )     ,
2449:     .s00_axi_arburst (pcie_axi_arburst)     ,
2450:     .s00_axi_arlock  (pcie_axi_arlock )     ,
2451:     .s00_axi_arcache (pcie_axi_arcache)     ,
2452:     .s00_axi_arprot  (pcie_axi_arprot )     ,
2453:     .s00_axi_arqos   (pcie_axi_arqos  )     ,
2454:     .s00_axi_arvalid (pcie_axi_arvalid)     ,
2455:     .s00_axi_arready (pcie_axi_arready)     ,
2456:     .s00_axi_aruser  (),
2457: 
2458:     .s00_axi_rid     (pcie_axi_rid    ),
2459:     .s00_axi_rdata   (pcie_axi_rdata  ),
2460:     .s00_axi_rresp   (pcie_axi_rresp  ),
2461:     .s00_axi_rlast   (pcie_axi_rlast  ),
2462:     .s00_axi_rvalid  (pcie_axi_rvalid ),
2463:     .s00_axi_rready  (pcie_axi_rready ),
2464:     .s00_axi_ruser   (),
2465: 
2466:     // [WARB] S01 write retired (camera DMAs go through ddr_w_arb)
2467:     .s01_axi_awid    (4'd0               ),
2468:     .s01_axi_awaddr  (32'd0              ),
2469:     .s01_axi_awlen   (8'd0               ),
2470:     .s01_axi_awsize  (3'd0               ),
2471:     .s01_axi_awburst (2'd0               ),
2472:     .s01_axi_awlock  (1'b0               ),
2473:     .s01_axi_awcache (4'd0               ),
2474:     .s01_axi_awprot  (3'd0               ),
2475:     .s01_axi_awqos   (4'd0               ),
2476:     .s01_axi_awvalid (1'b0               ),
2477:     .s01_axi_awready (               ),
2478:     .s01_axi_awuser  (               ),
2479:     .s01_axi_wdata   (128'd0             ),
2480:     .s01_axi_wstrb   (16'd0              ),
2481:     .s01_axi_wlast   (1'b0               ),
2482:     .s01_axi_wvalid  (1'b0               ),
2483:     .s01_axi_wready  (               ),
2484:     .s01_axi_wuser   (               ),
2485:     .s01_axi_bid     (               ),
2486:     .s01_axi_bresp   (               ),
2487:     .s01_axi_bvalid  (               ),
2488:     .s01_axi_bready  (1'b0               ),
2489:     .s01_axi_buser   (               ),
2490:     .s01_axi_arid    (4'd0               ),
2491:     .s01_axi_araddr  (32'd0              ),
2492:     .s01_axi_arlen   (8'd0               ),
2493:     .s01_axi_arsize  (3'd0               ),
2494:     .s01_axi_arburst (2'd0               ),
2495:     .s01_axi_arlock  (1'b0               ),
2496:     .s01_axi_arcache (4'd0               ),
2497:     .s01_axi_arprot  (3'd0               ),
2498:     .s01_axi_arqos   (4'd0               ),
2499:     .s01_axi_aruser  (1'b0               ),
2500:     .s01_axi_arvalid (1'b0               ),
2501:     .s01_axi_arready (),
2502:     .s01_axi_rid     (),
2503:     .s01_axi_rdata   (),
2504:     .s01_axi_rresp   (),
2505:     .s01_axi_rlast   (),
2506:     .s01_axi_ruser   (),
2507:     .s01_axi_rvalid  (),
2508:     .s01_axi_rready  (1'b0               ),
2509: 
2510:     .s02_axi_awid   (npu_out_axi_awid   ),
2511:     .s02_axi_awaddr (npu_out_axi_awaddr ),
2512:     .s02_axi_awlen  (npu_out_axi_awlen  ),
2513:     .s02_axi_awsize (npu_out_axi_awsize ),
2514:     .s02_axi_awburst(npu_out_axi_awburst),
2515:     .s02_axi_awlock (npu_out_axi_awlock ),
2516:     .s02_axi_awcache(npu_out_axi_awcache),
2517:     .s02_axi_awprot (npu_out_axi_awprot ),
2518:     .s02_axi_awqos  (4'd0),
2519:     .s02_axi_awuser (),
2520:     .s02_axi_awvalid(npu_out_axi_awvalid),
2521:     .s02_axi_awready(npu_out_axi_awready),
2522:     .s02_axi_wdata  (npu_out_axi_wdata  ),
2523:     .s02_axi_wstrb  (npu_out_axi_wstrb  ),
2524:     .s02_axi_wlast  (npu_out_axi_wlast  ),
2525:     .s02_axi_wvalid (npu_out_axi_wvalid ),
2526:     .s02_axi_wready (npu_out_axi_wready ),
2527:     .s02_axi_wuser  (),
2528:     .s02_axi_bid    (npu_out_axi_bid    ),
2529:     .s02_axi_bresp  (npu_out_axi_bresp  ),
2530:     .s02_axi_bvalid (npu_out_axi_bvalid ),
2531:     .s02_axi_bready (npu_out_axi_bready ),
2532:     .s02_axi_buser  (),
2533: 
2534:     .s02_axi_arid   (npu_s0_axi_arid    ),
2535:     .s02_axi_araddr (npu_s0_axi_araddr  ),
2536:     .s02_axi_arlen  (npu_s0_axi_arlen   ),
2537:     .s02_axi_arsize (npu_s0_axi_arsize  ),
2538:     .s02_axi_arburst(npu_s0_axi_arburst ),
2539:     .s02_axi_arlock (npu_s0_axi_arlock  ),
2540:     .s02_axi_arcache(npu_s0_axi_arcache ),
2541:     .s02_axi_arprot (npu_s0_axi_arprot  ),
2542:     .s02_axi_arqos(v8_read_arqos),
2543:     .s02_axi_aruser (),
2544:     .s02_axi_arvalid(npu_s0_axi_arvalid ),
2545:     .s02_axi_arready(npu_s0_axi_arready ),
2546:     .s02_axi_rid    (npu_s0_axi_rid     ),
2547:     .s02_axi_rdata  (npu_s0_axi_rdata   ),
2548:     .s02_axi_rresp  (npu_s0_axi_rresp   ),
2549:     .s02_axi_rlast  (npu_s0_axi_rlast   ),
2550:     .s02_axi_rvalid (npu_s0_axi_rvalid  ),
2551:     .s02_axi_rready (npu_s0_axi_rready  ),
2552:     .s02_axi_ruser  (),
2553: 
2554:     .s03_axi_awid   (prep2_axi_awid   ),
2555:     .s03_axi_awaddr (prep2_axi_awaddr ),
2556:     .s03_axi_awlen  (prep2_axi_awlen  ),
2557:     .s03_axi_awsize (prep2_axi_awsize ),
2558:     .s03_axi_awburst(prep2_axi_awburst),
2559:     .s03_axi_awlock (prep2_axi_awlock ),
2560:     .s03_axi_awcache(prep2_axi_awcache),
2561:     .s03_axi_awprot (prep2_axi_awprot ),
2562:     .s03_axi_awqos  (4'd0),
2563:     .s03_axi_awuser (),
2564:     .s03_axi_awvalid(prep2_axi_awvalid),
2565:     .s03_axi_awready(prep2_axi_awready),
2566:     .s03_axi_wdata  (prep2_axi_wdata ),
2567:     .s03_axi_wstrb  (prep2_axi_wstrb ),
2568:     .s03_axi_wlast  (prep2_axi_wlast ),
2569:     .s03_axi_wuser  (),
2570:     .s03_axi_wvalid (prep2_axi_wvalid),
2571:     .s03_axi_wready (prep2_axi_wready),
2572:     .s03_axi_bid    (prep2_axi_bid   ),
2573:     .s03_axi_bresp  (prep2_axi_bresp ),
2574:     .s03_axi_buser  (),
2575:     .s03_axi_bvalid (prep2_axi_bvalid),
2576:     .s03_axi_bready (prep2_axi_bready),
2577:     .s03_axi_arid   (npu_s1_axi_arid    ),
2578:     .s03_axi_araddr (npu_s1_axi_araddr  ),
2579:     .s03_axi_arlen  (npu_s1_axi_arlen   ),
2580:     .s03_axi_arsize (npu_s1_axi_arsize  ),
2581:     .s03_axi_arburst(npu_s1_axi_arburst ),
2582:     .s03_axi_arlock (npu_s1_axi_arlock  ),
2583:     .s03_axi_arcache(npu_s1_axi_arcache ),
2584:     .s03_axi_arprot (npu_s1_axi_arprot  ),
2585:     .s03_axi_arqos  (4'd0),
2586:     .s03_axi_aruser (),
2587:     .s03_axi_arvalid(npu_s1_axi_arvalid ),
2588:     .s03_axi_arready(npu_s1_axi_arready ),
2589:     .s03_axi_rid    (npu_s1_axi_rid     ),
2590:     .s03_axi_rdata  (npu_s1_axi_rdata   ),
2591:     .s03_axi_rresp  (npu_s1_axi_rresp   ),
2592:     .s03_axi_rlast  (npu_s1_axi_rlast   ),
2593:     .s03_axi_rvalid (npu_s1_axi_rvalid  ),
2594:     .s03_axi_rready (npu_s1_axi_rready  ),
2595:     .s03_axi_ruser  (),
2596: 
2597:     // [WARB] S04 write retired (cam2 DMA goes through ddr_w_arb)
2598:     .s04_axi_awid   (4'd0            ),
2599:     .s04_axi_awaddr (32'd0           ),
2600:     .s04_axi_awlen  (8'd0            ),
2601:     .s04_axi_awsize (3'd0            ),
2602:     .s04_axi_awburst(2'd0            ),
2603:     .s04_axi_awlock (1'b0            ),
2604:     .s04_axi_awcache(4'd0            ),
2605:     .s04_axi_awprot (3'd0            ),
2606:     .s04_axi_awqos  (4'd0),
2607:     .s04_axi_awuser (),
2608:     .s04_axi_awvalid(1'b0            ),
2609:     .s04_axi_awready(                ),
2610:     .s04_axi_wdata  (128'd0          ),
2611:     .s04_axi_wstrb  (16'd0           ),
2612:     .s04_axi_wlast  (1'b0            ),
2613:     .s04_axi_wuser  (),
2614:     .s04_axi_wvalid (1'b0            ),
2615:     .s04_axi_wready (                ),
2616:     .s04_axi_bid    (                ),
2617:     .s04_axi_bresp  (                ),
2618:     .s04_axi_buser  (),
2619:     .s04_axi_bvalid (                ),
2620:     .s04_axi_bready (1'b0            ),
2621:     .s04_axi_arid   (npu_s2_axi_arid    ),
2622:     .s04_axi_araddr (npu_s2_axi_araddr  ),
2623:     .s04_axi_arlen  (npu_s2_axi_arlen   ),
2624:     .s04_axi_arsize (npu_s2_axi_arsize  ),
2625:     .s04_axi_arburst(npu_s2_axi_arburst ),
2626:     .s04_axi_arlock (npu_s2_axi_arlock  ),
2627:     .s04_axi_arcache(npu_s2_axi_arcache ),
2628:     .s04_axi_arprot (npu_s2_axi_arprot  ),
2629:     .s04_axi_arqos  (4'd0),
2630:     .s04_axi_aruser (),
2631:     .s04_axi_arvalid(npu_s2_axi_arvalid ),
2632:     .s04_axi_arready(npu_s2_axi_arready ),
2633:     .s04_axi_rid    (npu_s2_axi_rid     ),
2634:     .s04_axi_rdata  (npu_s2_axi_rdata   ),
2635:     .s04_axi_rresp  (npu_s2_axi_rresp   ),
2636:     .s04_axi_rlast  (npu_s2_axi_rlast   ),
2637:     .s04_axi_rvalid (npu_s2_axi_rvalid  ),
2638:     .s04_axi_rready (npu_s2_axi_rready  ),
2639:     .s04_axi_ruser  (),
2640: 
2641:     .s05_axi_awid(),
2642:     .s05_axi_awaddr(),
2643:     .s05_axi_awlen(),
2644:     .s05_axi_awsize(),
2645:     .s05_axi_awburst(),
2646:     .s05_axi_awlock(),
2647:     .s05_axi_awcache(),
2648:     .s05_axi_awprot(),
2649:     .s05_axi_awqos(),
2650:     .s05_axi_awuser(),
2651:     .s05_axi_awvalid(),
2652:     .s05_axi_awready(),
2653:     .s05_axi_wdata(),
2654:     .s05_axi_wstrb(),
2655:     .s05_axi_wlast(),
2656:     .s05_axi_wuser(),
2657:     .s05_axi_wvalid(),
2658:     .s05_axi_wready(),
2659:     .s05_axi_bid(),
2660:     .s05_axi_bresp(),
2661:     .s05_axi_buser(),
2662:     .s05_axi_bvalid(),
2663:     .s05_axi_bready(),
2664:     .s05_axi_arid   (npu_s3_axi_arid    ),
2665:     .s05_axi_araddr (npu_s3_axi_araddr  ),
2666:     .s05_axi_arlen  (npu_s3_axi_arlen   ),
2667:     .s05_axi_arsize (npu_s3_axi_arsize  ),
2668:     .s05_axi_arburst(npu_s3_axi_arburst ),
2669:     .s05_axi_arlock (npu_s3_axi_arlock  ),
2670:     .s05_axi_arcache(npu_s3_axi_arcache ),
2671:     .s05_axi_arprot (npu_s3_axi_arprot  ),
2672:     .s05_axi_arqos  (4'd0),
2673:     .s05_axi_aruser (),
2674:     .s05_axi_arvalid(npu_s3_axi_arvalid ),
2675:     .s05_axi_arready(npu_s3_axi_arready ),
2676:     .s05_axi_rid    (npu_s3_axi_rid     ),
2677:     .s05_axi_rdata  (npu_s3_axi_rdata   ),
2678:     .s05_axi_rresp  (npu_s3_axi_rresp   ),
2679:     .s05_axi_rlast  (npu_s3_axi_rlast   ),
2680:     .s05_axi_rvalid (npu_s3_axi_rvalid  ),
2681:     .s05_axi_rready (npu_s3_axi_rready  ),
2682:     .s05_axi_ruser  (),
2683: 
2684:     .s06_axi_awid(),
2685:     .s06_axi_awaddr(),
2686:     .s06_axi_awlen(),
2687:     .s06_axi_awsize(),
2688:     .s06_axi_awburst(),
2689:     .s06_axi_awlock(),
2690:     .s06_axi_awcache(),
2691:     .s06_axi_awprot(),
2692:     .s06_axi_awqos(),
2693:     .s06_axi_awuser(),
2694:     .s06_axi_awvalid(),
2695:     .s06_axi_awready(),
2696:     .s06_axi_wdata(),
2697:     .s06_axi_wstrb(),
2698:     .s06_axi_wlast(),
2699:     .s06_axi_wuser(),
2700:     .s06_axi_wvalid(),
2701:     .s06_axi_wready(),
2702:     .s06_axi_bid(),
2703:     .s06_axi_bresp(),
2704:     .s06_axi_buser(),
2705:     .s06_axi_bvalid(),
2706:     .s06_axi_bready(),
2707:     .s06_axi_arid   (npu_s4_axi_arid    ),
2708:     .s06_axi_araddr (npu_s4_axi_araddr  ),
2709:     .s06_axi_arlen  (npu_s4_axi_arlen   ),
2710:     .s06_axi_arsize (npu_s4_axi_arsize  ),
2711:     .s06_axi_arburst(npu_s4_axi_arburst ),
2712:     .s06_axi_arlock (npu_s4_axi_arlock  ),
2713:     .s06_axi_arcache(npu_s4_axi_arcache ),
2714:     .s06_axi_arprot (npu_s4_axi_arprot  ),
2715:     .s06_axi_arqos  (4'd0),
2716:     .s06_axi_aruser (),
2717:     .s06_axi_arvalid(npu_s4_axi_arvalid ),
2718:     .s06_axi_arready(npu_s4_axi_arready ),
2719:     .s06_axi_rid    (npu_s4_axi_rid     ),
2720:     .s06_axi_rdata  (npu_s4_axi_rdata   ),
2721:     .s06_axi_rresp  (npu_s4_axi_rresp   ),
2722:     .s06_axi_rlast  (npu_s4_axi_rlast   ),
2723:     .s06_axi_rvalid (npu_s4_axi_rvalid  ),
2724:     .s06_axi_rready (npu_s4_axi_rready  ),
2725:     .s06_axi_ruser  (),
2726: 
2727:     /*
2728:      * AXI master interface
2729:      */
2730:     // [WARB] M00 write parked: the arbiter drives the DDR write path now
2731:     .m00_axi_awid    (arb2x_awid                     ),
2732:     .m00_axi_awaddr  (arb2x_awaddr                   ),
2733:     .m00_axi_awlen   (arb2x_awlen                    ),
2734:     .m00_axi_awsize  (arb2x_awsize                   ),
2735:     .m00_axi_awburst (arb2x_awburst                  ),
2736:     .m00_axi_awlock  (arb2x_awlock                   ),
2737:     .m00_axi_awcache (arb2x_awcache                  ),
2738:     .m00_axi_awprot  (arb2x_awprot                   ),
2739:     .m00_axi_awqos   (arb2x_awqos                    ),
2740:     .m00_axi_awregion(),
2741:     .m00_axi_awuser  (arb2x_awuser                   ),
2742:     .m00_axi_awvalid (arb2x_awvalid                  ),
2743:     .m00_axi_awready (1'b0                           ),  // never granted (write retired)
2744:     .m00_axi_wdata   (arb2x_wdata                    ),
2745:     .m00_axi_wstrb   (arb2x_wstrb                    ),
2746:     .m00_axi_wlast   (arb2x_wlast                    ),
2747:     .m00_axi_wuser   (arb2x_wuser                    ),
2748:     .m00_axi_wvalid  (arb2x_wvalid                   ),
2749:     .m00_axi_wready  (1'b0                           ),
2750:     .m00_axi_bid     (                               ),
2751:     .m00_axi_bresp   (                               ),
2752:     .m00_axi_buser   (                               ),
2753:     .m00_axi_bvalid  (                               ),
2754:     .m00_axi_bready  (                               ),  // [WARB] crossbar out, unused: write retired
2755:     .m00_axi_arid    (ddr_axi_aruser_id              ),
2756:     .m00_axi_araddr  (ddr_axi_araddr                 ),
2757:     .m00_axi_arlen   (ddr_axi_arlen                  ),
2758:     .m00_axi_arsize  (ddr_axi_arsize                 ),
2759:     .m00_axi_arburst (ddr_axi_arburst                ),
2760:     .m00_axi_arlock  (ddr_axi_arlock                 ),
2761:     .m00_axi_arcache (ddr_axi_arcache                ),
2762:     .m00_axi_arprot  (ddr_axi_arprot                 ),
2763:     .m00_axi_arqos   (ddr_axi_arqos                  ),
2764:     .m00_axi_arregion(),
2765:     .m00_axi_aruser  (ddr_axi_aruser                 ),
2766:     .m00_axi_arvalid (ddr_axi_arvalid                ),
2767:     .m00_axi_arready (ddr_axi_arready_xbar           ),  // [ARFIX] ack at latch
2768:     .m00_axi_rid     (ddr_axi_rid                    ),
2769:     .m00_axi_rdata   (ddr_axi_rdata                  ),
2770:     .m00_axi_rresp(ddr_axi_rresp),
2771:     .m00_axi_rlast   (ddr_axi_rlast                  ),
2772:     .m00_axi_ruser   (ddr_axi_ruser                  ),
2773:     .m00_axi_rvalid(ddr_axi_rvalid),
2774:     .m00_axi_rready  (ddr_axi_rready                 ),
2775: 
2776: 
2777: 
2778: 
2779: 
2780:     .m01_axi_awid    (ovreg_axi_awid     ),
2781:     .m01_axi_awaddr  (ovreg_axi_awaddr   ),
2782:     .m01_axi_awlen   (ovreg_axi_awlen    ),
2783:     .m01_axi_awsize  (ovreg_axi_awsize   ),
2784:     .m01_axi_awburst (ovreg_axi_awburst  ),
2785:     .m01_axi_awlock  (ovreg_axi_awlock   ),
2786:     .m01_axi_awcache (ovreg_axi_awcache  ),
2787:     .m01_axi_awprot  (ovreg_axi_awprot   ),
2788:     .m01_axi_awqos   (ovreg_axi_awqos    ),
2789:     .m01_axi_awregion(ovreg_axi_awregion),
2790:     .m01_axi_awuser  (               ),
2791:     .m01_axi_awvalid (ovreg_axi_awvalid  ),
2792:     .m01_axi_awready (ovreg_axi_awready  ),
2793:     .m01_axi_wdata   (ovreg_axi_wdata    ),
2794:     .m01_axi_wstrb   (ovreg_axi_wstrb    ),
2795:     .m01_axi_wlast   (ovreg_axi_wlast    ),
2796:     .m01_axi_wuser   (               ),
2797:     .m01_axi_wvalid  (ovreg_axi_wvalid   ),
2798:     .m01_axi_wready  (ovreg_axi_wready   ),
2799:     .m01_axi_bid     (ovreg_axi_bid      ),
2800:     .m01_axi_bresp   (ovreg_axi_bresp    ),
2801:     .m01_axi_buser   (               ),
2802:     .m01_axi_bvalid  (ovreg_axi_bvalid   ),
2803:     .m01_axi_bready  (ovreg_axi_bready   ),
2804:     .m01_axi_arid    (ovreg_axi_arid     ),
2805:     .m01_axi_araddr  (ovreg_axi_araddr   ),
2806:     .m01_axi_arlen   (ovreg_axi_arlen    ),
2807:     .m01_axi_arsize  (ovreg_axi_arsize   ),
2808:     .m01_axi_arburst (ovreg_axi_arburst  ),
2809:     .m01_axi_arlock  (ovreg_axi_arlock   ),
2810:     .m01_axi_arcache (ovreg_axi_arcache  ),
2811:     .m01_axi_arprot  (ovreg_axi_arprot   ),
2812:     .m01_axi_arqos   (ovreg_axi_arqos    ),
2813:     .m01_axi_arregion(ovreg_axi_arregion ),
2814:     .m01_axi_aruser  (               ),
2815:     .m01_axi_arvalid (ovreg_axi_arvalid  ),
2816:     .m01_axi_arready (ovreg_axi_arready  ),
2817:     .m01_axi_rid     (ovreg_axi_rid      ),
2818:     .m01_axi_rdata   (ovreg_axi_rdata    ),
2819:     .m01_axi_rresp   (ovreg_axi_rresp    ),
2820:     .m01_axi_rlast   (ovreg_axi_rlast    ),
2821:     .m01_axi_ruser   (              ),
2822:     .m01_axi_rvalid  (ovreg_axi_rvalid   ),
2823:     .m01_axi_rready  (ovreg_axi_rready   ),
2824: 
2825: 
2826: 
2827:     .m02_axi_awid    (npu_reg_axi_awid    ),
2828:     .m02_axi_awaddr  (npu_reg_axi_awaddr  ),
2829:     .m02_axi_awlen   (npu_reg_axi_awlen   ),
2830:     .m02_axi_awsize  (npu_reg_axi_awsize  ),
2831:     .m02_axi_awburst (npu_reg_axi_awburst ),
2832:     .m02_axi_awlock  (npu_reg_axi_awlock  ),
2833:     .m02_axi_awcache (npu_reg_axi_awcache ),
2834:     .m02_axi_awprot  (npu_reg_axi_awprot  ),
2835:     .m02_axi_awqos   (npu_reg_axi_awqos   ),
2836:     .m02_axi_awregion(npu_reg_axi_awregion),
2837:     .m02_axi_awvalid (npu_reg_axi_awvalid ),
2838:     .m02_axi_awready (npu_reg_axi_awready ),
2839:     .m02_axi_awuser  (  ),
2840:     .m02_axi_wdata   (npu_reg_axi_wdata   ),
2841:     .m02_axi_wstrb   (npu_reg_axi_wstrb   ),
2842:     .m02_axi_wlast   (npu_reg_axi_wlast   ),
2843:     .m02_axi_wvalid  (npu_reg_axi_wvalid  ),
2844:     .m02_axi_wready  (npu_reg_axi_wready  ),
2845:     .m02_axi_wuser   (  ),
2846:     .m02_axi_bid     (npu_reg_axi_bid     ),
2847:     .m02_axi_bresp   (npu_reg_axi_bresp   ),
2848:     .m02_axi_bvalid  (npu_reg_axi_bvalid  ),
2849:     .m02_axi_bready  (npu_reg_axi_bready  ),
2850:     .m02_axi_buser   (  ),
2851:     .m02_axi_arid    (npu_reg_axi_arid    ),
2852:     .m02_axi_araddr  (npu_reg_axi_araddr  ),
2853:     .m02_axi_arlen   (npu_reg_axi_arlen   ),
2854:     .m02_axi_arsize  (npu_reg_axi_arsize  ),
2855:     .m02_axi_arburst (npu_reg_axi_arburst ),
2856:     .m02_axi_arlock  (npu_reg_axi_arlock  ),
2857:     .m02_axi_arcache (npu_reg_axi_arcache ),
2858:     .m02_axi_arprot  (npu_reg_axi_arprot  ),
2859:     .m02_axi_arqos   (npu_reg_axi_arqos   ),
2860:     .m02_axi_arregion(npu_reg_axi_arregion),
2861:     .m02_axi_arvalid (npu_reg_axi_arvalid ),
2862:     .m02_axi_arready (npu_reg_axi_arready ),
2863:     .m02_axi_aruser  (  ),
2864:     .m02_axi_rid     (npu_reg_axi_rid     ),
2865:     .m02_axi_rdata   (npu_reg_axi_rdata   ),
2866:     .m02_axi_rresp   (npu_reg_axi_rresp   ),
2867:     .m02_axi_rlast   (npu_reg_axi_rlast   ),
2868:     .m02_axi_ruser   (  ),
2869:     .m02_axi_rvalid  (npu_reg_axi_rvalid  ),
2870:     .m02_axi_rready  (npu_reg_axi_rready  )  
2871: 
2872: 
2873: 
2874: 
2875: );
2876: 
2877: // BEGIN ISOLATED V8 COOPERATIVE INTEGRATION
2878: wire [27:0] ddr3_ar_addr;
2879: wire ddr3_ar_ap;
2880: wire [3:0] ddr3_ar_id;
2881: wire [3:0] ddr3_ar_len;
2882: wire ddr3_ar_v;
2883: wire [27:0] ddr3_aw_addr;
2884: wire ddr3_aw_ap;
2885: wire [3:0] ddr3_aw_id;
2886: wire [3:0] ddr3_aw_len;
2887: wire ddr3_aw_v;
2888: wire ddr_axi_arready_xbar;
2889: wire [31:0] npu_reg_axi_araddr;
2890: wire [1:0] npu_reg_axi_arburst;
2891: wire [3:0] npu_reg_axi_arcache;
2892: wire [6:0] npu_reg_axi_arid;
2893: wire [7:0] npu_reg_axi_arlen;
2894: wire npu_reg_axi_arlock;
2895: wire [2:0] npu_reg_axi_arprot;
2896: wire [3:0] npu_reg_axi_arqos;
2897: wire [3:0] npu_reg_axi_arregion;
2898: wire [2:0] npu_reg_axi_arsize;
2899: wire npu_reg_axi_arvalid;
2900: wire [3:0] npu_reg_axi_awqos;
2901: wire [3:0] npu_reg_axi_awregion;
2902: wire npu_reg_axi_rready;
2903: wire [31:0] v8_c0_araddr;
2904: wire [2:0] v8_c0_arprot;
2905: wire v8_c0_arready;
2906: wire v8_c0_arvalid;
2907: wire [31:0] v8_c0_awaddr;
2908: wire [2:0] v8_c0_awprot;
2909: wire v8_c0_awready;
2910: wire v8_c0_awvalid;
2911: wire v8_c0_bready;
2912: wire [1:0] v8_c0_bresp;
2913: wire v8_c0_bvalid;
2914: wire [31:0] v8_c0_rdata;
2915: wire v8_c0_rready;
2916: wire [1:0] v8_c0_rresp;
2917: wire v8_c0_rvalid;
2918: wire [31:0] v8_c0_wdata;
2919: wire v8_c0_wready;
2920: wire [3:0] v8_c0_wstrb;
2921: wire v8_c0_wvalid;
2922: wire [31:0] v8_c1_araddr;
2923: wire [2:0] v8_c1_arprot;
2924: wire v8_c1_arready;
2925: wire v8_c1_arvalid;
2926: wire [31:0] v8_c1_awaddr;
2927: wire [2:0] v8_c1_awprot;
2928: wire v8_c1_awready;
2929: wire v8_c1_awvalid;
2930: wire v8_c1_bready;
2931: wire [1:0] v8_c1_bresp;
2932: wire v8_c1_bvalid;
2933: wire [31:0] v8_c1_rdata;
2934: wire v8_c1_rready;
2935: wire [1:0] v8_c1_rresp;
2936: wire v8_c1_rvalid;
2937: wire [31:0] v8_c1_wdata;
2938: wire v8_c1_wready;
2939: wire [3:0] v8_c1_wstrb;
2940: wire v8_c1_wvalid;
2941: wire v8_cap_admitted_sof;
2942: wire v8_cap_armed;
2943: wire [1:0] v8_cap_bank0_state;
2944: wire [1:0] v8_cap_bank1_state;
2945: wire v8_cap_capture_bank;
2946: wire v8_cap_capture_flush_o;
2947: wire v8_cap_capture_overflow_o;
2948: wire v8_cap_config_accept;
2949: wire [31:0] v8_cap_config_generation;
2950: wire v8_cap_config_ok;
2951: wire v8_cap_config_ready;
2952: wire v8_cap_config_reject;
2953: wire v8_cap_config_valid;
2954: wire v8_cap_engine_idle;
2955: wire v8_cap_epoch_start;
2956: wire [31:0] v8_cap_failed_count;
2957: wire v8_cap_frame_good_o;
2958: wire v8_cap_host_bank;
2959: wire [2:0] v8_cap_host_camera;
2960: wire [31:0] v8_cap_host_generation;
2961: wire [31:0] v8_cap_host_length;
2962: wire v8_cap_host_ready;
2963: wire v8_cap_host_release_accept;
2964: wire v8_cap_host_release_bank;
2965: wire [2:0] v8_cap_host_release_camera;
2966: wire [31:0] v8_cap_host_release_generation;
2967: wire v8_cap_host_release_ready;
2968: wire v8_cap_host_release_reject;
2969: wire [31:0] v8_cap_host_release_seq;
2970: wire [63:0] v8_cap_host_release_token;
2971: wire v8_cap_host_release_valid;
2972: wire [31:0] v8_cap_host_seq;
2973: wire [31:0] v8_cap_host_src_addr;
2974: wire [63:0] v8_cap_host_token;
2975: wire v8_cap_host_valid;
2976: wire v8_cap_input_bank;
2977: wire [2:0] v8_cap_input_camera;
2978: wire [31:0] v8_cap_input_generation;
2979: wire [31:0] v8_cap_input_length;
2980: wire v8_cap_input_raw_valid;
2981: wire v8_cap_input_ready;
2982: wire [31:0] v8_cap_input_seq;
2983: wire [31:0] v8_cap_input_src_addr;
2984: wire [63:0] v8_cap_input_token;
2985: wire v8_cap_input_valid;
2986: wire v8_cap_lease_block;
2987: wire v8_cap_protocol_fault;
2988: wire v8_cap_publish;
2989: wire [31:0] v8_cap_publish_seq;
2990: wire [31:0] v8_cap_published_count;
2991: wire [31:0] v8_cap_rejected_release_count;
2992: wire v8_cap_release_accept;
2993: wire v8_cap_release_bank;
2994: wire [2:0] v8_cap_release_camera;
2995: wire [31:0] v8_cap_release_generation;
2996: wire v8_cap_release_ready;
2997: wire v8_cap_release_reject;
2998: wire [31:0] v8_cap_release_seq;
2999: wire [63:0] v8_cap_release_token;
3000: wire v8_cap_release_valid;
3001: wire v8_cap_retired_error;
3002: wire v8_coop_arbiter_busy;
3003: wire v8_coop_arbiter_error;
3004: wire [4:0] v8_coop_arbiter_error_flags;
3005: wire [2:0] v8_coop_arbiter_owner;
3006: wire [1:0] v8_coop_bank0_state;
3007: wire [1:0] v8_coop_bank1_state;
3008: wire v8_coop_bridge_busy;
3009: wire v8_coop_bridge_cmd_error;
3010: wire v8_coop_bridge_done;
3011: wire v8_coop_bridge_error;
3012: wire v8_coop_busy;
3013: wire v8_coop_input_claim;
3014: wire v8_coop_input_reject;
3015: wire [31:0] v8_coop_src_release_addr;
3016: wire [7:0] v8_ddr_error_flags;
3017: wire v8_ddr_read_busy;
3018: wire v8_ddr_read_fifo_full;
3019: wire v8_ddr_write_busy;
3020: wire v8_ddr_write_fifo_empty;
3021: wire [4:0] v8_ddr_write_water_level;
3022: wire [31:0] v8_ep_araddr;
3023: wire [2:0] v8_ep_arprot;
3024: wire v8_ep_arready;
3025: wire v8_ep_arvalid;
3026: wire [31:0] v8_ep_awaddr;
3027: wire [2:0] v8_ep_awprot;
3028: wire v8_ep_awready;
3029: wire v8_ep_awvalid;
3030: wire v8_ep_bready;
3031: wire [1:0] v8_ep_bresp;
3032: wire v8_ep_bvalid;
3033: wire [31:0] v8_ep_rdata;
3034: wire v8_ep_rready;
3035: wire [1:0] v8_ep_rresp;
3036: wire v8_ep_rvalid;
3037: wire [31:0] v8_ep_wdata;
3038: wire v8_ep_wready;
3039: wire [3:0] v8_ep_wstrb;
3040: wire v8_ep_wvalid;
3041: wire [7:0] v8_read_arlen;
3042: wire [3:0] v8_read_arqos;
3043: wire [3:0] v8_read_arregion;
3044: wire [3:0] v8_write_awqos;
3045: wire [3:0] v8_write_awregion;
3046: 
3047: // Fixed downstream cam5 binding: 640x480 RGB565, no local filter on this branch.
3048: // Generation allocation and host exclusivity are required external protocol policy.
3049: assign npu_s0_axi_arlen = v8_read_arlen[3:0];
3050: assign ddr3_aw_ap = 1'b0;
3051: assign ddr3_ar_ap = 1'b0;
3052: assign ddr_axi_ruser = 2'b00;
3053: // Preserve the legacy debug aliases without retaining the removed FIFO/ID logic.
3054: assign ddr_axi_awaddr = arb_s_awaddr[27:0];
3055: assign ddr_axi_awlen = arb_s_awlen[3:0];
3056: assign ddr_axi_awvalid = arb_s_awvalid;
3057: assign ddr_axi_awuser_id = {3'b000, arb_s_awid};
3058: assign ddr_axi_awuser_ap = 1'b0;
3059: assign ddr_axi_awsize = arb_s_awsize;
3060: assign ddr_axi_awburst = arb_s_awburst;
3061: assign ddr_axi_awlock = arb_s_awlock;
3062: assign ddr_axi_awcache = arb_s_awcache;
3063: assign ddr_axi_awprot = arb_s_awprot;
3064: assign ddr_axi_awqos = v8_write_awqos;
3065: assign ddr_axi_wdata = arb_s_wdata;
3066: assign ddr_axi_wstrb = arb_s_wstrb;
3067: assign ddr_axi_wvalid = arb_s_wvalid;
3068: assign ddr_axi_wlast = arb_s_wlast;
3069: assign ddr_axi_bvalid = arb_s_bvalid;
3070: assign ddr_axi_bresp = arb_s_bresp;
3071: assign ddr_axi_bid = {3'b000, arb_s_bid};
3072: assign ddr_axi_bready = arb_s_bready;
3073: // synthesis translate_off
3074: initial begin
3075:     if (AXI_ID_LEN != 4 || AXI_ID_M_LEN != 7 || AXI_DATA_LEN != 128 || BURST_LEN != 16)
3076:         $fatal(1, "Whole candidate requires original 4/7-bit IDs, 128-bit data, 16-beat camera DMA");
3077: end
3078: always @(posedge axi_clk) if (!axi_rst) begin
3079:     if (npu_s0_axi_arvalid && v8_read_arlen[7:4] != 0)
3080:         $fatal(1, "Cooperative S02 read LEN cannot be truncated");
3081:     if (ddr_axi_arvalid && (ddr_axi_arlen > 15 || ddr_axi_arsize != 4 || ddr_axi_arburst != 1))
3082:         $fatal(1, "M00 read violates vendor DDR beat/burst contract");
3083:     if (v8_cap_release_valid && v8_coop_src_release_addr !=
3084:             (v8_cap_release_bank ? 32'h01a00000 : 32'h01800000))
3085:         $fatal(1, "Cooperative release address disagrees with capture bank identity");
3086: end
3087: // synthesis translate_on
3088: fpga_v8_capture_lease #(
3089:     .BANK0_ADDR(32'h01800000),
3090:     .BANK1_ADDR(32'h01a00000),
3091:     .RAW_LENGTH(614400),
3092:     .CAM_DATA_LEN(38400),
3093:     .FRAME_WIDTH(640),
3094:     .FRAME_HEIGHT(480),
3095:     .DATA_WIDTH(16),
3096:     .CAM_ID(4),
3097:     .HOST_REQUIRED(1)
3098: ) u_v8_capture_lease (
3099:     .clk(axi_clk),
3100:     .rst(axi_rst),
3101:     .config_valid(v8_cap_config_valid),
3102:     .config_ready(v8_cap_config_ready),
3103:     .config_generation(v8_cap_config_generation),
3104:     .config_accept(v8_cap_config_accept),
3105:     .config_reject(v8_cap_config_reject),
3106:     .epoch_start(v8_cap_epoch_start),
3107:     .armed(v8_cap_armed),
3108:     .config_ok(v8_cap_config_ok),
3109:     .engine_idle(v8_cap_engine_idle),
3110:     .capture_bank(v8_cap_capture_bank),
3111:     .admitted_sof(v8_cap_admitted_sof),
3112:     .publish(v8_cap_publish),
3113:     .publish_seq(v8_cap_publish_seq),
3114:     .retired_error(v8_cap_retired_error),
3115:     .lease_block(v8_cap_lease_block),
3116:     .bank0_state(v8_cap_bank0_state),
3117:     .bank1_state(v8_cap_bank1_state),
3118:     .protocol_fault(v8_cap_protocol_fault),
3119:     .input_valid(v8_cap_input_valid),
3120:     .input_ready(v8_cap_input_ready),
3121:     .input_raw_valid(v8_cap_input_raw_valid),
3122:     .input_src_addr(v8_cap_input_src_addr),
3123:     .input_length(v8_cap_input_length),
3124:     .input_seq(v8_cap_input_seq),
3125:     .input_generation(v8_cap_input_generation),
3126:     .input_camera(v8_cap_input_camera),
3127:     .input_bank(v8_cap_input_bank),
3128:     .input_token(v8_cap_input_token),
3129:     .release_valid(v8_cap_release_valid),
3130:     .release_ready(v8_cap_release_ready),
3131:     .release_camera(v8_cap_release_camera),
3132:     .release_bank(v8_cap_release_bank),
3133:     .release_seq(v8_cap_release_seq),
3134:     .release_generation(v8_cap_release_generation),
3135:     .release_token(v8_cap_release_token),
3136:     .release_accept(v8_cap_release_accept),
3137:     .release_reject(v8_cap_release_reject),
3138:     .host_valid(v8_cap_host_valid),
3139:     .host_ready(v8_cap_host_ready),
3140:     .host_src_addr(v8_cap_host_src_addr),
3141:     .host_length(v8_cap_host_length),
3142:     .host_seq(v8_cap_host_seq),
3143:     .host_generation(v8_cap_host_generation),
3144:     .host_camera(v8_cap_host_camera),
3145:     .host_bank(v8_cap_host_bank),
3146:     .host_token(v8_cap_host_token),
3147:     .host_release_valid(v8_cap_host_release_valid),
3148:     .host_release_ready(v8_cap_host_release_ready),
3149:     .host_release_camera(v8_cap_host_release_camera),
3150:     .host_release_bank(v8_cap_host_release_bank),
3151:     .host_release_seq(v8_cap_host_release_seq),
3152:     .host_release_generation(v8_cap_host_release_generation),
3153:     .host_release_token(v8_cap_host_release_token),
3154:     .host_release_accept(v8_cap_host_release_accept),
3155:     .host_release_reject(v8_cap_host_release_reject),
3156:     .published_count(v8_cap_published_count),
3157:     .failed_count(v8_cap_failed_count),
3158:     .rejected_release_count(v8_cap_rejected_release_count)
3159: );
3160: 
3161: fpga_v8_cooperative_core #(
3162:     .OUTPUT_BANK0_ADDR(32'h08000000),
3163:     .OUTPUT_BANK1_ADDR(32'h08200000),
3164:     .DDR_ADDRESS_LIMIT(32'h10000000),
3165:     .AXI_ID(4'd1)
3166: ) u_v8_cooperative_core (
3167:     .core_clk(axi_clk),
3168:     .rst_n(~axi_rst),
3169:     .input_valid(v8_cap_input_valid),
3170:     .input_ready(v8_cap_input_ready),
3171:     .input_raw_valid(v8_cap_input_raw_valid),
3172:     .input_src_addr(v8_cap_input_src_addr),
3173:     .input_source_seq(v8_cap_input_seq),
3174:     .input_generation(v8_cap_input_generation),
3175:     .input_camera(v8_cap_input_camera),
3176:     .input_camera_bank(v8_cap_input_bank),
3177:     .input_lease_token(v8_cap_input_token),
3178:     .input_claim(v8_coop_input_claim),
3179:     .input_reject(v8_coop_input_reject),
3180:     .src_release_valid(v8_cap_release_valid),
3181:     .src_release_ready(v8_cap_release_ready),
3182:     .src_release_addr(v8_coop_src_release_addr),
3183:     .src_release_seq(v8_cap_release_seq),
3184:     .src_release_generation(v8_cap_release_generation),
3185:     .src_release_camera(v8_cap_release_camera),
3186:     .src_release_camera_bank(v8_cap_release_bank),
3187:     .src_release_token(v8_cap_release_token),
3188:     .busy(v8_coop_busy),
3189:     .bank0_state(v8_coop_bank0_state),
3190:     .bank1_state(v8_coop_bank1_state),
3191:     .bridge_busy(v8_coop_bridge_busy),
3192:     .bridge_done(v8_coop_bridge_done),
3193:     .bridge_error(v8_coop_bridge_error),
3194:     .bridge_cmd_error(v8_coop_bridge_cmd_error),
3195:     .arbiter_busy(v8_coop_arbiter_busy),
3196:     .arbiter_owner(v8_coop_arbiter_owner),
3197:     .arbiter_error(v8_coop_arbiter_error),
3198:     .arbiter_error_flags(v8_coop_arbiter_error_flags),
3199:     .s_axil_awaddr(v8_c0_awaddr),
3200:     .s_axil_awprot(v8_c0_awprot),
3201:     .s_axil_awvalid(v8_c0_awvalid),
3202:     .s_axil_awready(v8_c0_awready),
3203:     .s_axil_wdata(v8_c0_wdata),
3204:     .s_axil_wstrb(v8_c0_wstrb),
3205:     .s_axil_wvalid(v8_c0_wvalid),
3206:     .s_axil_wready(v8_c0_wready),
3207:     .s_axil_bresp(v8_c0_bresp),
3208:     .s_axil_bvalid(v8_c0_bvalid),
3209:     .s_axil_bready(v8_c0_bready),
3210:     .s_axil_araddr(v8_c0_araddr),
3211:     .s_axil_arprot(v8_c0_arprot),
3212:     .s_axil_arvalid(v8_c0_arvalid),
3213:     .s_axil_arready(v8_c0_arready),
3214:     .s_axil_rdata(v8_c0_rdata),
3215:     .s_axil_rresp(v8_c0_rresp),
3216:     .s_axil_rvalid(v8_c0_rvalid),
3217:     .s_axil_rready(v8_c0_rready),
3218:     .camera_awid({cam6_axi_awid, cam5_axi_awid, cam4_axi_awid, cam3_axi_awid, cam2_axi_awid, ov5640_axi_awid}),
3219:     .camera_awaddr({cam6_axi_awaddr, cam5_axi_awaddr, cam4_axi_awaddr, cam3_axi_awaddr, cam2_axi_awaddr, ov5640_axi_awaddr}),
3220:     .camera_awlen({{4'b0000,cam6_axi_awlen}, {4'b0000,cam5_axi_awlen}, cam4_axi_awlen, cam3_axi_awlen, {4'b0000,cam2_axi_awlen}, {4'b0000,ov5640_axi_awlen}}),
3221:     .camera_awsize({cam6_axi_awsize, cam5_axi_awsize, cam4_axi_awsize, cam3_axi_awsize, cam2_axi_awsize, ov5640_axi_awsize}),
3222:     .camera_awburst({cam6_axi_awburst, cam5_axi_awburst, cam4_axi_awburst, cam3_axi_awburst, cam2_axi_awburst, ov5640_axi_awburst}),
3223:     .camera_awlock({cam6_axi_awlock, cam5_axi_awlock, cam4_axi_awlock, cam3_axi_awlock, cam2_axi_awlock, ov5640_axi_awlock}),
3224:     .camera_awcache({cam6_axi_awcache, cam5_axi_awcache, cam4_axi_awcache, cam3_axi_awcache, cam2_axi_awcache, ov5640_axi_awcache}),
3225:     .camera_awprot({cam6_axi_awprot, cam5_axi_awprot, cam4_axi_awprot, cam3_axi_awprot, cam2_axi_awprot, ov5640_axi_awprot}),
3226:     .camera_awqos({4'b0000, 4'b0000, 4'b0000, 4'b0000, 4'b0000, 4'b0000}),
3227:     .camera_awregion({4'b0000, 4'b0000, 4'b0000, 4'b0000, 4'b0000, 4'b0000}),
3228:     .camera_awvalid({cam6_axi_awvalid, cam5_axi_awvalid, cam4_axi_awvalid, cam3_axi_awvalid, cam2_axi_awvalid, ov5640_axi_awvalid}),
3229:     .camera_awready({cam6_axi_awready, cam5_axi_awready, cam4_axi_awready, cam3_axi_awready, cam2_axi_awready, ov5640_axi_awready}),
3230:     .camera_wdata({cam6_axi_wdata, cam5_axi_wdata, cam4_axi_wdata, cam3_axi_wdata, cam2_axi_wdata, ov5640_axi_wdata}),
3231:     .camera_wstrb({cam6_axi_wstrb, cam5_axi_wstrb, cam4_axi_wstrb, cam3_axi_wstrb, cam2_axi_wstrb, ov5640_axi_wstrb}),
3232:     .camera_wlast({cam6_axi_wlast, cam5_axi_wlast, cam4_axi_wlast, cam3_axi_wlast, cam2_axi_wlast, ov5640_axi_wlast}),
3233:     .camera_wvalid({cam6_axi_wvalid, cam5_axi_wvalid, cam4_axi_wvalid, cam3_axi_wvalid, cam2_axi_wvalid, ov5640_axi_wvalid}),
3234:     .camera_wready({cam6_axi_wready, cam5_axi_wready, cam4_axi_wready, cam3_axi_wready, cam2_axi_wready, ov5640_axi_wready}),
3235:     .camera_bid({cam6_axi_bid, cam5_axi_bid, cam4_axi_bid, cam3_axi_bid, cam2_axi_bid, ov5640_axi_bid}),
3236:     .camera_bresp({cam6_axi_bresp, cam5_axi_bresp, cam4_axi_bresp, cam3_axi_bresp, cam2_axi_bresp, ov5640_axi_bresp}),
3237:     .camera_bvalid({cam6_axi_bvalid, cam5_axi_bvalid, cam4_axi_bvalid, cam3_axi_bvalid, cam2_axi_bvalid, ov5640_axi_bvalid}),
3238:     .camera_bready({cam6_axi_bready, cam5_axi_bready, cam4_axi_bready, cam3_axi_bready, cam2_axi_bready, ov5640_axi_bready}),
3239:     .m_axi_read_arid(npu_s0_axi_arid),
3240:     .m_axi_read_araddr(npu_s0_axi_araddr),
3241:     .m_axi_read_arlen(v8_read_arlen),
3242:     .m_axi_read_arsize(npu_s0_axi_arsize),
3243:     .m_axi_read_arburst(npu_s0_axi_arburst),
3244:     .m_axi_read_arlock(npu_s0_axi_arlock),
3245:     .m_axi_read_arcache(npu_s0_axi_arcache),
3246:     .m_axi_read_arprot(npu_s0_axi_arprot),
3247:     .m_axi_read_arqos(v8_read_arqos),
3248:     .m_axi_read_arregion(v8_read_arregion),
3249:     .m_axi_read_arvalid(npu_s0_axi_arvalid),
3250:     .m_axi_read_arready(npu_s0_axi_arready),
3251:     .m_axi_read_rid(npu_s0_axi_rid),
3252:     .m_axi_read_rdata(npu_s0_axi_rdata),
3253:     .m_axi_read_rresp(npu_s0_axi_rresp),
3254:     .m_axi_read_rlast(npu_s0_axi_rlast),
3255:     .m_axi_read_rvalid(npu_s0_axi_rvalid),
3256:     .m_axi_read_rready(npu_s0_axi_rready),
3257:     .m_axi_write_awid(arb_s_awid),
3258:     .m_axi_write_awaddr(arb_s_awaddr),
3259:     .m_axi_write_awlen(arb_s_awlen),
3260:     .m_axi_write_awsize(arb_s_awsize),
3261:     .m_axi_write_awburst(arb_s_awburst),
3262:     .m_axi_write_awlock(arb_s_awlock),
3263:     .m_axi_write_awcache(arb_s_awcache),
3264:     .m_axi_write_awprot(arb_s_awprot),
3265:     .m_axi_write_awqos(v8_write_awqos),
3266:     .m_axi_write_awregion(v8_write_awregion),
3267:     .m_axi_write_awvalid(arb_s_awvalid),
3268:     .m_axi_write_awready(arb_s_awready),
3269:     .m_axi_write_wdata(arb_s_wdata),
3270:     .m_axi_write_wstrb(arb_s_wstrb),
3271:     .m_axi_write_wlast(arb_s_wlast),
3272:     .m_axi_write_wvalid(arb_s_wvalid),
3273:     .m_axi_write_wready(arb_s_wready),
3274:     .m_axi_write_bid(arb_s_bid),
3275:     .m_axi_write_bresp(arb_s_bresp),
3276:     .m_axi_write_bvalid(arb_s_bvalid),
3277:     .m_axi_write_bready(arb_s_bready)
3278: );
3279: 
3280: fpga_v8_capture_control_axil_arm_v2 #(
3281:     .LOCAL_BASE(32'h00000100)
3282: ) u_v8_capture_control (
3283:     .clk(axi_clk),
3284:     .rst_n(~axi_rst),
3285:     .config_valid(v8_cap_config_valid),
3286:     .config_ready(v8_cap_config_ready),
3287:     .config_generation(v8_cap_config_generation),
3288:     .config_accept(v8_cap_config_accept),
3289:     .config_reject(v8_cap_config_reject),
3290:     .epoch_start(v8_cap_epoch_start),
3291:     .armed(v8_cap_armed),
3292:     .config_ok(v8_cap_config_ok),
3293:     .protocol_fault(v8_cap_protocol_fault),
3294:     .bank0_state(v8_cap_bank0_state),
3295:     .bank1_state(v8_cap_bank1_state),
3296:     .host_valid(v8_cap_host_valid),
3297:     .host_ready(v8_cap_host_ready),
3298:     .host_src_addr(v8_cap_host_src_addr),
3299:     .host_length(v8_cap_host_length),
3300:     .host_seq(v8_cap_host_seq),
3301:     .host_generation(v8_cap_host_generation),
3302:     .host_camera(v8_cap_host_camera),
3303:     .host_bank(v8_cap_host_bank),
3304:     .host_token(v8_cap_host_token),
3305:     .host_release_valid(v8_cap_host_release_valid),
3306:     .host_release_ready(v8_cap_host_release_ready),
3307:     .host_release_camera(v8_cap_host_release_camera),
3308:     .host_release_bank(v8_cap_host_release_bank),
3309:     .host_release_seq(v8_cap_host_release_seq),
3310:     .host_release_generation(v8_cap_host_release_generation),
3311:     .host_release_token(v8_cap_host_release_token),
3312:     .host_release_accept(v8_cap_host_release_accept),
3313:     .host_release_reject(v8_cap_host_release_reject),
3314:     .published_count(v8_cap_published_count),
3315:     .failed_count(v8_cap_failed_count),
3316:     .rejected_release_count(v8_cap_rejected_release_count),
3317:     .s_axil_awaddr(v8_c1_awaddr),
3318:     .s_axil_awprot(v8_c1_awprot),
3319:     .s_axil_awvalid(v8_c1_awvalid),
3320:     .s_axil_awready(v8_c1_awready),
3321:     .s_axil_wdata(v8_c1_wdata),
3322:     .s_axil_wstrb(v8_c1_wstrb),
3323:     .s_axil_wvalid(v8_c1_wvalid),
3324:     .s_axil_wready(v8_c1_wready),
3325:     .s_axil_bresp(v8_c1_bresp),
3326:     .s_axil_bvalid(v8_c1_bvalid),
3327:     .s_axil_bready(v8_c1_bready),
3328:     .s_axil_araddr(v8_c1_araddr),
3329:     .s_axil_arprot(v8_c1_arprot),
3330:     .s_axil_arvalid(v8_c1_arvalid),
3331:     .s_axil_arready(v8_c1_arready),
3332:     .s_axil_rdata(v8_c1_rdata),
3333:     .s_axil_rresp(v8_c1_rresp),
3334:     .s_axil_rvalid(v8_c1_rvalid),
3335:     .s_axil_rready(v8_c1_rready)
3336: );
3337: 
3338: fpga_v8_coop_axil_router u_v8_axil_router (
3339:     .clk(axi_clk),
3340:     .rst_n(~axi_rst),
3341:     .s_axil_awaddr(v8_ep_awaddr),
3342:     .s_axil_awprot(v8_ep_awprot),
3343:     .s_axil_awvalid(v8_ep_awvalid),
3344:     .s_axil_awready(v8_ep_awready),
3345:     .s_axil_wdata(v8_ep_wdata),
3346:     .s_axil_wstrb(v8_ep_wstrb),
3347:     .s_axil_wvalid(v8_ep_wvalid),
3348:     .s_axil_wready(v8_ep_wready),
3349:     .s_axil_bresp(v8_ep_bresp),
3350:     .s_axil_bvalid(v8_ep_bvalid),
3351:     .s_axil_bready(v8_ep_bready),
3352:     .s_axil_araddr(v8_ep_araddr),
3353:     .s_axil_arprot(v8_ep_arprot),
3354:     .s_axil_arvalid(v8_ep_arvalid),
3355:     .s_axil_arready(v8_ep_arready),
3356:     .s_axil_rdata(v8_ep_rdata),
3357:     .s_axil_rresp(v8_ep_rresp),
3358:     .s_axil_rvalid(v8_ep_rvalid),
3359:     .s_axil_rready(v8_ep_rready),
3360:     .m0_axil_awaddr(v8_c0_awaddr),
3361:     .m0_axil_awprot(v8_c0_awprot),
3362:     .m0_axil_awvalid(v8_c0_awvalid),
3363:     .m0_axil_awready(v8_c0_awready),
3364:     .m0_axil_wdata(v8_c0_wdata),
3365:     .m0_axil_wstrb(v8_c0_wstrb),
3366:     .m0_axil_wvalid(v8_c0_wvalid),
3367:     .m0_axil_wready(v8_c0_wready),
3368:     .m0_axil_bresp(v8_c0_bresp),
3369:     .m0_axil_bvalid(v8_c0_bvalid),
3370:     .m0_axil_bready(v8_c0_bready),
3371:     .m0_axil_araddr(v8_c0_araddr),
3372:     .m0_axil_arprot(v8_c0_arprot),
3373:     .m0_axil_arvalid(v8_c0_arvalid),
3374:     .m0_axil_arready(v8_c0_arready),
3375:     .m0_axil_rdata(v8_c0_rdata),
3376:     .m0_axil_rresp(v8_c0_rresp),
3377:     .m0_axil_rvalid(v8_c0_rvalid),
3378:     .m0_axil_rready(v8_c0_rready),
3379:     .m1_axil_awaddr(v8_c1_awaddr),
3380:     .m1_axil_awprot(v8_c1_awprot),
3381:     .m1_axil_awvalid(v8_c1_awvalid),
3382:     .m1_axil_awready(v8_c1_awready),
3383:     .m1_axil_wdata(v8_c1_wdata),
3384:     .m1_axil_wstrb(v8_c1_wstrb),
3385:     .m1_axil_wvalid(v8_c1_wvalid),
3386:     .m1_axil_wready(v8_c1_wready),
3387:     .m1_axil_bresp(v8_c1_bresp),
3388:     .m1_axil_bvalid(v8_c1_bvalid),
3389:     .m1_axil_bready(v8_c1_bready),
3390:     .m1_axil_araddr(v8_c1_araddr),
3391:     .m1_axil_arprot(v8_c1_arprot),
3392:     .m1_axil_arvalid(v8_c1_arvalid),
3393:     .m1_axil_arready(v8_c1_arready),
3394:     .m1_axil_rdata(v8_c1_rdata),
3395:     .m1_axil_rresp(v8_c1_rresp),
3396:     .m1_axil_rvalid(v8_c1_rvalid),
3397:     .m1_axil_rready(v8_c1_rready)
3398: );
3399: 
3400: fpga_v8_coop_axi128_endpoint #(
3401:     .ID_WIDTH(AXI_ID_M_LEN),
3402:     .BASE_ADDR(32'h40010000),
3403:     .WINDOW_BYTES(32'h00001000)
3404: ) u_v8_axi128_endpoint (
3405:     .clk(axi_clk),
3406:     .rst_n(~axi_rst),
3407:     .s_axi_awid(npu_reg_axi_awid),
3408:     .s_axi_awaddr(npu_reg_axi_awaddr),
3409:     .s_axi_awlen(npu_reg_axi_awlen),
3410:     .s_axi_awsize(npu_reg_axi_awsize),
3411:     .s_axi_awburst(npu_reg_axi_awburst),
3412:     .s_axi_awlock(npu_reg_axi_awlock),
3413:     .s_axi_awcache(npu_reg_axi_awcache),
3414:     .s_axi_awprot(npu_reg_axi_awprot),
3415:     .s_axi_awqos(npu_reg_axi_awqos),
3416:     .s_axi_awregion(npu_reg_axi_awregion),
3417:     .s_axi_awvalid(npu_reg_axi_awvalid),
3418:     .s_axi_awready(npu_reg_axi_awready),
3419:     .s_axi_wdata(npu_reg_axi_wdata),
3420:     .s_axi_wstrb(npu_reg_axi_wstrb),
3421:     .s_axi_wlast(npu_reg_axi_wlast),
3422:     .s_axi_wvalid(npu_reg_axi_wvalid),
3423:     .s_axi_wready(npu_reg_axi_wready),
3424:     .s_axi_bid(npu_reg_axi_bid),
3425:     .s_axi_bresp(npu_reg_axi_bresp),
3426:     .s_axi_bvalid(npu_reg_axi_bvalid),
3427:     .s_axi_bready(npu_reg_axi_bready),
3428:     .s_axi_arid(npu_reg_axi_arid),
3429:     .s_axi_araddr(npu_reg_axi_araddr),
3430:     .s_axi_arlen(npu_reg_axi_arlen),
3431:     .s_axi_arsize(npu_reg_axi_arsize),
3432:     .s_axi_arburst(npu_reg_axi_arburst),
3433:     .s_axi_arlock(npu_reg_axi_arlock),
3434:     .s_axi_arcache(npu_reg_axi_arcache),
3435:     .s_axi_arprot(npu_reg_axi_arprot),
3436:     .s_axi_arqos(npu_reg_axi_arqos),
3437:     .s_axi_arregion(npu_reg_axi_arregion),
3438:     .s_axi_arvalid(npu_reg_axi_arvalid),
3439:     .s_axi_arready(npu_reg_axi_arready),
3440:     .s_axi_rid(npu_reg_axi_rid),
3441:     .s_axi_rdata(npu_reg_axi_rdata),
3442:     .s_axi_rresp(npu_reg_axi_rresp),
3443:     .s_axi_rlast(npu_reg_axi_rlast),
3444:     .s_axi_rvalid(npu_reg_axi_rvalid),
3445:     .s_axi_rready(npu_reg_axi_rready),
3446:     .m_axil_awaddr(v8_ep_awaddr),
3447:     .m_axil_awprot(v8_ep_awprot),
3448:     .m_axil_awvalid(v8_ep_awvalid),
3449:     .m_axil_awready(v8_ep_awready),
3450:     .m_axil_wdata(v8_ep_wdata),
3451:     .m_axil_wstrb(v8_ep_wstrb),
3452:     .m_axil_wvalid(v8_ep_wvalid),
3453:     .m_axil_wready(v8_ep_wready),
3454:     .m_axil_bresp(v8_ep_bresp),
3455:     .m_axil_bvalid(v8_ep_bvalid),
3456:     .m_axil_bready(v8_ep_bready),
3457:     .m_axil_araddr(v8_ep_araddr),
3458:     .m_axil_arprot(v8_ep_arprot),
3459:     .m_axil_arvalid(v8_ep_arvalid),
3460:     .m_axil_arready(v8_ep_arready),
3461:     .m_axil_rdata(v8_ep_rdata),
3462:     .m_axil_rresp(v8_ep_rresp),
3463:     .m_axil_rvalid(v8_ep_rvalid),
3464:     .m_axil_rready(v8_ep_rready)
3465: );
3466: 
3467: fpga_v8_ddr_adapter #(
3468:     .DDR_ADDRESS_LIMIT(32'h10000000)
3469: ) u_v8_ddr_adapter (
3470:     .clk(axi_clk),
3471:     .rst_n(~axi_rst),
3472:     .s_awid(arb_s_awid),
3473:     .s_awaddr(arb_s_awaddr),
3474:     .s_awlen(arb_s_awlen),
3475:     .s_awsize(arb_s_awsize),
3476:     .s_awburst(arb_s_awburst),
3477:     .s_awvalid(arb_s_awvalid),
3478:     .s_awready(arb_s_awready),
3479:     .s_wdata(arb_s_wdata),
3480:     .s_wstrb(arb_s_wstrb),
3481:     .s_wlast(arb_s_wlast),
3482:     .s_wvalid(arb_s_wvalid),
3483:     .s_wready(arb_s_wready),
3484:     .s_bid(arb_s_bid),
3485:     .s_bresp(arb_s_bresp),
3486:     .s_bvalid(arb_s_bvalid),
3487:     .s_bready(arb_s_bready),
3488:     .s_arid(ddr_axi_aruser_id),
3489:     .s_araddr(ddr_axi_araddr),
3490:     .s_arlen(ddr_axi_arlen),
3491:     .s_arsize(ddr_axi_arsize),
3492:     .s_arburst(ddr_axi_arburst),
3493:     .s_arvalid(ddr_axi_arvalid),
3494:     .s_arready(ddr_axi_arready_xbar),
3495:     .s_rid(ddr_axi_rid),
3496:     .s_rdata(ddr_axi_rdata),
3497:     .s_rresp(ddr_axi_rresp),
3498:     .s_rlast(ddr_axi_rlast),
3499:     .s_rvalid(ddr_axi_rvalid),
3500:     .s_rready(ddr_axi_rready),
3501:     .v_awid(ddr3_aw_id),
3502:     .v_awaddr(ddr3_aw_addr),
3503:     .v_awlen(ddr3_aw_len),
3504:     .v_awvalid(ddr3_aw_v),
3505:     .v_awready(ddr_axi_awready),
3506:     .v_wdata(ddr_axi_wdata_ddr3),
3507:     .v_wstrb(ddr_axi_wstrb_ddr3),
3508:     .v_wready(ddr_axi_wready_ddr3),
3509:     .v_wlast(ddr_axi_wusero_last_ddr3),
3510:     .v_wid(ddr_axi_wusero_id),
3511:     .v_arid(ddr3_ar_id),
3512:     .v_araddr(ddr3_ar_addr),
3513:     .v_arlen(ddr3_ar_len),
3514:     .v_arvalid(ddr3_ar_v),
3515:     .v_arready(ddr_axi_arready),
3516:     .v_rid(ddr_axi_rid_ddr3),
3517:     .v_rdata(ddr_axi_rdata_ddr3),
3518:     .v_rlast(ddr_axi_rlast_ddr3),
3519:     .v_rvalid(ddr_axi_rvalid_ddr3),
3520:     .error_flags(v8_ddr_error_flags),
3521:     .write_water_level(v8_ddr_write_water_level),
3522:     .write_fifo_full(ddr_axi_fifo_full),
3523:     .write_fifo_empty(v8_ddr_write_fifo_empty),
3524:     .read_fifo_full(v8_ddr_read_fifo_full),
3525:     .read_fifo_empty(ddr_axi_fifo_empty),
3526:     .write_busy(v8_ddr_write_busy),
3527:     .read_busy(v8_ddr_read_busy)
3528: );
3529: 
3530: // END ISOLATED V8 COOPERATIVE INTEGRATION
3531: 
3532: endmodule
