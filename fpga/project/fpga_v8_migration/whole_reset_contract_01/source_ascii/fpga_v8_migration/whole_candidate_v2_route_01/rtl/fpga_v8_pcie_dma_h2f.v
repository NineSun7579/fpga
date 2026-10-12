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
13: // Filename:ips2l_pcie_dma.v
14: //////////////////////////////////////////////////////////////////////////////
15: module fpga_v8_pcie_dma_h2f #(
16:     parameter                           DEVICE_TYPE = 3'd0      ,   //3'd0:EP,3'd1:Legacy EP,3'd4:RC
17:     parameter   integer                 AXIS_SLAVE_NUM = 3      ,
18:     parameter                           ADDR_WIDTH  = 4'd11
19: 
20: )(
21:     input                               pclk                    ,
22:     input                               prst_n                  ,
23:     input                               clk                     ,            //gen1:62.5MHz,gen2:125MHz
24:     input                               rst_n                   ,
25: 
26:     input           [7:0]               i_cfg_pbus_num          ,
27:     input           [4:0]               i_cfg_pbus_dev_num      ,
28:     input           [2:0]               i_cfg_max_rd_req_size   ,
29:     input           [2:0]               i_cfg_max_payload_size  ,
30:     //**********************************************************************
31:     //axis master interface
32:     input                               i_axis_master_tvld      ,
33:     output  wire                        o_axis_master_trdy      ,
34:     input           [127:0]             i_axis_master_tdata     ,
35:     input           [3:0]               i_axis_master_tkeep     ,
36:     input                               i_axis_master_tlast     ,
37:     input           [7:0]               i_axis_master_tuser     ,
38:     output  wire    [2:0]               o_trgt1_radm_pkt_halt   ,
39: //    input           [5:0]               i_radm_grant_tlp_type   ,
40:     //**********************************************************************
41:     //axis_slave0 interface
42:     input                               i_axis_slave0_trdy      ,
43:     output  wire                        o_axis_slave0_tvld      ,
44:     output  wire    [127:0]             o_axis_slave0_tdata     ,
45:     output  wire                        o_axis_slave0_tlast     ,
46:     output  wire                        o_axis_slave0_tuser     ,
47:     //axis_slave1 interface
48:     input                               i_axis_slave1_trdy      ,
49:     output  wire                        o_axis_slave1_tvld      ,
50:     output  wire    [127:0]             o_axis_slave1_tdata     ,
51:     output  wire                        o_axis_slave1_tlast     ,
52:     output  wire                        o_axis_slave1_tuser     ,
53:     //axis_slave2 interface
54:     input                               i_axis_slave2_trdy      ,
55:     output  wire                        o_axis_slave2_tvld      ,
56:     output  wire    [127:0]             o_axis_slave2_tdata     ,
57:     output  wire                        o_axis_slave2_tlast     ,
58:     output  wire                        o_axis_slave2_tuser     ,
59:     //**********************************************************************
60:     //credit interface
61:     //from pcie
62:     input                               i_cfg_ido_req_en        ,
63:     input                               i_cfg_ido_cpl_en        ,
64:     input           [7:0]               i_xadm_ph_cdts          ,
65:     input           [11:0]              i_xadm_pd_cdts          ,
66:     input           [7:0]               i_xadm_nph_cdts         ,
67:     input           [11:0]              i_xadm_npd_cdts         ,
68:     input           [7:0]               i_xadm_cplh_cdts        ,
69:     input           [11:0]              i_xadm_cpld_cdts        ,
70:     //**********************************************************************
71:     //apb interface
72:     input                               i_apb_psel              ,
73:     input           [8:0]               i_apb_paddr             ,
74:     input           [31:0]              i_apb_pwdata            ,
75:     input           [3:0]               i_apb_pstrb             ,
76:     input                               i_apb_pwrite            ,
77:     input                               i_apb_penable           ,
78:     output  wire                        o_apb_prdy              ,
79:     output  wire    [31:0]              o_apb_prdata            ,
80:     //cross_4kb_boundary
81:     output  wire                        o_cross_4kb_boundary    ,
82: 
83:     //////////////////////////////////////////////////
84:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe8\xbe\x93\xe5\x87\xba\xe7\xbb\x99\xe5\xba\x95\xe5\xb1\x82 PCIe IP \xe7\x9a\x84 MSI \xe8\xaf\xb7\xe6\xb1\x82
85:     output  wire                        o_fpga_msi              , 
86:     input   wire                        i_fpga_msi_grant        ,
87:     output  wire                        o_dma_active            ,
88:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe4\xb8\x93\xe9\x97\xa8\xe8\xbe\x93\xe5\x87\xba\xe7\xbb\x99 DDR3 \xe8\xaf\xbb\xe5\x86\x99\xe6\x8e\xa7\xe5\x88\xb6\xe9\x80\xbb\xe8\xbe\x91\xe7\x9a\x84\xe8\xb5\xb7\xe5\xa7\x8b\xe5\x9c\xb0\xe5\x9d\x80
89:     output  wire     [31:0]             o_ddr3_addr             ,
90:     output  wire     [31:0]             o_ddr3_length           ,
91:     output  wire     [31:0]             o_ddr3_total_length     ,
92:     //*********************************************************************
93:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe6\x95\xb0\xe6\x8d\xae\xe5\xb0\xb1\xe7\xbb\xaa\xe4\xbf\xa1\xe5\x8f\xb7\xef\xbc\x88\xe5\xa4\x96\xe9\x83\xa8 DDR3 \xe9\x80\xbb\xe8\xbe\x91\xe5\x91\x8a\xe7\x9f\xa5 FPGA \xe5\x8f\xaf\xe4\xbb\xa5\xe5\xbc\x80\xe5\xa7\x8b\xe8\xaf\xbb\xef\xbc\x89
94:     input                             i_data_ready               ,
95:     //\xe4\xb8\x8b\xe9\x99\x8d\xe6\xb2\xbf DDR3\xe5\xb7\xb2\xe7\xbb\x8f\xe5\xae\x8c\xe6\x88\x90\xe4\xbc\xa0\xe8\xbe\x93 
96:     input                             fpga_tx_done,
97:     input                             fpga_rx_done,
98:     //\xe4\xb8\x8b\xe9\x99\x8d\xe6\xb2\xbf \xe5\x85\x81\xe8\xae\xb8FIFO\xe5\xbc\x80\xe5\xa7\x8b\xe5\x92\x8cram\xe6\x90\xac\xe8\xbf\x90
99:     output                            mwr_tx_busy, 
100:     output                            mrd_rx_busy, 
101:     //FPGA --> CPU
102:     output                            fpga_tx_clk_en,
103:     output        [ADDR_WIDTH-1:0]    fpga_tx_addr  ,
104:     input         [127:0]             fpga_tx_data  ,
105:     //CPU --> FPGA
106:     input                             fpga_rd_clk_en,
107:     input         [ADDR_WIDTH-1:0]    fpga_rd_addr  ,
108:     output        [127:0]             fpga_rd_data     
109: );
110: 
111: wire        fpga_msi_pulse; // \xe6\x8e\xa5\xe6\x94\xb6\xe6\x9d\xa5\xe8\x87\xaa DMA Controller \xe7\x9a\x84 MSI \xe8\x84\x89\xe5\x86\xb2
112: reg         fpga_msi_r;
113: // \xe6\x8f\xa1\xe6\x89\x8b\xe9\x80\xbb\xe8\xbe\x91\xef\xbc\x9a\xe5\xb0\x86\xe5\x8d\x95\xe6\x8b\x8d\xe8\x84\x89\xe5\x86\xb2\xe5\xb1\x95\xe5\xae\xbd\xef\xbc\x8c\xe7\x9b\xb4\xe5\x88\xb0\xe6\x94\xb6\xe5\x88\xb0 grant \xe5\xba\x94\xe7\xad\x94
114: always @(posedge clk or negedge rst_n) begin
115:     if (!rst_n) begin
116:         fpga_msi_r <= 1'b0;
117:     end 
118:     // \xe5\xbd\x93\xe6\x94\xb6\xe5\x88\xb0 DMA \xe7\x9a\x84\xe5\xae\x8c\xe6\x88\x90\xe8\x84\x89\xe5\x86\xb2\xe6\x8b\x89\xe9\xab\x98\xe8\xaf\xb7\xe6\xb1\x82
119:     else if (fpga_msi_pulse) begin
120:         fpga_msi_r <= 1'b1; 
121:     end 
122:     // \xe5\xbd\x93 PCIe \xe5\xba\x95\xe5\xb1\x82\xe7\xa1\xac\xe6\xa0\xb8\xe5\x93\x8d\xe5\xba\x94\xe4\xba\x86\xe6\x88\x91\xe4\xbb\xac\xe7\x9a\x84\xe8\xaf\xb7\xe6\xb1\x82\xe5\x90\x8e\xef\xbc\x8c\xe6\x92\xa4\xe9\x94\x80\xe8\xaf\xb7\xe6\xb1\x82
123:     else if (i_fpga_msi_grant) begin
124:         fpga_msi_r <= 1'b0; 
125:     end
126: end
127: assign o_fpga_msi = fpga_msi_r;
128: 
129: // DMA \xe6\x80\xbb\xe6\xb4\xbb\xe8\xb7\x83
130: reg dma_active;
131: always @(posedge clk or negedge rst_n) begin
132:     if (!rst_n) begin
133:         dma_active <= 1'b0;
134:     end
135:     else if(o_fpga_msi & i_fpga_msi_grant) begin
136:         dma_active <= 1'b0;
137:     end
138:     else if((mwr32_req || mwr64_req) || (mrd32_req || mrd64_req)) begin
139:         dma_active <= 1'b1;
140:     end
141: end
142: assign o_dma_active = dma_active;
143: 
144: //**********************************************************************
145: //from rx to tx
146: wire        [2:0]               mrd_tc;
147: wire        [2:0]               mrd_attr;
148: wire        [9:0]               mrd_length;
149: wire        [15:0]              mrd_id;
150: wire        [7:0]               mrd_tag;
151: wire        [63:0]              mrd_addr;
152: 
153: wire                            cpld_req_vld;
154: wire                            cpld_req_rdy;
155: wire                            cpld_tx_rdy;
156: //cpld rcv
157: wire                            cpld_rcv;
158: wire        [7:0]               cpld_tag;
159: wire                            tag_full;
160: //from dma_controller to tx
161: wire                            user_define_header_flag;
162: wire                            user_define_data_flag;
163: //mwr req & ack
164: wire                            mwr32_req;
165: wire                            mwr32_req_ack;
166: wire                            mwr64_req;
167: wire                            mwr64_req_ack;
168: //mrd req & ack
169: wire                            mrd32_req;
170: wire                            mrd32_req_ack;
171: wire                            mrd64_req;
172: wire                            mrd64_req_ack;
173: //req information
174: wire        [10:0]              req_length;
175: wire        [63:0]              req_addr;
176: wire        [31:0]              req_data;
177: 
178: 
179: //axis_slave0 interface
180: wire                            dma_axis_slave0_trdy ;
181: wire                            dma_axis_slave0_tvld ;
182: wire        [127:0]             dma_axis_slave0_tdata;
183: wire                            dma_axis_slave0_tlast;
184: wire                            dma_axis_slave0_tuser;
185: //axis_slave1 interface
186: wire                            dma_axis_slave1_trdy ;
187: wire                            dma_axis_slave1_tvld ;
188: wire        [127:0]             dma_axis_slave1_tdata;
189: wire                            dma_axis_slave1_tlast;
190: wire                            dma_axis_slave1_tuser;
191: //axis_slave2 interface
192: wire                            dma_axis_slave2_trdy ;
193: wire                            dma_axis_slave2_tvld ;
194: wire        [127:0]             dma_axis_slave2_tdata;
195: wire                            dma_axis_slave2_tlast;
196: wire                            dma_axis_slave2_tuser;
197: 
198: //**********************************************************************
199: //bar0 rd interface
200: wire                            bar0_rd_clk_en;
201: wire        [ADDR_WIDTH-1:0]    bar0_rd_addr;
202: wire        [127:0]             bar0_rd_data;
203: //bar1 wr interface
204: wire                            bar1_wr_en;
205: wire        [ADDR_WIDTH-1:0]    bar1_wr_addr;
206: wire        [127:0]             bar1_wr_data;
207: wire        [15:0]              bar1_wr_byte_en;
208: //bar2 rd interface
209: wire                            bar2_rd_clk_en;
210: wire        [ADDR_WIDTH-1:0]    bar2_rd_addr  ;
211: wire        [127:0]             bar2_rd_data  ;
212: //**********************************************************************
213: //rst tlp cnt
214: wire                            tx_restart;
215: wire        [63:0]              dma_check_result;
216: //debug bus
217: //wire        [42:0]              dbg_bus_rx_ctrl;
218: //wire        [43:0]              dbg_bus_mrd_tx;
219: //wire        [72:0]              dbg_bus_mwr_tx;
220: 
221: //assign o_dbg_bus = {
222: //                    dbg_bus_mwr_tx, //159:87
223: //                    dbg_bus_mrd_tx, //86:43
224: //                    dbg_bus_rx_ctrl //42:0
225: //                    };
226: wire        [7:0]               cfg_pbus_num;
227: wire        [4:0]               cfg_pbus_dev_num;
228: wire        [2:0]               cfg_max_rd_req_size_reg;
229: wire        [2:0]               cfg_max_payload_size_reg;
230: ips2l_pcie_reg #(
231:     .SIG_WIDTH                  (4'd8                       )
232: )
233: u_cfg_pbus_num_reg
234: (
235:     .clk                        (clk                        ),
236:     .sig                        (i_cfg_pbus_num             ),
237:     .sig_reg                    (cfg_pbus_num               )
238: );
239: 
240: ips2l_pcie_reg #(
241:     .SIG_WIDTH                  (3'd5                       )
242: )
243: u_cfg_pbus_dev_num_reg
244: (
245:     .clk                        (clk                        ),
246:     .sig                        (i_cfg_pbus_dev_num         ),
247:     .sig_reg                    (cfg_pbus_dev_num           )
248: );
249: 
250: ips2l_pcie_reg #(
251:     .SIG_WIDTH                  (2'd3                       )
252: )
253: u_max_rd_req_size_reg
254: (
255:     .clk                        (clk                        ),
256:     .sig                        (i_cfg_max_rd_req_size      ),
257:     .sig_reg                    (cfg_max_rd_req_size_reg    )
258: );
259: 
260: ips2l_pcie_reg #(
261:     .SIG_WIDTH                  (2'd3                       )
262: )
263: u_max_payload_size_reg
264: (
265:     .clk                        (clk                        ),
266:     .sig                        (i_cfg_max_payload_size     ),
267:     .sig_reg                    (cfg_max_payload_size_reg   )
268: );
269: 
270: 
271: ips2l_pcie_dma_rx_top #(
272:     .DEVICE_TYPE                (DEVICE_TYPE                ),  //3'd0:EP,3'd1:Legacy EP,3'd4:RC
273:     .ADDR_WIDTH                 (ADDR_WIDTH                 )
274: )
275: u_ips2l_pcie_dma_rx_top
276: (
277:     .clk                        (clk                        ),  //gen1:62.5MHz,gen2:125MHz
278:     .rst_n                      (rst_n                      ),
279:     .i_cfg_max_rd_req_size      (cfg_max_rd_req_size_reg    ),  //input [2:0]
280:     //**********************************************************************
281:     //axis master interface
282:     .i_axis_master_tvld         (i_axis_master_tvld         ),
283:     .o_axis_master_trdy         (o_axis_master_trdy         ),
284:     .i_axis_master_tdata        (i_axis_master_tdata        ),
285:     .i_axis_master_tkeep        (i_axis_master_tkeep        ),
286:     .i_axis_master_tlast        (i_axis_master_tlast        ),
287:     .i_axis_master_tuser        (i_axis_master_tuser        ),
288:     .o_trgt1_radm_pkt_halt      (o_trgt1_radm_pkt_halt      ),
289: //    .i_radm_grant_tlp_type      (i_radm_grant_tlp_type      ),
290:     //**********************************************************************
291:     //bar0 rd interface
292:     .i_bar0_rd_clk_en           (bar0_rd_clk_en             ),
293:     .i_bar0_rd_addr             (bar0_rd_addr               ),
294:     .o_bar0_rd_data             (bar0_rd_data               ),
295:     //bar2 rd interface
296:     .i_bar2_rd_clk_en          (fpga_rd_clk_en             ),
297:     .i_bar2_rd_addr            (fpga_rd_addr               ),
298:     .o_bar2_rd_data            (fpga_rd_data               ),
299:     //bar1 wr interface
300:     .o_bar1_wr_en               (bar1_wr_en                 ),
301:     .o_bar1_wr_addr             (bar1_wr_addr               ),
302:     .o_bar1_wr_data             (bar1_wr_data               ),
303:     .o_bar1_wr_byte_en          (bar1_wr_byte_en            ),
304:     //**********************************************************************
305:     //to tx top
306:     //req rcv
307:     .o_mrd_tc                   (mrd_tc                     ),
308:     .o_mrd_attr                 (mrd_attr                   ),
309:     .o_mrd_length               (mrd_length                 ),
310:     .o_mrd_id                   (mrd_id                     ),
311:     .o_mrd_tag                  (mrd_tag                    ),
312:     .o_mrd_addr                 (mrd_addr                   ),
313: 
314:     .o_cpld_req_vld             (cpld_req_vld               ),
315:     .i_cpld_req_rdy             (cpld_req_rdy               ),
316:     .i_cpld_tx_rdy              (cpld_tx_rdy                ),
317:     //cpld rcv
318:     .o_cpld_rcv                 (cpld_rcv                   ),
319:     .o_cpld_tag                 (cpld_tag                   ),
320:     .i_tag_full                 (tag_full                   ),
321:     //rst tlp cnt
322:     .o_dma_check_result         (dma_check_result           ),
323:     .i_tx_restart               (tx_restart                 )
324: 
325:     //.o_dbg_bus_rx_ctrl          (dbg_bus_rx_ctrl            )
326: );
327: 
328: fpga_v8_pcie_dma_controller_h2f #(
329:     .DEVICE_TYPE                (DEVICE_TYPE                ),  //3'd0:EP,3'd1:Legacy EP,3'd4:RC
330:     .ADDR_WIDTH                 (ADDR_WIDTH                 )
331: )
332: u_ips2l_pcie_dma_controller
333: (
334:     .clk                        (clk                        ),  //gen1:62.5MHz,gen2:125MHz
335:     .rst_n                      (rst_n                      ),
336:     ////
337:     .i_mwr_tx_busy              (~fpga_tx_done              ), // [\xe6\x96\xb0\xe5\xa2\x9e]
338:     .i_mrd_rx_busy              (~fpga_rx_done              ), // [\xe6\x96\xb0\xe5\xa2\x9e]
339:     .o_fpga_msi                 (fpga_msi_pulse             ), // [\xe6\x96\xb0\xe5\xa2\x9e]
340:     //**********************************************************************
341:     //bar1 wr interface
342:     .i_bar1_wr_en               (bar1_wr_en                 ),
343:     .i_bar1_wr_addr             (bar1_wr_addr               ),
344:     .i_bar1_wr_data             (bar1_wr_data               ),
345:     .i_bar1_wr_byte_en          (bar1_wr_byte_en            ),
346:     //**********************************************************************
347:     //apb interface
348:     .i_apb_psel                 (i_apb_psel                 ),
349:     .i_apb_paddr                (i_apb_paddr                ),
350:     .i_apb_pwdata               (i_apb_pwdata               ),
351:     .i_apb_pstrb                (i_apb_pstrb                ),
352:     .i_apb_pwrite               (i_apb_pwrite               ),
353:     .i_apb_penable              (i_apb_penable              ),
354:     .o_apb_prdy                 (o_apb_prdy                 ),
355:     .o_apb_prdata               (o_apb_prdata               ),
356:     //**********************************************************************
357:     .o_user_define_data_flag    (user_define_data_flag      ),
358: 
359:     //**********************************************************************
360:     //to tx top
361:     //mwr req & ack
362:     .o_mwr32_req                (mwr32_req                  ),
363:     .i_mwr32_req_ack            (mwr32_req_ack              ),
364:     .o_mwr64_req                (mwr64_req                  ),
365:     .i_mwr64_req_ack            (mwr64_req_ack              ),
366:     //mrd req & ack
367:     .o_mrd32_req                (mrd32_req                  ),
368:     .i_mrd32_req_ack            (mrd32_req_ack              ),
369:     .o_mrd64_req                (mrd64_req                  ),
370:     .i_mrd64_req_ack            (mrd64_req_ack              ),
371:     //req information
372:     .o_req_length               (req_length                 ),
373:     .o_req_addr                 (req_addr                   ),
374:     .o_req_data                 (req_data                   ),
375:     .o_cross_4kb_boundary       (o_cross_4kb_boundary       ),
376:     //rst tlp cnt
377:     .i_dma_check_result         (dma_check_result           ),
378:     .o_tx_restart               (tx_restart                 ),
379: 
380:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe4\xb8\x93\xe9\x97\xa8\xe8\xbe\x93\xe5\x87\xba\xe7\xbb\x99 DDR3 \xe8\xaf\xbb\xe5\x86\x99\xe6\x8e\xa7\xe5\x88\xb6\xe9\x80\xbb\xe8\xbe\x91\xe7\x9a\x84\xe8\xb5\xb7\xe5\xa7\x8b\xe5\x9c\xb0\xe5\x9d\x80
381:     .o_ddr3_addr               (o_ddr3_addr                 ),
382:     .o_ddr3_length             (o_ddr3_length               ),
383:     .o_ddr3_total_length       (o_ddr3_total_length         )
384: );
385: 
386: ips2l_pcie_dma_tx_top #(
387:     .DEVICE_TYPE                (DEVICE_TYPE                ),          //3'd0:EP,3'd1:Legacy EP,3'd4:RC
388:     .ADDR_WIDTH                 (ADDR_WIDTH                 )
389: )
390: u_ips2l_pcie_dma_tx_top
391: (
392:     .clk                        (clk                        ),  //gen1:62.5MHz,gen2:125MHz
393:     .rst_n                      (rst_n                      ),
394:     .i_cfg_pbus_num             (cfg_pbus_num               ),  //input [7:0]
395:     .i_cfg_pbus_dev_num         (cfg_pbus_dev_num           ),  //input [4:0]
396:     .i_cfg_max_rd_req_size      (cfg_max_rd_req_size_reg    ),  //input [2:0]
397:     .i_cfg_max_payload_size     (cfg_max_payload_size_reg   ),  //input [2:0]
398:     .o_mwr_tx_busy              (mwr_tx_busy                ),  // [\xe6\x96\xb0\xe5\xa2\x9e]
399:     .o_mrd_rx_busy              (mrd_rx_busy                ),  // [\xe6\x96\xb0\xe5\xa2\x9e]
400:     // [\xe6\x96\xb0\xe5\xa2\x9e] \xe5\xa4\x96\xe9\x83\xa8\xe6\x95\xb0\xe6\x8d\xae\xe5\xb0\xb1\xe7\xbb\xaa\xe4\xbf\xa1\xe5\x8f\xb7
401:     .i_data_ready               (i_data_ready               ),
402:     //**********************************************************************
403:     //axis_slave0 interface
404:     .i_axis_slave0_trdy         (dma_axis_slave0_trdy       ),
405:     .o_axis_slave0_tvld         (dma_axis_slave0_tvld       ),
406:     .o_axis_slave0_tdata        (dma_axis_slave0_tdata      ),
407:     .o_axis_slave0_tlast        (dma_axis_slave0_tlast      ),
408:     .o_axis_slave0_tuser        (dma_axis_slave0_tuser      ),
409:     //axis_slave1 interface
410:     .i_axis_slave1_trdy         (dma_axis_slave1_trdy       ),
411:     .o_axis_slave1_tvld         (dma_axis_slave1_tvld       ),
412:     .o_axis_slave1_tdata        (dma_axis_slave1_tdata      ),
413:     .o_axis_slave1_tlast        (dma_axis_slave1_tlast      ),
414:     .o_axis_slave1_tuser        (dma_axis_slave1_tuser      ),
415:     //axis_slave2 interface
416:     .i_axis_slave2_trdy         (dma_axis_slave2_trdy       ),
417:     .o_axis_slave2_tvld         (dma_axis_slave2_tvld       ),
418:     .o_axis_slave2_tdata        (dma_axis_slave2_tdata      ),
419:     .o_axis_slave2_tlast        (dma_axis_slave2_tlast      ),
420:     .o_axis_slave2_tuser        (dma_axis_slave2_tuser      ),
421:     //**********************************************************************
422:     //from dma_controller
423:     .i_user_define_data_flag    (user_define_data_flag      ),
424: 
425:     .i_mwr32_req                (mwr32_req                  ),
426:     .o_mwr32_req_ack            (mwr32_req_ack              ),
427:     .i_mwr64_req                (mwr64_req                  ),
428:     .o_mwr64_req_ack            (mwr64_req_ack              ),
429: 
430:     .i_mrd32_req                (mrd32_req                  ),
431:     .o_mrd32_req_ack            (mrd32_req_ack              ),
432:     .i_mrd64_req                (mrd64_req                  ),
433:     .o_mrd64_req_ack            (mrd64_req_ack              ),
434: 
435:     .i_req_length               (req_length                 ),
436:     .i_req_addr                 (req_addr                   ),
437:     .i_req_data                 (req_data                   ),
438: 
439:     //**********************************************************************
440:     //bar0 rd interface
441:     .o_bar0_rd_clk_en           (bar0_rd_clk_en             ),
442:     .o_bar0_rd_addr             (bar0_rd_addr               ),
443:     .i_bar0_rd_data             (bar0_rd_data               ),
444:     //bar2 rd interface
445:     .o_bar2_rd_clk_en           (fpga_tx_clk_en             ),
446:     .o_bar2_rd_addr             (fpga_tx_addr               ),
447:     .i_bar2_rd_data             (fpga_tx_data               ),
448:     //**********************************************************************
449:     //from rx top
450:     //req rcv
451:     .i_mrd_tc                   (mrd_tc                     ),
452:     .i_mrd_attr                 (mrd_attr                   ),
453:     .i_mrd_length               (mrd_length                 ),
454:     .i_mrd_id                   (mrd_id                     ),
455:     .i_mrd_tag                  (mrd_tag                    ),
456:     .i_mrd_addr                 (mrd_addr                   ),
457: 
458:     .i_cpld_req_vld             (cpld_req_vld               ),
459:     .o_cpld_req_rdy             (cpld_req_rdy               ),
460:     .o_cpld_tx_rdy              (cpld_tx_rdy                ),
461:     //cpld rcv
462:     .i_cpld_rcv                 (cpld_rcv                   ),
463:     .i_cpld_tag                 (cpld_tag                   ),
464:     .o_tag_full                 (tag_full                   ),
465:     //rst tlp cnt
466:     .i_tx_restart               (tx_restart                 )
467:     //debug
468:     //.o_dbg_bus_mrd_tx           (dbg_bus_mrd_tx             ),
469:     //.o_dbg_bus_mwr_tx           (dbg_bus_mwr_tx             )
470: );
471: 
472: generate
473:     if (AXIS_SLAVE_NUM == 1)
474:     begin:axis_slave_num_1
475:         ips2l_pcie_dma_tlp_tx_mux #(
476:             .AXIS_SLAVE_NUM             (AXIS_SLAVE_NUM         )
477:         )
478:         u_pcie_dma_tlp_tx_mux
479:         (
480:             .clk                         (clk                   ),   //gen1:62.5MHz,gen2:125MHz
481:             .rst_n                       (rst_n                 ),
482:             //**********************************************************************
483:             //from dma
484:             //axis_slave0 interface
485:             .o_dma_axis_slave0_trdy      (dma_axis_slave0_trdy  ),
486:             .i_dma_axis_slave0_tvld      (dma_axis_slave0_tvld  ),
487:             .i_dma_axis_slave0_tdata     (dma_axis_slave0_tdata ),
488:             .i_dma_axis_slave0_tlast     (dma_axis_slave0_tlast ),
489:             .i_dma_axis_slave0_tuser     (dma_axis_slave0_tuser ),
490:             //axis_slave1 interface
491:             .o_dma_axis_slave1_trdy      (dma_axis_slave1_trdy  ),
492:             .i_dma_axis_slave1_tvld      (dma_axis_slave1_tvld  ),
493:             .i_dma_axis_slave1_tdata     (dma_axis_slave1_tdata ),
494:             .i_dma_axis_slave1_tlast     (dma_axis_slave1_tlast ),
495:             .i_dma_axis_slave1_tuser     (dma_axis_slave1_tuser ),
496:             //axis_slave2 interface
497:             .o_dma_axis_slave2_trdy      (dma_axis_slave2_trdy  ),
498:             .i_dma_axis_slave2_tvld      (dma_axis_slave2_tvld  ),
499:             .i_dma_axis_slave2_tdata     (dma_axis_slave2_tdata ),
500:             .i_dma_axis_slave2_tlast     (dma_axis_slave2_tlast ),
501:             .i_dma_axis_slave2_tuser     (dma_axis_slave2_tuser ),
502:             //credit interface
503:             //from pcie
504:             .i_cfg_ido_req_en            (i_cfg_ido_req_en      ),
505:             .i_cfg_ido_cpl_en            (i_cfg_ido_cpl_en      ),
506:             .i_xadm_ph_cdts              (i_xadm_ph_cdts        ),
507:             .i_xadm_pd_cdts              (i_xadm_pd_cdts        ),
508:             .i_xadm_nph_cdts             (i_xadm_nph_cdts       ),
509:             .i_xadm_npd_cdts             (i_xadm_npd_cdts       ),
510:             .i_xadm_cplh_cdts            (i_xadm_cplh_cdts      ),
511:             .i_xadm_cpld_cdts            (i_xadm_cpld_cdts      ),
512:             //pcie_axis_slave0
513:             .i_pcie_axis_slave_trdy      (i_axis_slave0_trdy    ),
514:             .o_pcie_axis_slave_tvld      (o_axis_slave0_tvld    ),
515:             .o_pcie_axis_slave_tdata     (o_axis_slave0_tdata   ),
516:             .o_pcie_axis_slave_tlast     (o_axis_slave0_tlast   ),
517:             .o_pcie_axis_slave_tuser     (o_axis_slave0_tuser   )
518:         );
519: 
520:         assign o_axis_slave1_tvld  = 1'b0;
521:         assign o_axis_slave1_tdata = 128'b0;
522:         assign o_axis_slave1_tlast = 1'b0;
523:         assign o_axis_slave1_tuser = 1'b0;
524: 
525:         assign o_axis_slave2_tvld  = 1'b0;
526:         assign o_axis_slave2_tdata = 128'b0;
527:         assign o_axis_slave2_tlast = 1'b0;
528:         assign o_axis_slave2_tuser = 1'b0;
529:     end
530:     else if (AXIS_SLAVE_NUM == 2)
531:     begin:axis_slave_num_2
532:         ips2l_pcie_dma_tlp_tx_mux #(
533:             .AXIS_SLAVE_NUM             (AXIS_SLAVE_NUM         )
534:         )
535:         u_pcie_dma_tlp_tx_mux
536:         (
537:             .clk                         (clk                   ),   //gen1:62.5MHz,gen2:125MHz
538:             .rst_n                       (rst_n                 ),
539:             //**********************************************************************
540:             //from dma
541:             //axis_slave0 interface
542:             .o_dma_axis_slave0_trdy      (                      ),
543:             .i_dma_axis_slave0_tvld      (1'b0                  ),
544:             .i_dma_axis_slave0_tdata     (128'b0                ),
545:             .i_dma_axis_slave0_tlast     (1'b0                  ),
546:             .i_dma_axis_slave0_tuser     (1'b0                  ),
547:             //axis_slave1 interface
548:             .o_dma_axis_slave1_trdy      (dma_axis_slave1_trdy  ),
549:             .i_dma_axis_slave1_tvld      (dma_axis_slave1_tvld  ),
550:             .i_dma_axis_slave1_tdata     (dma_axis_slave1_tdata ),
551:             .i_dma_axis_slave1_tlast     (dma_axis_slave1_tlast ),
552:             .i_dma_axis_slave1_tuser     (dma_axis_slave1_tuser ),
553:             //axis_slave2 interface
554:             .o_dma_axis_slave2_trdy      (dma_axis_slave2_trdy  ),
555:             .i_dma_axis_slave2_tvld      (dma_axis_slave2_tvld  ),
556:             .i_dma_axis_slave2_tdata     (dma_axis_slave2_tdata ),
557:             .i_dma_axis_slave2_tlast     (dma_axis_slave2_tlast ),
558:             .i_dma_axis_slave2_tuser     (dma_axis_slave2_tuser ),
559:             //credit interface
560:             //from pcie
561:             .i_cfg_ido_req_en            (i_cfg_ido_req_en      ),
562:             .i_cfg_ido_cpl_en            (i_cfg_ido_cpl_en      ),
563:             .i_xadm_ph_cdts              (i_xadm_ph_cdts        ),
564:             .i_xadm_pd_cdts              (i_xadm_pd_cdts        ),
565:             .i_xadm_nph_cdts             (i_xadm_nph_cdts       ),
566:             .i_xadm_npd_cdts             (i_xadm_npd_cdts       ),
567:             .i_xadm_cplh_cdts            (i_xadm_cplh_cdts      ),
568:             .i_xadm_cpld_cdts            (i_xadm_cpld_cdts      ),
569:             //pcie_axis_slave0
570:             .i_pcie_axis_slave_trdy      (i_axis_slave1_trdy    ),
571:             .o_pcie_axis_slave_tvld      (o_axis_slave1_tvld    ),
572:             .o_pcie_axis_slave_tdata     (o_axis_slave1_tdata   ),
573:             .o_pcie_axis_slave_tlast     (o_axis_slave1_tlast   ),
574:             .o_pcie_axis_slave_tuser     (o_axis_slave1_tuser   )
575:         );
576: 
577:         assign dma_axis_slave0_trdy = i_axis_slave0_trdy    ;
578:         assign o_axis_slave0_tvld   = dma_axis_slave0_tvld  ;
579:         assign o_axis_slave0_tdata  = dma_axis_slave0_tdata ;
580:         assign o_axis_slave0_tlast  = dma_axis_slave0_tlast ;
581:         assign o_axis_slave0_tuser  = dma_axis_slave0_tuser ;
582: 
583:         assign o_axis_slave2_tvld  = 1'b0;
584:         assign o_axis_slave2_tdata = 128'b0;
585:         assign o_axis_slave2_tlast = 1'b0;
586:         assign o_axis_slave2_tuser = 1'b0;
587:     end
588:     else if (AXIS_SLAVE_NUM == 3)
589:     begin:axis_slave_num_3
590:         assign dma_axis_slave0_trdy = i_axis_slave0_trdy    ;
591:         assign o_axis_slave0_tvld   = dma_axis_slave0_tvld  ;
592:         assign o_axis_slave0_tdata  = dma_axis_slave0_tdata ;
593:         assign o_axis_slave0_tlast  = dma_axis_slave0_tlast ;
594:         assign o_axis_slave0_tuser  = dma_axis_slave0_tuser ;
595: 
596:         assign dma_axis_slave1_trdy = i_axis_slave1_trdy    ;
597:         assign o_axis_slave1_tvld   = dma_axis_slave1_tvld  ;
598:         assign o_axis_slave1_tdata  = dma_axis_slave1_tdata ;
599:         assign o_axis_slave1_tlast  = dma_axis_slave1_tlast ;
600:         assign o_axis_slave1_tuser  = dma_axis_slave1_tuser ;
601: 
602:         assign dma_axis_slave2_trdy = i_axis_slave2_trdy    ;
603:         assign o_axis_slave2_tvld   = dma_axis_slave2_tvld  ;
604:         assign o_axis_slave2_tdata  = dma_axis_slave2_tdata ;
605:         assign o_axis_slave2_tlast  = dma_axis_slave2_tlast ;
606:         assign o_axis_slave2_tuser  = dma_axis_slave2_tuser ;
607:     end
608: endgenerate
609: 
610: endmodule
