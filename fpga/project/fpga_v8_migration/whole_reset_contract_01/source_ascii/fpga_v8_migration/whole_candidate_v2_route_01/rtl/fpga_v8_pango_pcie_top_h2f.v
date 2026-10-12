1: 
2: //////////////////////////////////////////////////////////////////////////////
3: //
4: // Copyright (c) 2019 PANGO MICROSYSTEMS, INC
5: // ALL RIGHTS REVERVED.
6: //
7: // THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
8: // IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
9: // PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
10: //
11: //////////////////////////////////////////////////////////////////////////////
12: //
13: // Library:
14: // Filename:pango_pcie_top.v
15: //////////////////////////////////////////////////////////////////////////////
16: module fpga_v8_pango_pcie_top_h2f #(
17:     parameter ADDR_WIDTH = 12,
18:               MSI_NUM = 5
19: )(
20:     input                       button_rst_n    ,
21:     input                       perst_n         ,
22:     //UART interface
23:     output  wire                txd             ,
24:     input                       rxd             ,
25:     //clk and rst
26:     input                       ref_clk_n       ,      //100 Mhz
27:     input                       ref_clk_p       ,      //100 Mhz
28:     //diff signals
29: 
30:     input           [1:0]       rxn             ,
31:     input           [1:0]       rxp             ,
32:     output  wire    [1:0]       txn             ,
33:     output  wire    [1:0]       txp             ,
34: 
35:     //LED signals
36:     output reg                  ref_led         ,
37:     output reg                  pclk_led        ,
38:     output wire                 smlh_link_up    ,
39:     output wire                 rdlh_link_up    ,
40: 
41:     ///MSI
42:     input  [MSI_NUM-2 : 0]        i_msi_req  ,
43:     output [MSI_NUM-2 : 0]        o_msi_grant,
44:     // //*********************************************************************  
45:     output  wire     [31:0]           fpga_ddr3_addr         ,  //ddr3\xe8\xa6\x81\xe6\x93\x8d\xe4\xbd\x9c\xe7\x9a\x84\xe7\x9c\x9f\xe5\xae\x9e\xe5\x9c\xb0\xe5\x9d\x80
46:     output  wire     [31:0]           fpga_ddr3_length       ,  //\xe8\xa6\x81\xe6\x93\x8d\xe4\xbd\x9c\xe7\x9a\x84\xe9\x95\xbf\xe5\xba\xa6
47:     output  wire     [31:0]           fpga_ddr3_total_length ,
48:     //FPGA --> CPU
49:     input                             fpga_tx_done           ,             //empty\xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf \xe5\xb7\xb2\xe7\xbb\x8f\xe6\x8a\x8a\xe6\x95\xb0\xe6\x8d\xae\xe4\xbb\x8eFIFO\xe6\x90\xac\xe8\xbf\x90\xe5\x88\xb0CPU\xe7\x9a\x84LPDDR4
50:     output                            mwr_tx_busy            ,             //\xe8\xaf\xa5\xe4\xbf\xa1\xe5\x8f\xb7\xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf \xe9\x9c\x80\xe8\xa6\x81\xe6\x8a\x8a\xe6\x95\xb0\xe6\x8d\xae\xe4\xbb\x8eFIFO\xe6\x90\xac\xe8\xbf\x90\xe8\xbf\x9b\xe6\x9d\xa5    
51:     input                             fpga_data_ready        ,           // \xe5\xa4\x96\xe9\x83\xa8\xe6\x95\xb0\xe6\x8d\xae\xe5\xb0\xb1\xe7\xbb\xaa\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x88DDR3 \xe5\x86\x99\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe9\x80\x9a\xe7\x9f\xa5 FPGA \xe5\x8f\xaf\xe4\xbb\xa5\xe5\xbc\x80\xe5\xa7\x8b\xe8\xaf\xbb\xe5\x8f\x96\xe6\x95\xb0\xe6\x8d\xae\xef\xbc\x89
52:     output                            fpga_tx_clk_en         ,           //\xe6\x95\xb0\xe6\x8d\xae\xe8\xbf\x9b\xe6\x9d\xa5\xe7\x9a\x84\xe4\xbd\xbf\xe8\x83\xbd 
53:     output        [ADDR_WIDTH-1:0]    fpga_tx_addr           ,           //\xe6\xb2\xa1\xe7\x94\xa8
54:     input         [127:0]             fpga_tx_data           ,           //\xe8\xbf\x9b\xe6\x9d\xa5\xe7\x9a\x84\xe6\x95\xb0\xe6\x8d\xae
55: 
56:     //CPU --> FPGA
57:     input                             fpga_rx_done           ,             //empty\xe4\xb8\x8a\xe5\x8d\x87\xe6\xb2\xbf \xe5\xb7\xb2\xe7\xbb\x8f\xe6\x8a\x8a\xe6\x95\xb0\xe6\x8d\xae\xe4\xbb\x8eFIFO\xe6\x90\xac\xe8\xbf\x90\xe5\x88\xb0FPGA\xe7\x9a\x84DDR3
58:     output                            mrd_rx_busy            ,              //\xe8\xaf\xa5\xe4\xbf\xa1\xe5\x8f\xb7\xe4\xb8\x8b\xe9\x99\x8d\xe6\xb2\xbf \xe5\x8f\xaf\xe4\xbb\xa5\xe6\x8a\x8a\xe6\x95\xb0\xe6\x8d\xae\xe4\xbb\x8eRAM\xe6\x90\xac\xe8\xbf\x90\xe5\x88\xb0FIFO
59:     input                             fpga_rx_clk_en         ,           //\xe4\xbb\x8eram\xe6\x90\xac\xe8\xbf\x90\xe6\x95\xb0\xe6\x8d\xae\xe4\xbd\xbf\xe8\x83\xbd
60:     input         [ADDR_WIDTH-1:0]    fpga_rx_addr           ,           //\xe8\xaf\xbb\xe5\x8f\x96ram\xe7\x9a\x84\xe5\x9c\xb0\xe5\x9d\x80
61:     output        [127:0]             fpga_rx_data           ,           //\xe4\xbb\x8eram\xe4\xb8\xad\xe8\xaf\xbb\xe5\x88\xb0\xe7\x9a\x84\xe6\x95\xb0\xe6\x8d\xae
62: 
63:     output                            fifo_pcie_clk          ,
64:     output                            fifo_pcie_rst
65: 
66: );
67: 
68: assign fifo_pcie_clk = pclk_div2;
69: assign fifo_pcie_rst = ~core_rst_n;
70: 
71: localparam  DEVICE_TYPE   = 3'b000;//@IPC enum 3'b000,3'b001,3'b100
72: 
73: localparam AXIS_SLAVE_NUM = 3      ;  //@IPC enum 1 2 3
74: 
75: 
76: //TEST UNIT MODE SIGNALS
77: wire            pcie_cfg_ctrl_en        ;
78: wire            axis_master_tready_cfg  ;
79: 
80: wire            cfg_axis_slave0_tvalid  ;
81: wire    [127:0] cfg_axis_slave0_tdata   ;
82: wire            cfg_axis_slave0_tlast   ;
83: wire            cfg_axis_slave0_tuser   ;
84: 
85: //for mux
86: wire            axis_master_tready_mem  ;
87: wire            axis_master_tvalid_mem  ;
88: wire    [127:0] axis_master_tdata_mem   ;
89: wire    [3:0]   axis_master_tkeep_mem   ;
90: wire            axis_master_tlast_mem   ;
91: wire    [7:0]   axis_master_tuser_mem   ;
92: 
93: wire            cross_4kb_boundary      ;
94: 
95: wire            dma_axis_slave0_tvalid  ;
96: wire    [127:0] dma_axis_slave0_tdata   ;
97: wire            dma_axis_slave0_tlast   ;
98: wire            dma_axis_slave0_tuser   ;
99: 
100: //RESET DEBOUNCE and SYNC
101: wire            sync_button_rst_n       ;
102: wire            s_pclk_rstn             ;
103: wire            s_pclk_div2_rstn        ;
104: 
105: //********************** internal signal
106: //clk and rst
107: wire            pclk_div2               ;
108: wire            pclk                    ;
109: wire            ref_clk                 ;
110: wire            core_rst_n              ;
111: //AXIS master interface
112: wire            axis_master_tvalid      ;
113: wire            axis_master_tready      ;
114: wire    [127:0] axis_master_tdata       ;
115: wire    [3:0]   axis_master_tkeep       ;
116: wire            axis_master_tlast       ;
117: wire    [7:0]   axis_master_tuser       ;
118: 
119: //axis slave 0 interface
120: wire            axis_slave0_tready      ;
121: wire            axis_slave0_tvalid      ;
122: wire    [127:0] axis_slave0_tdata       ;
123: wire            axis_slave0_tlast       ;
124: wire            axis_slave0_tuser       ;
125: 
126: //axis slave 1 interface
127: wire            axis_slave1_tready      ;
128: wire            axis_slave1_tvalid      ;
129: wire    [127:0] axis_slave1_tdata       ;
130: wire            axis_slave1_tlast       ;
131: wire            axis_slave1_tuser       ;
132: 
133: //axis slave 2 interface
134: wire            axis_slave2_tready      ;
135: wire            axis_slave2_tvalid      ;
136: wire    [127:0] axis_slave2_tdata       ;
137: wire            axis_slave2_tlast       ;
138: wire            axis_slave2_tuser       ;
139: 
140: wire    [7:0]   cfg_pbus_num            ;
141: wire    [4:0]   cfg_pbus_dev_num        ;
142: wire    [2:0]   cfg_max_rd_req_size     ;
143: wire    [2:0]   cfg_max_payload_size    ;
144: wire            cfg_rcb                 ;
145: 
146: wire            cfg_ido_req_en          ;
147: wire            cfg_ido_cpl_en          ;
148: wire    [7:0]   xadm_ph_cdts            ;
149: wire    [11:0]  xadm_pd_cdts            ;
150: wire    [7:0]   xadm_nph_cdts           ;
151: wire    [11:0]  xadm_npd_cdts           ;
152: wire    [7:0]   xadm_cplh_cdts          ;
153: wire    [11:0]  xadm_cpld_cdts          ;
154: 
155: //system signal
156: wire    [4:0]   smlh_ltssm_state        ;
157: 
158: // led lights up
159: reg     [22:0]  ref_led_cnt             ;
160: reg     [26:0]  pclk_led_cnt            ;
161: 
162: //uart2apb 32bits
163: wire            uart_p_sel              ;
164: wire    [3:0]   uart_p_strb             ;
165: wire    [15:0]  uart_p_addr             ;
166: wire    [31:0]  uart_p_wdata            ;
167: wire            uart_p_ce               ;
168: wire            uart_p_we               ;
169: wire            uart_p_rdy              ;
170: wire    [31:0]  uart_p_rdata            ;
171: 
172: //apb
173: wire    [3:0]   p_strb                  ;
174: wire    [15:0]  p_addr                  ;
175: wire    [31:0]  p_wdata                 ;
176: wire            p_ce                    ;
177: wire            p_we                    ;
178: 
179: //apb mux
180: wire            p_sel_pcie              ;       //0~5:hsstlp 6:Reserved 7:pcie
181: wire            p_sel_cfg               ;       //8: cfg
182: wire            p_sel_dma               ;       //9: dma
183: 
184: wire    [31:0]  p_rdata_pcie            ;       //0~5:hsstlp 6:Reserved 7:pcie
185: wire    [31:0]  p_rdata_cfg             ;       //8: cfg
186: wire    [31:0]  p_rdata_dma             ;       //9: dma
187: 
188: wire            p_rdy_pcie              ;       //0~5:hsstlp 6:Reserved 7:pcie
189: wire            p_rdy_cfg               ;       //8: cfg
190: wire            p_rdy_dma               ;       //9: dma
191: 
192: 
193: assign cfg_ido_req_en   =   1'b0;
194: assign cfg_ido_cpl_en   =   1'b0;
195: assign xadm_ph_cdts     =   8'b0;
196: assign xadm_pd_cdts     =   12'b0;
197: assign xadm_nph_cdts    =   8'b0;
198: assign xadm_npd_cdts    =   12'b0;
199: assign xadm_cplh_cdts   =   8'b0;
200: assign xadm_cpld_cdts   =   12'b0;
201: 
202: //----------------------------------------------------------rst debounce ----------------------------------------------------------
203: //ASYNC RST  define IPS2L_PCIE_SPEEDUP_SIM when simulation
204: hsst_rst_cross_sync_v1_0 #(
205:     `ifdef IPS2L_PCIE_SPEEDUP_SIM
206:     .RST_CNTR_VALUE     (16'h10             )
207:     `else
208:     .RST_CNTR_VALUE     (16'hC000           )
209:     `endif
210: )
211: u_refclk_buttonrstn_debounce(
212:     .clk                (ref_clk            ),
213:     .rstn_in            (button_rst_n       ),
214:     .rstn_out           (sync_button_rst_n  )
215: );
216: 
217: hsst_rst_cross_sync_v1_0 #(
218:     `ifdef IPS2L_PCIE_SPEEDUP_SIM
219:     .RST_CNTR_VALUE     (16'h10             )
220:     `else
221:     .RST_CNTR_VALUE     (16'hC000           )
222:     `endif
223: )
224: u_refclk_perstn_debounce(
225:     .clk                (ref_clk            ),
226:     .rstn_in            (perst_n            ),
227:     .rstn_out           (sync_perst_n       )
228: );
229: 
230: hsst_rst_sync_v1_0  u_ref_core_rstn_sync    (
231:     .clk                (ref_clk            ),
232:     .rst_n              (core_rst_n         ),
233:     .sig_async          (1'b1               ),
234:     .sig_synced         (ref_core_rst_n     )
235: );
236: 
237: hsst_rst_sync_v1_0  u_pclk_core_rstn_sync   (
238:     .clk                (pclk               ),
239:     .rst_n              (core_rst_n         ),
240:     .sig_async          (1'b1               ),
241:     .sig_synced         (s_pclk_rstn        )
242: );
243: 
244: 
245: //----------------------------------------------------------clk led ----------------------------------------------------------
246: always @(posedge ref_clk or negedge sync_perst_n)
247: begin
248:     if (!sync_perst_n)
249:         ref_led_cnt    <= 23'd0;
250:     else
251:         ref_led_cnt    <= ref_led_cnt + 23'd1;
252: end
253: 
254: always @(posedge ref_clk or negedge sync_perst_n)
255: begin
256:     if (!sync_perst_n)
257:         ref_led        <= 1'b1;
258:     else if(&ref_led_cnt)
259:         ref_led        <= ~ref_led;
260: end
261: 
262: always @(posedge pclk or negedge s_pclk_rstn)
263: begin
264:     if (!s_pclk_rstn)
265:         pclk_led_cnt    <= 27'd0;
266:     else
267:         pclk_led_cnt    <= pclk_led_cnt + 27'd1;
268: end
269: 
270: always @(posedge pclk or negedge s_pclk_rstn)
271: begin
272:     if (!s_pclk_rstn)
273:         pclk_led        <= 1'b1;
274:     else if(&pclk_led_cnt)
275:         pclk_led        <= ~pclk_led;
276: end
277: 
278: 
279: // //----------------------------------------------------------uart2apb ----------------------------------------------------------
280: // pgr_uart2apb_top_32bit u_uart2apb_top(
281: //     .i_clk        (ref_clk            ), // input
282: //     .i_rst_n      (ref_core_rst_n     ), // input
283: //     //apb enable
284: //     .o_p_sel      (uart_p_sel         ), // output
285: //     .o_p_strb     (uart_p_strb        ), // output  [SW-1:0]
286: //     .o_p_addr     (uart_p_addr        ), // output  [AW-1:0]
287: //     .o_p_wdata    (uart_p_wdata       ), // output  [DW-1:0]
288: //     .o_p_enable   (uart_p_ce          ), // output
289: //     .o_p_we       (uart_p_we          ), // output
290: //     .i_p_ready    (uart_p_rdy         ), // input
291: //     .i_p_rdata    (uart_p_rdata       ), // input   [DW-1:0]
292: //     .i_apb_en     (1'b1               ), // input
293: //     .i_strb_en    (1'b1               ), // input
294: //     //uart
295: //     .o_uart_txd   (txd                ), // output
296: //     .i_uart_rxd   (rxd                ), // input
297: //     //just for debug
298: //     .rx_overrun   (                   ), // output
299: //     .rx_chk_err   (                   ), // output
300: //     //apb bypass
301: //     .o_uart_txvld (                   ), // output
302: //     .i_uart_txreq (1'd0               ), // input
303: //     .i_uart_txdata(8'd0               ), // input   [7:0]
304: //     .i_uart_rxreq (1'd0               ), // input
305: //     .o_uart_rxdata(                   ), // output  [7:0]
306: //     .o_uart_rxvld (                   )  // output
307: // );
308: //----------------------------------------------------------apb mux----------------------------------------------------------
309: // ips2l_expd_apb_mux u_ips2l_pcie_expd_apb_mux(
310: //     //from ref_clk domain
311: //     .i_uart_clk             (ref_clk        ),
312: //     .i_uart_rst_n           (ref_core_rst_n ),
313: //     .i_uart_p_sel           (uart_p_sel     ),
314: //     .i_uart_p_strb          (uart_p_strb    ),
315: //     .i_uart_p_addr          (uart_p_addr    ),
316: //     .i_uart_p_wdata         (uart_p_wdata   ),
317: //     .i_uart_p_ce            (uart_p_ce      ),
318: //     .i_uart_p_we            (uart_p_we      ),
319: //     .o_uart_p_rdy           (uart_p_rdy     ),
320: //     .o_uart_p_rdata         (uart_p_rdata   ),
321: //     //to pclk_div2 domain
322: //     .i_pclk_div2_clk        (pclk_div2      ),
323: //     .i_pclk_div2_rst_n      (core_rst_n     ),
324: 
325: //     .o_pclk_div2_p_strb     (p_strb         ),
326: //     .o_pclk_div2_p_addr     (p_addr         ),
327: //     .o_pclk_div2_p_wdata    (p_wdata        ),
328: //     .o_pclk_div2_p_ce       (p_ce           ),
329: //     .o_pclk_div2_p_we       (p_we           ),
330: //     //to pcie
331: //     .o_pcie_p_sel           (p_sel_pcie     ),
332: //     .i_pcie_p_rdy           (p_rdy_pcie     ),
333: //     .i_pcie_p_rdata         (p_rdata_pcie   ),
334: //     //to dma
335: //     .o_dma_p_sel            (p_sel_dma      ),
336: //     .i_dma_p_rdy            (p_rdy_dma      ),
337: //     .i_dma_p_rdata          (p_rdata_dma    ),
338: //     //to cfg
339: //     .o_cfg_p_sel            (p_sel_cfg      ),
340: //     .i_cfg_p_rdy            (p_rdy_cfg      ),
341: //     .i_cfg_p_rdata          (p_rdata_cfg    )
342: // );
343: //----------------------------------------------------------   dma  ----------------------------------------------------------
344: // DMA CTRL      BASE ADDR = 0x8000
345: wire                     dma_active;     //DMA\xe6\x98\xaf\xe4\xb8\x8d\xe6\x98\xaf\xe6\xb4\xbb\xe8\xb7\x83\xe7\x9a\x84
346: wire                     dma_msi_req  ;
347: wire                     dma_msi_grant;
348: 
349: fpga_v8_pcie_dma_h2f #(
350:     .DEVICE_TYPE            (DEVICE_TYPE            ),
351:     .AXIS_SLAVE_NUM         (AXIS_SLAVE_NUM         ),
352:     .ADDR_WIDTH             (ADDR_WIDTH             )
353: )
354: u_ips2l_pcie_dma
355: (
356:     .pclk                   (pclk                   ),
357:     .prst_n                 (s_pclk_rstn            ),
358:     .clk                    (pclk_div2              ),  //gen1:62.5MHz,gen2:125MHz
359:     .rst_n                  (core_rst_n             ),
360:     //num
361:     .i_cfg_pbus_num         (cfg_pbus_num           ),  //input [7:0]
362:     .i_cfg_pbus_dev_num     (cfg_pbus_dev_num       ),  //input [4:0]
363:     .i_cfg_max_rd_req_size  (cfg_max_rd_req_size    ),  //input [2:0]
364:     .i_cfg_max_payload_size (cfg_max_payload_size   ),  //input [2:0]
365:     //**********************************************************************
366:     //axis master interface
367:     .i_axis_master_tvld     (axis_master_tvalid_mem ),
368:     .o_axis_master_trdy     (axis_master_tready_mem ),
369:     .i_axis_master_tdata    (axis_master_tdata_mem  ),
370:     .i_axis_master_tkeep    (axis_master_tkeep_mem  ),
371:     .i_axis_master_tlast    (axis_master_tlast_mem  ),
372:     .i_axis_master_tuser    (axis_master_tuser_mem  ),
373: 
374:     //**********************************************************************
375:     //axis_slave0 interface
376:     .i_axis_slave0_trdy     (axis_slave0_tready     ),
377:     .o_axis_slave0_tvld     (dma_axis_slave0_tvalid ),
378:     .o_axis_slave0_tdata    (dma_axis_slave0_tdata  ),
379:     .o_axis_slave0_tlast    (dma_axis_slave0_tlast  ),
380:     .o_axis_slave0_tuser    (dma_axis_slave0_tuser  ),
381:     //axis_slave1 interface
382:     .i_axis_slave1_trdy     (axis_slave1_tready     ),
383:     .o_axis_slave1_tvld     (axis_slave1_tvalid     ),
384:     .o_axis_slave1_tdata    (axis_slave1_tdata      ),
385:     .o_axis_slave1_tlast    (axis_slave1_tlast      ),
386:     .o_axis_slave1_tuser    (axis_slave1_tuser      ),
387:     //axis_slave2 interface
388:     .i_axis_slave2_trdy     (axis_slave2_tready     ),
389:     .o_axis_slave2_tvld     (axis_slave2_tvalid     ),
390:     .o_axis_slave2_tdata    (axis_slave2_tdata      ),
391:     .o_axis_slave2_tlast    (axis_slave2_tlast      ),
392:     .o_axis_slave2_tuser    (axis_slave2_tuser      ),
393:     //from pcie
394:     .i_cfg_ido_req_en       (cfg_ido_req_en         ),
395:     .i_cfg_ido_cpl_en       (cfg_ido_cpl_en         ),
396:     .i_xadm_ph_cdts         (xadm_ph_cdts           ),
397:     .i_xadm_pd_cdts         (xadm_pd_cdts           ),
398:     .i_xadm_nph_cdts        (xadm_nph_cdts          ),
399:     .i_xadm_npd_cdts        (xadm_npd_cdts          ),
400:     .i_xadm_cplh_cdts       (xadm_cplh_cdts         ),
401:     .i_xadm_cpld_cdts       (xadm_cpld_cdts         ),
402:     //**********************************************************************
403:     //apb interface
404:     .i_apb_psel             (p_sel_dma              ),
405:     .i_apb_paddr            (p_addr[8:0]            ),
406:     .i_apb_pwdata           (p_wdata                ),
407:     .i_apb_pstrb            (p_strb                 ),
408:     .i_apb_pwrite           (p_we                   ),
409:     .i_apb_penable          (p_ce                   ),
410:     .o_apb_prdy             (p_rdy_dma              ),
411:     .o_apb_prdata           (p_rdata_dma            ),
412:     .o_cross_4kb_boundary   (cross_4kb_boundary     ),
413: 
414: 
415:     ////////////
416:     .o_fpga_msi             (dma_msi_req              ),
417:     .i_fpga_msi_grant       (dma_msi_grant            ),
418:     .o_dma_active           (dma_active               ),    
419:     //*********************************************************************
420:     .o_ddr3_addr  (fpga_ddr3_addr  )             ,
421:     .o_ddr3_length(fpga_ddr3_length)             ,
422:     .o_ddr3_total_length(fpga_ddr3_total_length) ,
423:     //FPGA --> CPU
424:     .fpga_tx_done(fpga_tx_done),
425:     .mwr_tx_busy(mwr_tx_busy),    
426:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe5\xa4\x96\xe9\x83\xa8\xe6\x95\xb0\xe6\x8d\xae\xe5\xb0\xb1\xe7\xbb\xaa\xe4\xbf\xa1\xe5\x8f\xb7
427:     .i_data_ready (fpga_data_ready),
428:     .fpga_tx_clk_en(fpga_tx_clk_en),
429:     .fpga_tx_addr  (fpga_tx_addr  ),
430:     .fpga_tx_data  (fpga_tx_data  ),
431: 
432:     //CPU --> FPGA
433:     .fpga_rx_done   (fpga_rx_done),
434:     .mrd_rx_busy    (mrd_rx_busy),
435:     .fpga_rd_clk_en(fpga_rx_clk_en),
436:     .fpga_rd_addr  (fpga_rx_addr  ),
437:     .fpga_rd_data  (fpga_rx_data  )
438: );
439: 
440: generate
441:     if (DEVICE_TYPE == 3'd4)
442:     begin:rc
443:     //----------------------------------------------------------   cfg ctrl  ----------------------------------------------------------
444:     //CFG TLP TX RX     BASE ADDR = 0x9000
445:         pcie_cfg_ctrl   u_pcie_cfg_ctrl(
446:             //from APB
447:             .pclk_div2              (pclk_div2              ),
448:             .apb_rst_n              (core_rst_n             ),
449:             .p_sel                  (p_sel_cfg              ),
450:             .p_strb                 (p_strb                 ),
451:             .p_addr                 (p_addr[7:0]            ),
452:             .p_wdata                (p_wdata                ),
453:             .p_ce                   (p_ce                   ),
454:             .p_we                   (p_we                   ),
455:             .p_rdy                  (p_rdy_cfg              ),
456:             .p_rdata                (p_rdata_cfg            ),
457:             .pcie_cfg_ctrl_en       (pcie_cfg_ctrl_en       ),
458:             //to PCIE ctrl
459:             .axis_slave_tready      (axis_slave0_tready     ),
460:             .axis_slave_tvalid      (cfg_axis_slave0_tvalid ),
461:             .axis_slave_tlast       (cfg_axis_slave0_tlast  ),
462:             .axis_slave_tuser       (cfg_axis_slave0_tuser  ),
463:             .axis_slave_tdata       (cfg_axis_slave0_tdata  ),
464:             
465:             .axis_master_tready     (axis_master_tready_cfg ),
466:             .axis_master_tvalid     (axis_master_tvalid     ),
467:             .axis_master_tlast      (axis_master_tlast      ),
468:         //    .axis_master_tuser      (axis_master_tuser      ),
469:             .axis_master_tkeep      (axis_master_tkeep      ),
470:             .axis_master_tdata      (axis_master_tdata      )
471:         );
472: 
473:         //----------------------------------------------------------   logic mux  ----------------------------------------------------------
474:         assign axis_slave0_tvalid      = pcie_cfg_ctrl_en ? cfg_axis_slave0_tvalid  : dma_axis_slave0_tvalid;
475:         assign axis_slave0_tlast       = pcie_cfg_ctrl_en ? cfg_axis_slave0_tlast   : dma_axis_slave0_tlast;
476:         assign axis_slave0_tuser       = pcie_cfg_ctrl_en ? cfg_axis_slave0_tuser   : dma_axis_slave0_tuser;
477:         assign axis_slave0_tdata       = pcie_cfg_ctrl_en ? cfg_axis_slave0_tdata   : dma_axis_slave0_tdata;
478: 
479:         assign axis_master_tvalid_mem  = pcie_cfg_ctrl_en ? 1'b0                    : axis_master_tvalid;
480:         assign axis_master_tdata_mem   = pcie_cfg_ctrl_en ? 128'b0                  : axis_master_tdata;
481:         assign axis_master_tkeep_mem   = pcie_cfg_ctrl_en ? 4'b0                    : axis_master_tkeep;
482:         assign axis_master_tlast_mem   = pcie_cfg_ctrl_en ? 1'b0                    : axis_master_tlast;
483:         assign axis_master_tuser_mem   = pcie_cfg_ctrl_en ? 8'b0                    : axis_master_tuser;
484:         
485:         assign axis_master_tready      = pcie_cfg_ctrl_en ? axis_master_tready_cfg  : axis_master_tready_mem;
486:     end
487:     else
488:     begin:ep
489:         assign p_rdy_cfg               = 1'b0;
490:         assign p_rdata_cfg             = 32'b0;
491: 
492:         assign axis_slave0_tvalid      = dma_axis_slave0_tvalid;
493:         assign axis_slave0_tlast       = dma_axis_slave0_tlast;
494:         assign axis_slave0_tuser       = dma_axis_slave0_tuser;
495:         assign axis_slave0_tdata       = dma_axis_slave0_tdata;
496: 
497:         assign axis_master_tvalid_mem  = axis_master_tvalid;
498:         assign axis_master_tdata_mem   = axis_master_tdata;
499:         assign axis_master_tkeep_mem   = axis_master_tkeep;
500:         assign axis_master_tlast_mem   = axis_master_tlast;
501:         assign axis_master_tuser_mem   = axis_master_tuser;
502:         
503:         assign axis_master_tready      = axis_master_tready_mem;
504:     end
505: endgenerate
506: 
507: 
508: ////////////////////   MSI    /////////////////////////////////////
509: //**********************************************************************
510: // MSI Interrupt Logic
511: //**********************************************************************
512: wire                     cfg_msi_en;     // \xe6\x8e\xa5\xe6\x94\xb6\xe6\x9d\xa5\xe8\x87\xaa PCIe IP \xe7\x9a\x84 MSI \xe4\xbd\xbf\xe8\x83\xbd\xe7\x8a\xb6\xe6\x80\x81 (CPU\xe6\x98\xaf\xe5\x90\xa6\xe5\x85\x81\xe8\xae\xb8MSI)
513: wire                     ven_msi_req;    // \xe8\xbe\x93\xe5\x87\xba\xe7\xbb\x99 PCIe IP \xe7\x9a\x84\xe4\xb8\xad\xe6\x96\xad\xe8\xaf\xb7\xe6\xb1\x82
514: wire                     ven_msi_grant;  // \xe6\x8e\xa5\xe6\x94\xb6\xe6\x9d\xa5\xe8\x87\xaa PCIe IP \xe7\x9a\x84\xe5\xba\x94\xe7\xad\x94\xe4\xbf\xa1\xe5\x8f\xb7
515: wire     [MSI_NUM-1 : 0] ven_msi_vector;
516: wire     [31 : 0]        cfg_msi_pending; 
517: 
518: wire     [MSI_NUM-1 : 0] msi_req  ;      
519: wire     [MSI_NUM-1 : 0] msi_grant;
520: 
521: assign msi_req = {i_msi_req, dma_msi_req}  ;
522: 
523: assign dma_msi_grant = msi_grant[0];
524: assign o_msi_grant = msi_grant[MSI_NUM-1 : 1]; 
525: 
526: 
527: msi_arbiter #(
528:     .MSI_NUM(MSI_NUM)  // MSI\xe4\xb8\xad\xe6\x96\xad\xe6\x95\xb0\xe9\x87\x8f
529: )
530: msi_arbiter(
531:     .clk(pclk_div2),              // \xe6\x97\xb6\xe9\x92\x9f\xe4\xbf\xa1\xe5\x8f\xb7
532:     .rst(!core_rst_n),              // \xe5\xbc\x82\xe6\xad\xa5\xe5\xa4\x8d\xe4\xbd\x8d\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x88\xe9\xab\x98\xe6\x9c\x89\xe6\x95\x88\xef\xbc\x89
533: 
534:     .cfg_msi_en(cfg_msi_en), // \xe6\x80\xbb\xe4\xb8\xad\xe6\x96\xad\xe4\xbd\xbf\xe8\x83\xbd\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x88\xe6\x9d\xa5\xe8\x87\xaa\xe4\xb8\xbb\xe6\x9c\xba\xe9\x85\x8d\xe7\xbd\xae\xe7\xa9\xba\xe9\x97\xb4\xef\xbc\x89
535:     .dma_active(dma_active), // DMA\xe5\x8d\xa0\xe7\x94\xa8\xe6\xa0\x87\xe5\xbf\x97\xef\xbc\x88\xe4\xb8\xba1\xe6\x97\xb6\xe4\xbb\x85\xe5\x85\x81\xe8\xae\xb8msi[0]\xe9\x80\x9a\xe8\xbf\x87\xef\xbc\x89
536: 
537:     .msi_req(msi_req),           // MSI\xe4\xb8\xad\xe6\x96\xad\xe8\xaf\xb7\xe6\xb1\x82\xe8\xbe\x93\xe5\x85\xa5\xef\xbc\x88\xe7\x94\xb5\xe5\xb9\xb3\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x8c\xe5\x8f\xaf\xe8\x83\xbd\xe4\xb8\x80\xe7\x9b\xb4\xe6\x8b\x89\xe9\xab\x98\xef\xbc\x89
538:     .msi_grant(msi_grant),     // \xe8\xbf\x94\xe5\x9b\x9e\xe7\xbb\x99\xe5\x90\x84\xe6\xa8\xa1\xe5\x9d\x97\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\xadgrant\xe4\xbf\xa1\xe5\x8f\xb7
539: 
540:     .ven_msi_req  (ven_msi_req  ),   // \xe8\xbe\x93\xe5\x87\xba\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\xad\xe8\xaf\xb7\xe6\xb1\x82\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x88\xe9\xab\x98\xe6\x9c\x89\xe6\x95\x88\xef\xbc\x89
541:     .ven_msi_grant(ven_msi_grant), // \xe4\xb8\xbb\xe6\x9c\xba\xe4\xbe\xa7\xe8\xbf\x94\xe5\x9b\x9e\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\xad\xe6\x8e\xa5\xe6\x94\xb6\xe7\xa1\xae\xe8\xae\xa4\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x881bit\xe8\x84\x89\xe5\x86\xb2\xef\xbc\x89
542:     .ven_msi_vector(ven_msi_vector), // \xe5\xbd\x93\xe5\x89\x8d\xe4\xbb\xb2\xe8\xa3\x81\xe9\x80\x89\xe4\xb8\xad\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\xad\xe5\x90\x91\xe9\x87\x8f\xe5\x8f\xb7
543:     
544:     .cfg_msi_pending(cfg_msi_pending)  // \xe4\xb8\xbb\xe6\x9c\xba\xe4\xbe\xa7\xe8\xaf\xbb\xe5\x8f\x96\xe7\x9a\x84\xe6\x8c\x82\xe8\xb5\xb7\xe4\xb8\xad\xe6\x96\xad\xe7\x8a\xb6\xe6\x80\x81\xe5\xaf\x84\xe5\xad\x98\xe5\x99\xa8
545: );
546: 
547: 
548: 
549: 
550: //----------------------------------------------------------   pcie wrap  ----------------------------------------------------------
551: //pcie wrap : HSSTLP : 0x0000~6000 PCIe BASE ADDR : 0x7000
552: pcie_test
553: u_ips2l_pcie_wrap
554: (
555:     .button_rst_n               (sync_button_rst_n      ),
556:     .power_up_rst_n             (sync_perst_n           ),
557:     .perst_n                    (sync_perst_n           ),
558:     //clk and rst
559:     .pclk                       (pclk                   ),      //output
560:     .pclk_div2                  (pclk_div2              ),      //output
561:     .ref_clk                    (ref_clk                ),      //output
562:     .ref_clk_n                  (ref_clk_n              ),      //input
563:     .ref_clk_p                  (ref_clk_p              ),      //input
564:     .core_rst_n                 (core_rst_n             ),      //output
565:     
566:     //APB interface to  DBI cfg
567:     //.p_clk                      (ref_clk                ),      //input
568:     .p_sel                      (p_sel_pcie             ),      //input
569:     .p_strb                     (uart_p_strb            ),      //input  [ 3:0]
570:     .p_addr                     (uart_p_addr            ),      //input  [15:0]
571:     .p_wdata                    (uart_p_wdata           ),      //input  [31:0]
572:     .p_ce                       (uart_p_ce              ),      //input
573:     .p_we                       (uart_p_we              ),      //input
574:     .p_rdy                      (p_rdy_pcie             ),      //output
575:     .p_rdata                    (p_rdata_pcie           ),      //output [31:0]
576:     
577:     //PHY diff signals
578:     .rxn                        (rxn                    ),      //input   [3:0]
579:     .rxp                        (rxp                    ),      //input   [3:0]
580:     .txn                        (txn                    ),      //output  [3:0]
581:     .txp                        (txp                    ),      //output  [3:0]
582:     
583:     .pcs_nearend_loop           ({4{1'b0}}              ),      //input
584:     .pma_nearend_ploop          ({4{1'b0}}              ),      //input
585:     .pma_nearend_sloop          ({4{1'b0}}              ),      //input
586:     
587:     //AXIS master interface
588:     .axis_master_tvalid         (axis_master_tvalid     ),      //output
589:     .axis_master_tready         (axis_master_tready     ),      //input
590:     .axis_master_tdata          (axis_master_tdata      ),      //output [127:0]
591:     .axis_master_tkeep          (axis_master_tkeep      ),      //output [3:0]
592:     .axis_master_tlast          (axis_master_tlast      ),      //output
593:     .axis_master_tuser          (axis_master_tuser      ),      //output [7:0]
594:     
595:     //axis slave 0 interface
596:     .axis_slave0_tready         (axis_slave0_tready     ),      //output
597:     .axis_slave0_tvalid         (axis_slave0_tvalid     ),      //input
598:     .axis_slave0_tdata          (axis_slave0_tdata      ),      //input  [127:0]
599:     .axis_slave0_tlast          (axis_slave0_tlast      ),      //input
600:     .axis_slave0_tuser          (axis_slave0_tuser      ),      //input
601:     
602:     //axis slave 1 interface
603:     .axis_slave1_tready         (axis_slave1_tready     ),      //output
604:     .axis_slave1_tvalid         (axis_slave1_tvalid     ),      //input
605:     .axis_slave1_tdata          (axis_slave1_tdata      ),      //input  [127:0]
606:     .axis_slave1_tlast          (axis_slave1_tlast      ),      //input
607:     .axis_slave1_tuser          (axis_slave1_tuser      ),      //input
608:     //axis slave 2 interface
609:     .axis_slave2_tready         (axis_slave2_tready     ),      //output
610:     .axis_slave2_tvalid         (axis_slave2_tvalid     ),      //input
611:     .axis_slave2_tdata          (axis_slave2_tdata      ),      //input  [127:0]
612:     .axis_slave2_tlast          (axis_slave2_tlast      ),      //input
613:     .axis_slave2_tuser          (axis_slave2_tuser      ),      //input
614:      
615:     .pm_xtlh_block_tlp          (                       ),      //output
616:     
617:     //msi
618:     .ven_msi_vector             (ven_msi_vector         ),      //input   [4:0]
619:     .cfg_msi_pending            (cfg_msi_pending        ),      //input   [(32*1)-1:0]
620:     .cfg_msi_en                 (cfg_msi_en             ),      //output
621:     
622:     .ven_msi_req                (ven_msi_req            ),      //input
623:     .ven_msi_tc                 (3'b000                 ),      //input   [2:0]
624:     .ven_msi_grant              (ven_msi_grant          ),      //output
625: 
626:     
627:     .cfg_send_cor_err_mux       (                       ),      //output
628:     .cfg_send_nf_err_mux        (                       ),      //output
629:     .cfg_send_f_err_mux         (                       ),      //output
630:     .cfg_sys_err_rc             (                       ),      //output
631:     .cfg_aer_rc_err_mux         (                       ),      //output
632:     //radm timeout
633:     .radm_cpl_timeout           (                       ),      //output
634:     
635:     //configuration signals
636:     .cfg_max_rd_req_size        (cfg_max_rd_req_size    ),      //output [2:0]
637:     .cfg_bus_master_en          (                       ),      //output
638:     .cfg_max_payload_size       (cfg_max_payload_size   ),      //output [2:0]
639:     .cfg_ext_tag_en             (                       ),      //output
640:     .cfg_rcb                    (cfg_rcb                ),      //output
641:     .cfg_mem_space_en           (                       ),      //output
642:     .cfg_pm_no_soft_rst         (                       ),      //output
643:     .cfg_crs_sw_vis_en          (                       ),      //output
644:     .cfg_no_snoop_en            (                       ),      //output
645:     .cfg_relax_order_en         (                       ),      //output
646:     .cfg_tph_req_en             (                       ),      //output [2-1:0]
647:     .cfg_pf_tph_st_mode         (                       ),      //output [3-1:0]
648:     .rbar_ctrl_update           (                       ),      //output
649:     .cfg_atomic_req_en          (                       ),      //output
650:     
651:     .cfg_pbus_num               (cfg_pbus_num           ),      //output [7:0]
652:     .cfg_pbus_dev_num           (cfg_pbus_dev_num       ),      //output [4:0]
653:     
654:     //debug signals
655:     .radm_idle                  (                       ),      //output
656:     .radm_q_not_empty           (                       ),      //output
657:     .radm_qoverflow             (                       ),      //output
658:     .diag_ctrl_bus              (2'b0                   ),      //input   [1:0]
659:     .cfg_link_auto_bw_mux       (                       ),      //output              merge cfg_link_auto_bw_msi and cfg_link_auto_bw_int
660:     .cfg_bw_mgt_mux             (                       ),      //output              merge cfg_bw_mgt_int and cfg_bw_mgt_msi
661:     .cfg_pme_mux                (                       ),      //output              merge cfg_pme_int and cfg_pme_msi
662:     .app_ras_des_sd_hold_ltssm  (1'b0                   ),      //input
663:     .app_ras_des_tba_ctrl       (2'b0                   ),      //input   [1:0]
664:     
665:     .dyn_debug_info_sel         (4'b0                   ),      //input   [3:0]
666:     .debug_info_mux             (                       ),      //output  [132:0]
667:     
668:     //system signal
669:     .smlh_link_up               (smlh_link_up           ),      //output
670:     .rdlh_link_up               (rdlh_link_up           ),      //output
671:     .smlh_ltssm_state           (smlh_ltssm_state       )       //output  [4:0]
672: );
673: 
674: endmodule
