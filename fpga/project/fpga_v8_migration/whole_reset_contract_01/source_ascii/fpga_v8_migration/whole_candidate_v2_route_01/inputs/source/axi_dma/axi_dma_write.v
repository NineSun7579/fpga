1: module axi_dma_write
2: 	#(
3: 		parameter WAIT_FOR_DATA = 0, // camera source supplies stored beat credits
4: 		parameter WD_LIMIT = 24'hFFFFFF,
5: 		parameter 		BURST_LEN 	= 8		,
6: 		parameter       ID_WIDTH  	= 4		,
7: 		parameter       DATA_WIDTH 	= 128	,
8: 		parameter       KEEP_WIDTH  = DATA_WIDTH / 8	
9: 	)
10: 	(
11: 	input 				clk 			,    // Clock
12: 	input 				rst 			,    // Synchronous reset active high
13: 	
14: 	//cmd interface
15: 	input       	 					cmd_valid		,
16: 	input 			[31:0] 				cmd_addr		,
17: 	input 			[31:0] 				cmd_len			,
18: 	input			[ID_WIDTH - 1:0]    cmd_id          ,
19: 	output reg  	    				cmd_ready		,
20: 
21: 	input [15:0] data_in_available, // complete beats already stored upstream
22: 	input abort_req, // sticky source fault, held until retirement
23:     output reg data_in_abort, // failed command, all AXI obligations retired
24: 
25: 	//trans data in
26: 	input 			[DATA_WIDTH - 1:0]  data_in      	,
27: 	input			[KEEP_WIDTH - 1:0]	data_in_keep	,
28: 	input         						data_in_valid	,
29: 	output reg                          data_in_last    ,
30: 	output        						data_in_ready	,
31: 
32: 	//axi w
33: 	output reg		[ID_WIDTH - 1:0]   			m_axi_awid   	,
34: 	output reg		[31:0]  					m_axi_awaddr 	,
35: 	output reg		[7:0]   					m_axi_awlen  	,
36: 	output 			[2:0]   					m_axi_awsize 	,
37: 	output 			[1:0]   					m_axi_awburst	,
38: 	output 		    	    					m_axi_awlock 	,
39: 	output 			[3:0]   					m_axi_awcache	,
40: 	output 			[2:0]   					m_axi_awprot	,
41: 	output reg		        					m_axi_awvalid	,
42: 	input  		 	        					m_axi_awready	,
43: 	output 			[DATA_WIDTH - 1:0] 			m_axi_wdata		,
44: 	output 			[KEEP_WIDTH - 1:0]  		m_axi_wstrb		,
45: 	output 			        					m_axi_wlast		,
46: 	output 			        					m_axi_wvalid	,
47: 	input  			        					m_axi_wready	,
48: 	input  			[ID_WIDTH - 1:0]   			m_axi_bid  		,
49: 	input  			[1:0]   					m_axi_bresp 	,
50: 	input  			        					m_axi_bvalid	,
51: 	output 			        					m_axi_bready	
52: 
53: );
54: 
55: 
56: localparam AXI_BURST_SIZE = $clog2(KEEP_WIDTH); //log2(DATA_WIDTH / 8)
57: 
58: // [WD 2026-09-18] transmit watchdog state
59: reg        abort_r;
60: reg [23:0] wd_cnt;
61: wire       w_progress;
62: wire       abort_done;
63: 
64: wire [DATA_WIDTH - 1:0] 		t_m_axi_wdata;	
65: wire [KEEP_WIDTH - 1:0]  		t_m_axi_wstrb;	
66: wire         					t_m_axi_wlast;	
67: wire         					t_m_axi_wvalid;
68: wire         					t_m_axi_wready;
69: 
70: //common para
71: assign m_axi_awsize 	= 		AXI_BURST_SIZE	;
72: assign m_axi_awburst 	= 		2'b01			;
73: assign m_axi_awlock 	= 		1'b0			;
74: assign m_axi_awcache 	= 		4'b0011			;
75: assign m_axi_awprot 	= 		3'b000			;
76: 
77: 
78: wire [7:0] burst_len    ;
79: wire [7:0] max_burst_len;
80: 
81: //cmd
82: reg [31:0] addr;
83: reg [31:0] len;
84: reg        trans;
85: 
86: always @(posedge clk) begin 
87: 	if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin
88: 		addr <= cmd_addr;
89: 	end
90: 	else begin
91: 		if((m_axi_awvalid == 1'b1) && (m_axi_awready == 1'b1))begin
92: 			addr <= addr + ((m_axi_awlen + 1'b1) << AXI_BURST_SIZE);
93: 		end
94: 	end
95: end
96: 
97: always @(posedge clk) begin 
98: 	if(rst == 1'b1)begin
99: 		len <= 32'd0;
100: 	end
101: 	else if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin
102: 		len <= cmd_len[31:AXI_BURST_SIZE] + (|cmd_len[AXI_BURST_SIZE - 1:0]);
103: 	end
104: 	else begin
105: 		if((m_axi_awvalid == 1'b1) && (m_axi_awready == 1'b1))begin
106: 			len <= len - (m_axi_awlen + 1'b1);
107: 		end
108: 		else if(abort_done == 1'b1)begin
109: 			len <= 32'd0;       // Discard only unissued remainder after real B.
110: 		end
111: 	end
112: end
113: always @(posedge clk)begin
114: 	if(rst == 1'b1)begin
115: 		trans <= 1'b0;
116: 	end
117: 	else begin
118: 		if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin
119: 			trans <= 1'b1;
120: 		end
121: 		else begin
122: 			if((m_axi_bready == 1'b1) && (m_axi_bvalid == 1'b1) && (len == 32'd0))begin
123: 				trans <= 1'b0;
124: 			end
125: 			else if(abort_done == 1'b1)begin
126: 				trans <= 1'b0;      // Aborted burst has completed external W and B.
127: 			end
128: 		end
129: 	end
130: end
131: 
132: always @(posedge  clk)begin
133: 	if(rst == 1'b1)begin
134: 		cmd_ready <= 1'b0;
135: 	end
136: 	else begin
137: 		if(trans == 1'b0)begin
138: 			if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin
139: 				cmd_ready <= 1'b0;
140: 			end
141: 			else begin
142: 				cmd_ready <= 1'b1;
143: 			end
144: 		end
145: 		else begin
146: 			cmd_ready <= 1'b0;
147: 		end
148: 	end
149: end
150: 
151: //aw
152: 
153: reg burst_trans;
154: assign burst_len     = len > BURST_LEN ? BURST_LEN : len;
155: // Do not reserve the shared DDR owner while waiting for future pixels.
156: // Once advertised, AW remains irrevocable even if an abort arrives.
157: wire source_burst_ready = !WAIT_FOR_DATA ||
158:                          (data_in_valid && data_in_available >= max_burst_len);
159: wire waiting_source = WAIT_FOR_DATA && trans && !burst_trans &&
160:                       !m_axi_awvalid && (len != 0) && !source_burst_ready;
161: reg [15:0] available_q;
162: always @(posedge clk) begin
163:     if(rst) available_q <= 0;
164:     else available_q <= data_in_available;
165: end
166: assign max_burst_len = (((addr & 12'hfff) + (burst_len << AXI_BURST_SIZE )) >> 12)  != 0 ? (13'h1000 - (addr & 12'hfff)) >> AXI_BURST_SIZE : burst_len;
167: always@(posedge clk)begin
168: 	if(rst == 1'b1)begin
169: 		burst_trans <= 1'b0;
170: 	end
171: 	else begin
172: 		if((m_axi_awvalid == 1'b1) && (m_axi_awready == 1'b1))begin
173: 			burst_trans <= 1'b1;
174: 		end
175: 		else begin
176: 			// if((m_axi_wvalid == 1'b1) && (m_axi_wready == 1'b1) && (m_axi_wlast == 1'b1))begin
177: 			if((m_axi_bvalid == 1'b1) && (m_axi_bready == 1'b1))begin
178: 				burst_trans <= 1'b0;
179: 			end
180: 		end
181: 	end
182: end
183: always @(posedge clk)begin
184: 	if(rst == 1'b1)begin
185: 		m_axi_awvalid <= 1'b0;
186: 	end
187: 	else begin
188: 		if((m_axi_awvalid == 1'b1) && (m_axi_awready == 1'b1))begin
189: 			m_axi_awvalid <= 1'b0;
190: 		end
191: 		else begin
192: 			if((trans == 1'b1) && (burst_trans == 1'b0) && (len != 32'd0) && (abort_r == 1'b0) && !abort_req && source_burst_ready)begin
193: 				m_axi_awvalid <= 1'b1;
194: 			end
195: 		end
196: 	end
197: end
198: 
199: always @(posedge clk)begin
200: 	if(!m_axi_awvalid) m_axi_awlen <= max_burst_len - 8'd1;
201: end
202: always @(posedge clk)begin
203: 	if(!m_axi_awvalid) m_axi_awaddr <= addr;
204: end
205: always @(posedge clk) begin 
206: 	if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin
207: 		m_axi_awid <= cmd_id;
208: 	end
209: end
210: //w
211: reg [7:0] act_burst_len;
212: always@ (posedge clk)begin
213: 	if(rst == 1'b1)begin
214: 		act_burst_len <= 8'd0;
215: 	end
216: 	else begin
217: 		if((m_axi_awvalid == 1'b1) && (m_axi_awready == 1'b1))begin
218: 			act_burst_len <= m_axi_awlen + 8'd1;
219: 		end
220: 		else begin
221: 			if((t_m_axi_wvalid == 1'b1) && (t_m_axi_wready == 1'b1))begin
222: 				act_burst_len <= act_burst_len - 8'd1;
223: 			end
224: 		end
225: 	end
226: end
227: 
228: // [WD 2026-09-18] ------------------------------------------------------------------
229: // The DVP stream can deliver fewer 128-bit beats than CAM_DATA_LEN (CDC FIFO
230: // overflow drops pixels and cannot back-pressure the sensor). A frame's AXI
231: // burst then never completes: trans sticks at 1, cmd_ready stays low and the
232: // frame FSM deadlocks forever (measured: state=ADDR, axi_cnt=0, 0 frames).
233: //
234: // Recovery: if there is no W-beat progress for ~0.17 s while a write is in
235: // flight, close the open burst with dummy beats. AXI forbids cancelling an
236: // accepted AW, so we must still supply awlen beats; we just no longer consume
237: // real camera data. After the B response is absorbed, trans/len clear and the
238: // next frame's command is accepted again (only the bad frame is lost).
239: assign w_progress = (t_m_axi_wvalid == 1'b1) && (t_m_axi_wready == 1'b1);
240: 
241: always @(posedge clk) begin
242:     if(rst || abort_r) wd_cnt <= 0;
243:     else if(waiting_source) begin
244:         if(data_in_available != available_q) wd_cnt <= 0;
245:         else if(wd_cnt != 24'hFFFFFF) wd_cnt <= wd_cnt + 1'b1;
246:     end
247:     else if((rst == 1'b1) || (burst_trans == 1'b0) || (abort_r == 1'b1) || (w_progress == 1'b1) || data_in_valid || !t_m_axi_wready)
248: 		wd_cnt <= 24'd0;
249: 	else if(wd_cnt != 24'hFFFFFF)
250: 		wd_cnt <= wd_cnt + 24'd1;
251: end
252: 
253: // Timeout may fill an accepted burst, but cannot cancel an advertised AW
254: // or fabricate completion. Waiting AW and waiting B retain their ledger.
255: always @(posedge clk) begin
256:     if(rst == 1'b1)
257:         abort_r <= 1'b0;
258:     else if(abort_done == 1'b1)
259:         abort_r <= 1'b0;
260:     else if(trans && abort_req)
261:         abort_r <= 1'b1;
262:     else if(waiting_source && (wd_cnt == WD_LIMIT))
263:         abort_r <= 1'b1; // no AW exists: retire locally without owning DDR
264:     else if(!abort_r && burst_trans && (act_burst_len != 0)
265:             && !data_in_valid && t_m_axi_wready && !w_progress && (wd_cnt == WD_LIMIT))
266:         abort_r <= 1'b1;
267: end
268: 
269: // BREADY is asserted only after the external final W handshake below.
270: wire b_fire = m_axi_bvalid && m_axi_bready;
271: wire failed = abort_r || abort_req || (b_fire && m_axi_bresp[1]);
272: assign abort_done = trans && failed &&
273:                     (b_fire || (abort_r && !burst_trans && !m_axi_awvalid));
274: // ---------------------------------------------------------------------------------
275: 
276: stream_pipe #(
277:   .DATA_WIDTH 	(DATA_WIDTH+1+KEEP_WIDTH)	
278: ) stream_pipe_3(
279:   .dataIn_valid     (t_m_axi_wvalid),
280:   .dataIn_ready     (t_m_axi_wready),
281:   .dataIn_payload   ({t_m_axi_wdata, t_m_axi_wstrb, t_m_axi_wlast}),
282:   .dataOut_valid    (m_axi_wvalid),
283:   .dataOut_ready    (m_axi_wready),
284:   .dataOut_payload  ({m_axi_wdata, m_axi_wstrb, m_axi_wlast}),
285:   .clk              (clk),
286:   .reset            (rst)
287: );
288: 
289: assign data_in_ready = abort_r ? 1'b0
290:                                : (t_m_axi_wready && act_burst_len > 8'd0);
291: assign t_m_axi_wvalid  = abort_r ? (act_burst_len > 8'd0)
292:                                  : (data_in_valid && act_burst_len > 8'd0);
293: assign t_m_axi_wdata   = abort_r ? {DATA_WIDTH{1'b0}} : data_in;
294: assign t_m_axi_wlast   = (act_burst_len == 8'd1);
295: assign t_m_axi_wstrb   = abort_r ? {KEEP_WIDTH{1'b0}} : data_in_keep;
296: 
297: //b
298: reg w_done;
299: always @(posedge clk) begin
300: 	if(rst == 1'b1) begin
301: 		w_done <= 1'b0;
302: 	end
303: 	else begin
304: 		if((m_axi_wvalid == 1'b1) && (m_axi_wready == 1'b1) && (m_axi_wlast == 1'b1)) begin
305: 			w_done <= 1'b1;
306: 		end
307: 		else begin
308: 			if((m_axi_bvalid == 1'b1) && (m_axi_bready == 1'b1)) begin
309: 				w_done <= 1'b0;
310: 			end
311: 		end
312: 	end
313: end
314: assign m_axi_bready = w_done;
315: 
316: // Success and failure are mutually exclusive and follow real external B.
317: always @(posedge clk) begin
318:     if(rst) begin
319:         data_in_last <= 1'b0;
320:         data_in_abort <= 1'b0;
321:     end else begin
322:         data_in_last <= trans && b_fire && (len == 0) && !failed;
323:         data_in_abort <= abort_done;
324:     end
325: end
326: 
327: endmodule
