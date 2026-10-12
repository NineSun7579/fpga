1: //\xbf\xe7\xca\xb1\xd6\xd3\xd3\xf2
2: module ov5640_cdc #(
3:     parameter DATA_WIDTH = 24,
4:     parameter DEVICE = "PG"
5: )
6: (
7:     // [CDC_PIXEL] Read-only per-frame snapshots, all in video_clk domain.
8:     output reg [31:0] dbg_cdc_input,
9:     output reg [31:0] dbg_cdc_output,
10:     output reg [31:0] dbg_cdc_drop,
11:     output reg [31:0] dbg_cdc_seq,
12:     input         cam_clk    /*synthesis PAP_MARK_DEBUG="1"*/,          //???????
13:     input         cam_rst    /*synthesis PAP_MARK_DEBUG="1"*/,
14: 
15:     input [DATA_WIDTH-1 : 0]   s_data     /*synthesis PAP_MARK_DEBUG="1"*/,
16:     input                      s_valid    /*synthesis PAP_MARK_DEBUG="1"*/,
17:     input                      s_hsync    /*synthesis PAP_MARK_DEBUG="1"*/,
18:     input                      s_vsync    /*synthesis PAP_MARK_DEBUG="1"*/,
19: 
20:     input                      video_clk  /*synthesis PAP_MARK_DEBUG="1"*/,
21:     input                      video_rst  /*synthesis PAP_MARK_DEBUG="1"*/,
22:     output [DATA_WIDTH-1 : 0]  video_data /*synthesis PAP_MARK_DEBUG="1"*/,
23:     output                     video_valid/*synthesis PAP_MARK_DEBUG="1"*/,
24:     output                     video_hsync/*synthesis PAP_MARK_DEBUG="1"*/,
25:     output                     video_vsync/*synthesis PAP_MARK_DEBUG="1"*/
26: );
27: 
28: 
29: 
30: 
31: 
32: 
33: 
34: 
35:     // reg s_vsync_d, s_hsync_d;
36:     // always @(posedge cam_clk) begin
37:     //     s_vsync_d <= s_vsync;
38:     //     s_hsync_d <= s_hsync;
39:     // end
40:     // wire vsync_rise = s_vsync & ~s_vsync_d;
41:     // wire hsync_rise = s_hsync & ~s_hsync_d;
42: 
43: 
44: 
45: 
46: 
47:     // reg [31 : 0] cnt_cdc_in/*synthesis PAP_MARK_DEBUG="1"*/;
48:     // always @(posedge cam_clk) begin
49:     //     if(cam_rst)begin
50:     //         cnt_cdc_in <= 32'd0;
51:     //     end
52:     //     else if(vsync_rise)begin
53:     //         cnt_cdc_in <= 32'd0;
54:     //     end
55:     //     else if(s_valid)begin
56:     //         cnt_cdc_in <= cnt_cdc_in + 32'd1;
57:     //     end
58:     // end
59: 
60: 
61:     // reg [31 : 0] cnt_cdc_in_h/*synthesis PAP_MARK_DEBUG="1"*/;
62:     // always @(posedge cam_clk) begin
63:     //     if(cam_rst)begin
64:     //         cnt_cdc_in_h <= 32'd0;
65:     //     end
66:     //     else if(hsync_rise)begin
67:     //         cnt_cdc_in_h <= 32'd0;
68:     //     end
69:     //     else if(s_valid)begin
70:     //         cnt_cdc_in_h <= cnt_cdc_in_h + 32'd1;
71:     //     end
72:     // end
73: 
74:     // reg not_1920/*synthesis PAP_MARK_DEBUG="1"*/;
75:     // always @(posedge cam_clk) begin
76:     //     if(cam_rst)begin
77:     //         not_1920 <= 1'b0;
78:     //     end        
79:     //     else if(vsync_rise) begin
80:     //         not_1920 <= 1'b0;
81:     //     end
82:     //     else if(cnt_cdc_in_h != 32'd1920 && hsync_rise && cnt_cdc_in_h != 32'd0)begin
83:     //         not_1920 <= 1'b1;
84:     //     end
85:     // end
86: 
87: 
88: 
89:     // [FIX 2026-09-18] The original code pushed {vsync,href} through a FIFO whose
90:     // write-enable was `(|vhsync_in) | s_valid`. That never records the LOW phase
91:     // of hsync/vsync, so the read side saw a scrambled, glitchy sync stream
92:     // (measured vsync at ~6x the true frame rate). The spurious vsync resets
93:     // ov5640_ddr_w axi_cnt mid-frame, so axi_data_last never fired, no frame ever
94:     // completed and the write engine streamed garbage forever.
95:     //
96:     // vsync/hsync are slow single-bit levels here (a vsync pulse spans thousands of
97:     // cam_pclk cycles, far more than 2 video_clk cycles), so a plain 2-stage
98:     // synchroniser is both simpler and correct. The pixel data keeps using the
99:     // asynchronous FIFO below; only the sync levels change.
100:     reg [1:0] vsync_sync, hsync_sync;
101:     always @(posedge video_clk) begin
102:         if (video_rst) begin
103:             vsync_sync <= 2'b0;
104:             hsync_sync <= 2'b0;
105:         end
106:         else begin
107:             vsync_sync <= {vsync_sync[0], s_vsync};
108:             hsync_sync <= {hsync_sync[0], s_hsync};
109:         end
110:     end
111: 
112:     assign video_hsync = hsync_sync[1];
113:     assign video_vsync = vsync_sync[1];
114: 
115: 
116: 
117: 
118: 
119: 
120: 
121: 
122: 
123: 
124: 
125: 
126: 
127: 
128: 
129: 
130: 
131:     wire empty;
132:     wire full ;
133:     wire rd_rst_busy;
134:     wire wr_rst_busy;
135:     wire data_valid ;
136:     wire wr_en;
137:     wire rd_en;
138: 
139:     wire [DATA_WIDTH-1 : 0] dout;
140: 
141: 
142:     wire [DATA_WIDTH-1 : 0] din = s_data;
143:     assign wr_en = !full & s_valid;
144: 
145:     assign rd_en       = !empty;
146:     assign video_data  = dout[DATA_WIDTH-1 : 0];
147: 
148: 
149: 
150: 
151:     reg video_valid_r;
152:     always @(posedge video_clk) begin
153:         if (video_rst) video_valid_r <= 1'b0;
154:         else video_valid_r <= rd_en;
155:     end
156:     assign video_valid = video_valid_r;
157:     ov5640_cdc_fifo ov5640_cdc_fifo (
158:       .wr_clk(cam_clk),                // input
159:       .wr_rst(cam_rst),                // input
160:       .wr_en(wr_en),                  // input
161:       .wr_data(din),              // input [24:0]
162:       .wr_full(full),              // output
163:     
164:       .rd_clk(video_clk),                // input
165:       .rd_en(rd_en),                  // input
166:       .rd_data(dout),              // output [24:0]
167:       .rd_empty(empty),            // output
168:       .rd_rst(video_rst),                // input
169:       .almost_full(),      // output
170:       .almost_empty()     // output
171:     );
172: 
173: 
174: 
175: 
176: 
177:     // wire video_vsync_rise = vsync_d & ~vsync_dd;
178:     // wire video_hsync_rise = hsync_d & ~hsync_dd;
179: 
180: 
181:     // reg [31 : 0] cnt_cdc_out/*synthesis PAP_MARK_DEBUG="1"*/;
182:     // always @(posedge video_clk) begin   
183:     //     if(video_rst)begin
184:     //         cnt_cdc_out <= 32'd0;
185:     //     end
186:     //     else if(video_vsync_rise)begin
187:     //         cnt_cdc_out <= 32'd0;
188:     //     end
189:     //     else if(video_valid)begin
190:     //         cnt_cdc_out <= cnt_cdc_out + 32'd1;
191:     //     end
192:     // end
193: 
194: 
195:     // reg [31 : 0] cnt_cdc_out_h/*synthesis PAP_MARK_DEBUG="1"*/;
196:     // always @(posedge video_clk) begin
197:     //     if(video_rst)begin
198:     //         cnt_cdc_out_h <= 32'd0;
199:     //     end
200:     //     else if(video_hsync_rise)begin
201:     //         cnt_cdc_out_h <= 32'd0;
202:     //     end
203:     //     else if(video_valid)begin
204:     //         cnt_cdc_out_h <= cnt_cdc_out_h + 32'd1;
205:     //     end
206:     // end
207: 
208: 
209: 
210:     // Diagnostic-only source snapshot: data is held for a complete frame.
211:     // Two data stages precede the three-stage toggle notification. This is
212:     // a bundled-data transfer, not a live asynchronous binary counter read.
213:     reg src_vs_q, src_toggle;
214:     reg [31:0] src_count, src_drop, src_seq;
215:     reg [95:0] src_snapshot;
216:     always @(posedge cam_clk or posedge cam_rst) begin
217:         if (cam_rst) begin
218:             src_vs_q <= 0;
219:             src_toggle <= 0;
220:             src_count <= 0;
221:             src_drop <= 0;
222:             src_seq <= 0;
223:             src_snapshot <= 0;
224:         end else begin
225:             src_vs_q <= s_vsync;
226:             if (s_vsync && !src_vs_q) begin
227:                 src_snapshot <= {src_seq + 32'd1, src_drop, src_count};
228:                 src_toggle <= ~src_toggle;
229:                 src_seq <= src_seq + 1'b1;
230:                 src_count <= {31'd0, s_valid};
231:                 src_drop <= {31'd0, (s_valid && full)};
232:             end else begin
233:                 if (s_valid) src_count <= src_count + 1'b1;
234:                 if (s_valid && full) src_drop <= src_drop + 1'b1;
235:             end
236:         end
237:     end
238: 
239:     reg [95:0] snapshot_s1, snapshot_s2;
240:     reg [2:0] toggle_sync;
241:     reg toggle_seen, out_vs_q;
242:     reg [31:0] out_count, out_snapshot;
243:     always @(posedge video_clk) begin
244:         if (video_rst) begin
245:             snapshot_s1 <= 0;
246:             snapshot_s2 <= 0;
247:             toggle_sync <= 0;
248:             toggle_seen <= 0;
249:             out_vs_q <= 0;
250:             out_count <= 0;
251:             out_snapshot <= 0;
252:             dbg_cdc_input <= 0;
253:             dbg_cdc_output <= 0;
254:             dbg_cdc_drop <= 0;
255:             dbg_cdc_seq <= 0;
256:         end else begin
257:             snapshot_s1 <= src_snapshot;
258:             snapshot_s2 <= snapshot_s1;
259:             toggle_sync <= {toggle_sync[1:0], src_toggle};
260:             out_vs_q <= video_vsync;
261:             if (video_vsync && !out_vs_q) begin
262:                 out_snapshot <= out_count;
263:                 out_count <= {31'd0, video_valid};
264:             end else if (video_valid) out_count <= out_count + 1'b1;
265:             if (toggle_sync[2] != toggle_seen) begin
266:                 toggle_seen <= toggle_sync[2];
267:                 dbg_cdc_input <= snapshot_s2[31:0];
268:                 dbg_cdc_drop <= snapshot_s2[63:32];
269:                 dbg_cdc_seq <= snapshot_s2[95:64];
270:                 dbg_cdc_output <= out_snapshot;
271:             end
272:         end
273:     end
274: 
275: endmodule
