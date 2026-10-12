1: // Isolated RAW ownership candidate. All interfaces use the capture AXI clock.
2: // The event inputs MUST come from fpga_v8_capture_ov5640_ddr, not software.
3: module fpga_v8_capture_lease #(
4:     parameter [31:0] BANK0_ADDR = 32'h01800000,
5:     parameter [31:0] BANK1_ADDR = 32'h01a00000,
6:     parameter [31:0] DDR_LIMIT = 32'h10000000,
7:     parameter RAW_LENGTH = 614400,
8:     parameter CAM_DATA_LEN = 38400,
9:     parameter FRAME_WIDTH = 640,
10:     parameter FRAME_HEIGHT = 480,
11:     parameter DATA_WIDTH = 16,
12:     parameter CAM_ID = 4, // physical cam5, zero-based controller camera index
13:     parameter HOST_REQUIRED = 1
14: )(
15:     input clk, input rst,
16:     input config_valid, output config_ready, input [31:0] config_generation,
17:     output reg config_accept, output reg config_reject,
18:     output reg epoch_start, output reg armed, output config_ok,
19:     input engine_idle, input capture_bank, input admitted_sof,
20:     input publish, input [31:0] publish_seq, input retired_error,
21:     output lease_block,
22:     output [1:0] bank0_state, output [1:0] bank1_state,
23:     output reg protocol_fault,
24: 
25:     output reg input_valid, input input_ready, output input_raw_valid,
26:     output [31:0] input_src_addr, output [31:0] input_length,
27:     output [31:0] input_seq, output [31:0] input_generation,
28:     output [2:0] input_camera, output input_bank, output [63:0] input_token,
29:     input release_valid, output release_ready,
30:     input [2:0] release_camera, input release_bank,
31:     input [31:0] release_seq, input [31:0] release_generation,
32:     input [63:0] release_token,
33:     output reg release_accept, output reg release_reject,
34: 
35:     output reg host_valid, input host_ready,
36:     output [31:0] host_src_addr, output [31:0] host_length,
37:     output [31:0] host_seq, output [31:0] host_generation,
38:     output [2:0] host_camera, output host_bank, output [63:0] host_token,
39:     input host_release_valid, output host_release_ready,
40:     input [2:0] host_release_camera, input host_release_bank,
41:     input [31:0] host_release_seq, input [31:0] host_release_generation,
42:     input [63:0] host_release_token,
43:     output reg host_release_accept, output reg host_release_reject,
44:     output reg [31:0] published_count, output reg [31:0] failed_count,
45:     output reg [31:0] rejected_release_count
46: );
47:     localparam FREE = 2'd0, WRITING = 2'd1, HELD = 2'd2;
48:     // Widen BEFORE addition/multiplication, including the 16-byte frame tag.
49:     localparam [63:0] END0 = {32'd0, BANK0_ADDR} + RAW_LENGTH + 64'd16;
50:     localparam [63:0] END1 = {32'd0, BANK1_ADDR} + RAW_LENGTH + 64'd16;
51:     localparam [63:0] GEOMETRY_BYTES = 64'd2 * FRAME_WIDTH * FRAME_HEIGHT;
52:     localparam PARAM_OK = DATA_WIDTH == 16 && CAM_ID >= 0 && CAM_ID < 6 &&
53:         (HOST_REQUIRED == 0 || HOST_REQUIRED == 1) &&
54:         RAW_LENGTH > 0 && FRAME_WIDTH > 0 && FRAME_HEIGHT > 0 &&
55:         CAM_DATA_LEN >= 2 && (CAM_DATA_LEN % 2) == 0 &&
56:         RAW_LENGTH == (64'd16 * CAM_DATA_LEN) && RAW_LENGTH == GEOMETRY_BYTES &&
57:         BANK0_ADDR[3:0] == 0 && BANK1_ADDR[3:0] == 0 &&
58:         END0 <= {32'd0, DDR_LIMIT} && END1 <= {32'd0, DDR_LIMIT} &&
59:         (END0 <= {32'd0, BANK1_ADDR} || END1 <= {32'd0, BANK0_ADDR});
60:     assign config_ok = PARAM_OK;
61:     reg [1:0] state [0:1];
62:     reg [31:0] sequence [0:1];
63:     reg [31:0] generation;
64:     reg [31:0] next_sequence;
65:     reg coop_claimed [0:1], coop_released [0:1];
66:     reg host_claimed [0:1], host_released [0:1];
67:     reg writing_bank;
68:     reg coop_offer_bank, host_offer_bank, coop_rr, host_rr;
69:     wire all_free = state[0] == FREE && state[1] == FREE;
70:     // config_valid blocks SOF admission, so config and capture cannot race.
71:     assign config_ready = !rst && all_free && engine_idle && !epoch_start;
72:     assign lease_block = !PARAM_OK || !armed || protocol_fault || config_valid ||
73:                          epoch_start || next_sequence == 0 || state[capture_bank] != FREE;
74:     assign bank0_state = state[0];
75:     assign bank1_state = state[1];
76:     assign input_raw_valid = input_valid;
77:     assign input_bank = coop_offer_bank;
78:     assign input_src_addr = input_bank ? BANK1_ADDR : BANK0_ADDR;
79:     assign input_length = RAW_LENGTH;
80:     assign input_seq = sequence[input_bank];
81:     assign input_generation = generation;
82:     assign input_camera = CAM_ID;
83:     assign input_token = {generation, input_seq};
84:     assign host_bank = host_offer_bank;
85:     assign host_src_addr = host_bank ? BANK1_ADDR : BANK0_ADDR;
86:     assign host_length = RAW_LENGTH;
87:     assign host_seq = sequence[host_bank];
88:     assign host_generation = generation;
89:     assign host_camera = CAM_ID;
90:     assign host_token = {generation, host_seq};
91:     assign release_ready = !rst;
92:     assign host_release_ready = !rst;
93:     wire coop_match = state[release_bank] == HELD &&
94:         coop_claimed[release_bank] && !coop_released[release_bank] &&
95:         release_camera == CAM_ID && release_seq == sequence[release_bank] &&
96:         release_generation == generation && release_token == {generation, sequence[release_bank]};
97:     wire host_match = HOST_REQUIRED && state[host_release_bank] == HELD &&
98:         host_claimed[host_release_bank] && !host_released[host_release_bank] &&
99:         host_release_camera == CAM_ID && host_release_seq == sequence[host_release_bank] &&
100:         host_release_generation == generation && host_release_token == {generation, sequence[host_release_bank]};
101:     wire coop_fire = release_valid && release_ready && coop_match;
102:     wire host_fire = host_release_valid && host_release_ready && host_match;
103:     wire coop_available0 = state[0] == HELD && !coop_claimed[0];
104:     wire coop_available1 = state[1] == HELD && !coop_claimed[1];
105:     wire host_available0 = HOST_REQUIRED && state[0] == HELD && !host_claimed[0];
106:     wire host_available1 = HOST_REQUIRED && state[1] == HELD && !host_claimed[1];
107:     integer i;
108:     always @(posedge clk) begin
109:         if (rst) begin
110:             generation <= 0;
111:             next_sequence <= 1;
112:             armed <= 0;
113:             epoch_start <= 0;
114:             config_accept <= 0;
115:             config_reject <= 0;
116:             protocol_fault <= 0;
117:             input_valid <= 0;
118:             host_valid <= 0;
119:             coop_offer_bank <= 0;
120:             host_offer_bank <= 0;
121:             coop_rr <= 0;
122:             host_rr <= 0;
123:             writing_bank <= 0;
124:             release_accept <= 0;
125:             release_reject <= 0;
126:             host_release_accept <= 0;
127:             host_release_reject <= 0;
128:             published_count <= 0;
129:             failed_count <= 0;
130:             rejected_release_count <= 0;
131:             for (i=0; i<2; i=i+1) begin
132:                 state[i] <= FREE;
133:                 sequence[i] <= 0;
134:                 coop_claimed[i] <= 0;
135:                 coop_released[i] <= 0;
136:                 host_claimed[i] <= 0;
137:                 host_released[i] <= !HOST_REQUIRED;
138:             end
139:         end else begin
140:             epoch_start <= 0;
141:             config_accept <= 0;
142:             config_reject <= 0;
143:             release_accept <= coop_fire;
144:             release_reject <= release_valid && release_ready && !coop_match;
145:             host_release_accept <= host_fire;
146:             host_release_reject <= host_release_valid && host_release_ready && !host_match;
147:             rejected_release_count <= rejected_release_count +
148:                 (release_valid && release_ready && !coop_match) +
149:                 (host_release_valid && host_release_ready && !host_match);
150:             if (config_valid && config_ready) begin
151:                 if (PARAM_OK && config_generation != 0 && config_generation != generation && !protocol_fault) begin
152:                     generation <= config_generation;
153:                     next_sequence <= 1;
154:                     armed <= 1;
155:                     config_accept <= 1;
156:                     epoch_start <= 1; // idle-only camera datapath epoch restart
157:                     coop_rr <= 0;
158:                     host_rr <= 0;
159:                 end else config_reject <= 1;
160:             end
161:             if (admitted_sof) begin
162:                 if (!lease_block) begin
163:                     state[capture_bank] <= WRITING;
164:                     writing_bank <= capture_bank;
165:                     coop_claimed[capture_bank] <= 0;
166:                     coop_released[capture_bank] <= 0;
167:                     host_claimed[capture_bank] <= 0;
168:                     host_released[capture_bank] <= !HOST_REQUIRED;
169:                 end else begin protocol_fault <= 1; armed <= 0; end
170:             end
171:             if (publish) begin
172:                 if (state[writing_bank] == WRITING && publish_seq == next_sequence && publish_seq != 0) begin
173:                     state[writing_bank] <= HELD;
174:                     sequence[writing_bank] <= publish_seq;
175:                     next_sequence <= next_sequence + 1'b1;
176:                     published_count <= published_count + 1'b1;
177:                     if (next_sequence == 32'hffffffff) armed <= 0;
178:                 end else begin protocol_fault <= 1; armed <= 0; end
179:             end else if (retired_error && state[writing_bank] == WRITING) begin
180:                 state[writing_bank] <= FREE;
181:                 failed_count <= failed_count + 1'b1;
182:             end
183:             if (!input_valid && (coop_available0 || coop_available1)) begin
184:                 coop_offer_bank <= coop_available0 && coop_available1 ? coop_rr : !coop_available0;
185:                 input_valid <= 1;
186:             end else if (input_valid && input_ready) begin
187:                 coop_claimed[input_bank] <= 1;
188:                 input_valid <= 0;
189:                 coop_rr <= !input_bank;
190:             end
191:             if (!host_valid && (host_available0 || host_available1)) begin
192:                 host_offer_bank <= host_available0 && host_available1 ? host_rr : !host_available0;
193:                 host_valid <= 1;
194:             end else if (host_valid && host_ready) begin
195:                 host_claimed[host_bank] <= 1;
196:                 host_valid <= 0;
197:                 host_rr <= !host_bank;
198:             end
199:             if (coop_fire) coop_released[release_bank] <= 1;
200:             if (host_fire) host_released[host_release_bank] <= 1;
201:             for (i=0; i<2; i=i+1) begin
202:                 if (state[i] == HELD &&
203:                     (coop_released[i] || (coop_fire && release_bank == i)) &&
204:                     (host_released[i] || (host_fire && host_release_bank == i))) state[i] <= FREE;
205:             end
206:         end
207:     end
208: endmodule
