1: `timescale 1ns/1ps
2: // Isolated Verilog-2001 candidate. All ports share clk and common reset.
3: // Manager port names match fpga_v8_capture_lease exactly; invert rst_n for rst.
4: module fpga_v8_capture_control_axil_arm_v2 #(
5:     parameter [31:0] LOCAL_BASE = 32'h00000100
6: ) (
7:     input wire clk, input wire rst_n,
8:     output wire config_valid, input wire config_ready,
9:     output wire [31:0] config_generation,
10:     input wire config_accept, input wire config_reject,
11:     input wire epoch_start, input wire armed, input wire config_ok,
12:     input wire protocol_fault,
13:     input wire [1:0] bank0_state, input wire [1:0] bank1_state,
14:     input wire host_valid, output wire host_ready,
15:     input wire [31:0] host_src_addr, input wire [31:0] host_length,
16:     input wire [31:0] host_seq, input wire [31:0] host_generation,
17:     input wire [2:0] host_camera, input wire host_bank,
18:     input wire [63:0] host_token,
19:     output wire host_release_valid, input wire host_release_ready,
20:     output wire [2:0] host_release_camera, output wire host_release_bank,
21:     output wire [31:0] host_release_seq,
22:     output wire [31:0] host_release_generation,
23:     output wire [63:0] host_release_token,
24:     input wire host_release_accept, input wire host_release_reject,
25:     input wire [31:0] published_count, input wire [31:0] failed_count,
26:     input wire [31:0] rejected_release_count,
27:     input wire [31:0] s_axil_awaddr, input wire [2:0] s_axil_awprot,
28:     input wire s_axil_awvalid, output wire s_axil_awready,
29:     input wire [31:0] s_axil_wdata, input wire [3:0] s_axil_wstrb,
30:     input wire s_axil_wvalid, output wire s_axil_wready,
31:     output reg [1:0] s_axil_bresp, output reg s_axil_bvalid,
32:     input wire s_axil_bready,
33:     input wire [31:0] s_axil_araddr, input wire [2:0] s_axil_arprot,
34:     input wire s_axil_arvalid, output wire s_axil_arready,
35:     output reg [31:0] s_axil_rdata, output reg [1:0] s_axil_rresp,
36:     output reg s_axil_rvalid, input wire s_axil_rready
37: );
38:     localparam [1:0] NONE=0, ARM_WAIT=1, RELEASE_WAIT=2;
39:     localparam PARAM_OK = LOCAL_BASE[1:0]==0 && LOCAL_BASE<=32'hffffff80;
40:     reg aw_held, w_held;
41:     reg [31:0] aw_addr, w_data;
42:     reg [3:0] w_strb;
43:     reg [1:0] pending;
44:     reg [31:0] staged_generation, accepted_generation;
45:     reg host_bound;
46:     reg bound_bank;
47:     reg [31:0] bound_seq,bound_generation,bound_length,bound_addr;
48:     reg [2:0] bound_camera;
49:     reg [63:0] bound_token;
50:     reg [31:0] ack_bank,ack_seq,ack_generation,ack_token_low,ack_token_high,ack_camera;
51:     reg [31:0] rejected_claims,bad_acks,rejected_configs;
52:     reg [31:0] accepted_configs,accepted_claims,accepted_releases;
53:     wire commit = rst_n && aw_held && w_held && !s_axil_bvalid && pending==NONE;
54:     wire [31:0] wr_offset=aw_addr-LOCAL_BASE;
55:     wire wr_in_range=PARAM_OK && aw_addr>=LOCAL_BASE &&
56:         {1'b0,aw_addr}<({1'b0,LOCAL_BASE}+33'h80) && aw_addr[1:0]==0;
57:     wire doorbell=w_strb[0] && w_data[0];
58:     wire key_match=host_bound && ack_bank=={31'd0,bound_bank} &&
59:         ack_seq==bound_seq && ack_generation==bound_generation &&
60:         {ack_token_high,ack_token_low}==bound_token &&
61:         ack_camera=={29'd0,bound_camera};
62: 
63:     assign s_axil_awready=rst_n && !aw_held && !s_axil_bvalid && pending==NONE;
64:     assign s_axil_wready=rst_n && !w_held && !s_axil_bvalid && pending==NONE;
65:     assign s_axil_arready=rst_n && (!s_axil_rvalid || s_axil_rready);
66:     // READY-independent, single-edge request from immutable holding slots.
67:     // This asserts lease_block BEFORE that edge's wrapper SOF admission.
68:     // READY is sampled only in the sequential dispatch decision below.
69:     assign config_valid=commit && wr_in_range && wr_offset==32'h10 &&
70:         doorbell && !host_bound;
71:     assign config_generation=staged_generation;
72:     assign host_ready=commit && wr_in_range && wr_offset==32'h14 &&
73:         w_strb[0] && !host_bound && host_valid &&
74:         w_data=={31'd0,host_bank};
75:     assign host_release_valid=commit && wr_in_range && wr_offset==32'h50 &&
76:         doorbell && key_match && host_release_ready;
77:     assign host_release_camera=bound_camera;
78:     assign host_release_bank=bound_bank;
79:     assign host_release_seq=bound_seq;
80:     assign host_release_generation=bound_generation;
81:     assign host_release_token=bound_token;
82: 
83:     function [31:0] merge_bytes;
84:         input [31:0] old_data,new_data;
85:         input [3:0] strobes;
86:         integer b;
87:         begin
88:             merge_bytes=old_data;
89:             for(b=0;b<4;b=b+1) if(strobes[b]) merge_bytes[b*8 +: 8]=new_data[b*8 +: 8];
90:         end
91:     endfunction
92:     function valid_read;
93:         input [31:0] addr;
94:         begin
95:             // All 32 aligned words in this exact range are documented below.
96:             valid_read=PARAM_OK && addr>=LOCAL_BASE &&
97:                 {1'b0,addr}<({1'b0,LOCAL_BASE}+33'h80) && addr[1:0]==0;
98:         end
99:     endfunction
100:     function [31:0] read_register;
101:         input [31:0] addr;
102:         begin
103:             read_register=0;
104:             if(valid_read(addr)) case(addr-LOCAL_BASE)
105:                 32'h00: read_register=32'h4341504c; // CAPL
106:                 32'h04: read_register={21'd0,(host_valid && host_bank),epoch_start,host_release_ready,config_ready,
107:                     (pending==RELEASE_WAIT),(pending==ARM_WAIT),host_valid,
108:                     host_bound,protocol_fault,config_ok,armed};
109:                 32'h08: read_register=32'h00010000;
110:                 32'h0c: read_register=staged_generation;
111:                 32'h10: read_register=0;
112:                 32'h14,32'h18: read_register=host_bound ? {31'd0,bound_bank} : 32'hffffffff;
113:                 32'h1c: read_register=host_bound ? bound_seq : 0;
114:                 32'h20: read_register=host_bound ? bound_generation : 0;
115:                 32'h24: read_register=host_bound ? bound_length : 0;
116:                 32'h28: read_register=host_bound ? bound_addr : 0;
117:                 32'h2c: read_register=host_bound ? {29'd0,bound_camera} : 0;
118:                 32'h30: read_register=host_bound ? bound_token[31:0] : 0;
119:                 32'h34: read_register=host_bound ? bound_token[63:32] : 0;
120:                 32'h38: read_register=ack_bank;
121:                 32'h3c: read_register=ack_seq;
122:                 32'h40: read_register=ack_generation;
123:                 32'h44: read_register=ack_token_low;
124:                 32'h48: read_register=ack_token_high;
125:                 32'h4c: read_register=ack_camera;
126:                 32'h50: read_register=0;
127:                 32'h54: read_register=rejected_claims;
128:                 32'h58: read_register=bad_acks;
129:                 32'h5c: read_register=rejected_configs;
130:                 32'h60: read_register=published_count;
131:                 32'h64: read_register=failed_count;
132:                 32'h68: read_register=rejected_release_count;
133:                 32'h6c: read_register={28'd0,bank1_state,bank0_state};
134:                 32'h70: read_register=accepted_generation;
135:                 32'h74: read_register=accepted_configs;
136:                 32'h78: read_register=accepted_releases;
137:                 32'h7c: read_register=accepted_claims;
138:                 default: read_register=0;
139:             endcase
140:         end
141:     endfunction
142: 
143:     always @(posedge clk or negedge rst_n) begin
144:         if(!rst_n) begin
145:             aw_held<=0;w_held<=0;aw_addr<=0;w_data<=0;w_strb<=0;pending<=NONE;
146:             s_axil_bresp<=0;s_axil_bvalid<=0;
147:             s_axil_rdata<=0;s_axil_rresp<=0;s_axil_rvalid<=0;
148:             staged_generation<=0;accepted_generation<=0;
149:             host_bound<=0;bound_bank<=0;bound_seq<=0;bound_generation<=0;
150:             bound_length<=0;bound_addr<=0;bound_camera<=0;bound_token<=0;
151:             ack_bank<=0;ack_seq<=0;ack_generation<=0;
152:             ack_token_low<=0;ack_token_high<=0;ack_camera<=0;
153:             rejected_claims<=0;bad_acks<=0;rejected_configs<=0;
154:             accepted_configs<=0;accepted_claims<=0;accepted_releases<=0;
155:         end else begin
156:             if(s_axil_bvalid && s_axil_bready) s_axil_bvalid<=0;
157:             if(s_axil_awvalid && s_axil_awready) begin aw_held<=1;aw_addr<=s_axil_awaddr;end
158:             if(s_axil_wvalid && s_axil_wready) begin w_held<=1;w_data<=s_axil_wdata;w_strb<=s_axil_wstrb;end
159:             if(commit) begin
160:                 aw_held<=0;w_held<=0;
161:                 s_axil_bvalid<=1;s_axil_bresp<=0;
162:                 if(!wr_in_range) s_axil_bresp<=2;
163:                 else case(wr_offset)
164:                     32'h0c: staged_generation<=merge_bytes(staged_generation,w_data,w_strb);
165:                     32'h10: if(doorbell) begin
166:                         if(config_valid && config_ready) begin pending<=ARM_WAIT;s_axil_bvalid<=0;end
167:                         else begin s_axil_bresp<=2;rejected_configs<=rejected_configs+1'b1;end
168:                     end
169:                     32'h14: if(w_strb[0]) begin
170:                         if(host_ready) begin
171:                             host_bound<=1;bound_bank<=host_bank;
172:                             bound_seq<=host_seq;bound_generation<=host_generation;
173:                             bound_length<=host_length;bound_addr<=host_src_addr;
174:                             bound_camera<=host_camera;bound_token<=host_token;
175:                             accepted_claims<=accepted_claims+1'b1;
176:                         end else begin s_axil_bresp<=2;rejected_claims<=rejected_claims+1'b1;end
177:                     end
178:                     32'h38: ack_bank<=merge_bytes(ack_bank,w_data,w_strb);
179:                     32'h3c: ack_seq<=merge_bytes(ack_seq,w_data,w_strb);
180:                     32'h40: ack_generation<=merge_bytes(ack_generation,w_data,w_strb);
181:                     32'h44: ack_token_low<=merge_bytes(ack_token_low,w_data,w_strb);
182:                     32'h48: ack_token_high<=merge_bytes(ack_token_high,w_data,w_strb);
183:                     32'h4c: ack_camera<=merge_bytes(ack_camera,w_data,w_strb);
184:                     32'h50: if(doorbell) begin
185:                         if(host_release_valid) begin pending<=RELEASE_WAIT;s_axil_bvalid<=0;end
186:                         else begin s_axil_bresp<=2;bad_acks<=bad_acks+1'b1;end
187:                     end
188:                     default: s_axil_bresp<=2;
189:                 endcase
190:             end
191:             // Registered manager acceptance is authoritative, not READY alone.
192:             if(pending==ARM_WAIT && (config_accept || config_reject)) begin
193:                 pending<=NONE;s_axil_bvalid<=1;
194:                 s_axil_bresp<=config_accept && !config_reject ? 0 : 2;
195:                 if(config_accept && !config_reject) begin
196:                     accepted_generation<=staged_generation;accepted_configs<=accepted_configs+1'b1;
197:                 end else rejected_configs<=rejected_configs+1'b1;
198:             end
199:             if(pending==RELEASE_WAIT && (host_release_accept || host_release_reject)) begin
200:                 pending<=NONE;s_axil_bvalid<=1;
201:                 s_axil_bresp<=host_release_accept && !host_release_reject ? 0 : 2;
202:                 if(host_release_accept && !host_release_reject) begin
203:                     host_bound<=0;accepted_releases<=accepted_releases+1'b1;
204:                 end else bad_acks<=bad_acks+1'b1;
205:             end
206:             if(s_axil_arvalid && s_axil_arready) begin
207:                 s_axil_rvalid<=1;s_axil_rdata<=read_register(s_axil_araddr);
208:                 s_axil_rresp<=valid_read(s_axil_araddr) ? 0 : 2;
209:             end else if(s_axil_rvalid && s_axil_rready) s_axil_rvalid<=0;
210:         end
211:     end
212:     // PROT is accepted and ignored, like the existing cooperative controller.
213: endmodule
