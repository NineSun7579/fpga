1: // Candidate copy of production ov5640_ddr. The three original w_* modules
2: // are instantiated without modifications. Fixed capture layout; no runtime
3: // address/length configuration. lease_block only extends engine_busy at w_en.
4: module fpga_v8_capture_ov5640_ddr #(
5:     parameter DATA_WIDTH = 16,
6:     parameter AXI_DATA_WIDTH = 128,
7:     parameter CAM_DATA_LEN = 38400,
8:     parameter [31:0] BANK0_ADDR = 32'h01800000,
9:     parameter [31:0] BANK1_ADDR = 32'h01a00000,
10:     parameter DEVICE = "PG"
11: )(
12:     input axi_clk, input axi_rst, input epoch_start, input lease_block,
13:     input dma_abort, output dma_abort_req, input dma_done,
14:     output [15:0] axi_data_available, input axi_cam_en,
15:     input [DATA_WIDTH-1:0] s_data, input s_data_valid, input s_hsync, input s_vsync,
16:     output [AXI_DATA_WIDTH-1:0] axi_data,
17:     output axi_data_valid, output axi_data_last, input axi_data_ready,
18:     output [31:0] axi_cmd_addr, output [31:0] axi_cmd_len,
19:     output axi_cmd_valid, input axi_cmd_ready,
20:     output [1:0] xdma_req, input [1:0] xdma_ack,
21:     output admitted_sof, output capture_bank, output publish,
22:     output [31:0] publish_seq, output retired_error, output engine_idle,
23:     output capture_flush_o, output frame_good_o, output capture_overflow_o,
24:     output reg [31:0] dbg_fault_snapshot, output [31:0] dbg_reject_counts,
25:     output reg [31:0] dbg_input_pixels, output [31:0] dbg_axi_cnt,
26:     output [31:0] dbg_axi_num, output [31:0] dbg_zdin, output [31:0] dbg_zout,
27:     output [31:0] dbg_state, output [31:0] dbg_last_cnt, output [31:0] dbg_wd_cnt
28: );
29:     wire camera_rst = axi_rst | epoch_start;
30:     localparam LEN_WIDTH = $clog2(CAM_DATA_LEN)+1;
31:     localparam [LEN_WIDTH-1:0] cam_data_len = CAM_DATA_LEN;
32:     wire [DATA_WIDTH-1:0] m_data;
33:     wire m_data_valid, m_hsync, m_vsync;
34:     wire [AXI_DATA_WIDTH-1:0] w_data, tag_data;
35:     wire [15:0] w_available;
36:     wire w_valid, w_last, w_ready, frame_active, tag_active, engine_busy, w_ping_o;
37:     reg [2:0] flush_count;
38:     wire capture_flush = flush_count != 0;
39:     reg capture_open, capture_bad;
40:     reg [31:0] pixel_count, pixel_limit;
41:     reg raw_vsync_q;
42:     wire raw_sof = s_vsync && !raw_vsync_q;
43:     wire capture_overflow;
44:     wire capture_complete = capture_open && pixel_count == pixel_limit;
45:     wire frame_good = capture_complete && !capture_bad && !capture_overflow;
46:     wire capture_stop = capture_flush || capture_bad || capture_complete;
47:     assign dma_abort_req = capture_bad;
48:     assign admitted_sof = m_vsync;
49:     assign capture_bank = w_ping_o;
50:     assign publish = dma_done && dbg_state[2:0] == 3'd6 && frame_good && !dma_abort;
51:     assign publish_seq = dbg_last_cnt + 32'd1;
52:     assign retired_error = dma_abort || (dma_done && frame_active && !frame_good);
53:     assign engine_idle = !engine_busy && !capture_flush && !m_vsync;
54:     assign capture_flush_o = capture_flush;
55:     assign frame_good_o = frame_good;
56:     assign capture_overflow_o = capture_overflow;
57:     reg [15:0] diag_overflows, diag_shorts;
58:     reg [31:0] diag_input_count;
59:     wire diag_short = raw_sof && !capture_complete;
60:     wire diag_fault = capture_open && !capture_flush && !capture_bad &&
61:                       !m_vsync && (capture_overflow || diag_short);
62:     assign dbg_reject_counts = {diag_overflows, diag_shorts};
63:     always @(posedge axi_clk) begin
64:         if (camera_rst) begin
65:             dbg_fault_snapshot <= 0;
66:             diag_overflows <= 0;
67:             diag_shorts <= 0;
68:             diag_input_count <= 0;
69:             dbg_input_pixels <= 0;
70:         end else begin
71:             if (raw_sof) begin
72:                 dbg_input_pixels <= diag_input_count;
73:                 diag_input_count <= s_data_valid ? 1 : 0;
74:             end else if (s_data_valid) diag_input_count <= diag_input_count + 1'b1;
75:             if (diag_fault) begin
76:                 dbg_fault_snapshot <= {capture_overflow, diag_short, 1'b0,
77:                                       !frame_active, pixel_count[27:0]};
78:                 if (capture_overflow) diag_overflows <= diag_overflows + 1'b1;
79:                 if (diag_short) diag_shorts <= diag_shorts + 1'b1;
80:             end else if (dma_abort && !capture_bad)
81:                 dbg_fault_snapshot <= {2'b00, 1'b1, !frame_active, pixel_count[27:0]};
82:         end
83:     end
84:     always @(posedge axi_clk) begin
85:         if (camera_rst) begin flush_count <= 4; raw_vsync_q <= 0; end
86:         else begin
87:             raw_vsync_q <= s_vsync;
88:             if (dma_abort || (dma_done && (!frame_active || !frame_good))) flush_count <= 4;
89:             else if (capture_flush) flush_count <= flush_count - 1'b1;
90:         end
91:     end
92:     always @(posedge axi_clk) begin
93:         if (camera_rst || capture_flush) begin
94:             capture_open <= 0; capture_bad <= 0; pixel_count <= 0; pixel_limit <= 0;
95:         end else if (m_vsync) begin
96:             capture_open <= 1;
97:             capture_bad <= cam_data_len == 0;
98:             pixel_count <= 0;
99:             pixel_limit <= (cam_data_len * AXI_DATA_WIDTH) / DATA_WIDTH;
100:         end else if (capture_open) begin
101:             if (m_data_valid) pixel_count <= pixel_count + 1'b1;
102:             if (capture_overflow || (raw_sof && !capture_complete)) capture_bad <= 1;
103:         end
104:     end
105:     ov5640_ddr_w_en #(.DATA_WIDTH(DATA_WIDTH)) ov5640_ddr_w_en (
106:         .capture_stop(capture_stop),
107:         .engine_busy(engine_busy | capture_flush | lease_block |
108:                      (DATA_WIDTH != 16) | (AXI_DATA_WIDTH != 128)),
109:         .axi_clk(axi_clk), .axi_rst(camera_rst), .axi_cam_en(axi_cam_en),
110:         .frame_pending(xdma_req), .s_data(s_data), .s_data_valid(s_data_valid),
111:         .s_hsync(s_hsync), .s_vsync(s_vsync), .m_data(m_data),
112:         .m_data_valid(m_data_valid), .m_hsync(m_hsync), .m_vsync(m_vsync)
113:     );
114:     ov5640_ddr_w #(.DATA_WIDTH(DATA_WIDTH), .AXI_DATA_WIDTH(AXI_DATA_WIDTH),
115:         .CAM_DATA_LEN(CAM_DATA_LEN), .DEVICE(DEVICE)) ov5640_ddr_w (
116:         .axi_clk(axi_clk), .axi_rst(camera_rst), .capture_flush(capture_flush),
117:         .capture_overflow(capture_overflow), .axi_data_available(w_available),
118:         .data_len(cam_data_len), .s_data(m_data), .s_data_valid(m_data_valid),
119:         .s_hsync(m_hsync), .s_vsync(m_vsync), .axi_data(w_data),
120:         .axi_data_valid(w_valid), .axi_data_last(w_last), .axi_data_ready(w_ready),
121:         .dbg_axi_cnt(dbg_axi_cnt), .dbg_axi_num(dbg_axi_num),
122:         .dbg_zdin(dbg_zdin), .dbg_zout(dbg_zout)
123:     );
124:     assign axi_data_available = tag_active ? 16'd1 : (frame_active ? w_available : 16'd0);
125:     assign axi_data = tag_active ? tag_data : w_data;
126:     assign axi_data_valid = tag_active | (frame_active & w_valid);
127:     assign axi_data_last = w_last;
128:     assign w_ready = axi_data_ready & frame_active;
129:     ov5640_ddr_w_ctrl #(.AXI_ADDR_WIDTH(32), .AXI_LEN_WIDTH(32),
130:         .AXI_DATA_WIDTH(AXI_DATA_WIDTH), .CAM_DATA_LEN(CAM_DATA_LEN)) ov5640_ddr_w_ctrl (
131:         .axi_clk(axi_clk), .axi_rst(camera_rst), .cam_data_addr_1(BANK0_ADDR),
132:         .cam_data_addr_2(BANK1_ADDR), .cam_data_len(cam_data_len), .s_vsync(m_vsync),
133:         .dma_abort(dma_abort), .frame_good(frame_good), .dma_done(dma_done),
134:         .axi_cmd_addr(axi_cmd_addr), .axi_cmd_len(axi_cmd_len),
135:         .axi_cmd_valid(axi_cmd_valid), .axi_cmd_ready(axi_cmd_ready),
136:         .frame_active(frame_active), .tag_active(tag_active), .tag_data(tag_data),
137:         .tag_ready(axi_data_ready), .engine_busy(engine_busy), .w_ping_o(w_ping_o),
138:         .dbg_state(dbg_state), .dbg_last_cnt(dbg_last_cnt), .dbg_wd_cnt(dbg_wd_cnt),
139:         .xdma_req(xdma_req), .xdma_ack(xdma_ack)
140:     );
141: endmodule
