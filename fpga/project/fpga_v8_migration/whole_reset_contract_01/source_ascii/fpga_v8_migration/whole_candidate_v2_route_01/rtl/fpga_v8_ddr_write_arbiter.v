1: `timescale 1ns/1ps
2: // Isolated AXI4 write candidate: m0..m5 cameras, m6 preprocessing.
3: // Slot i occupies [i*FIELD_WIDTH +: FIELD_WIDTH] in every packed port.
4: // See README.md for staging, common-reset and protocol-error contracts.
5: module fpga_v8_ddr_write_arbiter #(
6:     parameter integer MASTER_COUNT = 7,
7:     parameter integer ID_WIDTH = 4,
8:     parameter integer ADDR_WIDTH = 32,
9:     parameter integer DATA_WIDTH = 128,
10:     parameter integer OWNER_WIDTH = (MASTER_COUNT > 1) ? $clog2(MASTER_COUNT) : 1
11: ) (
12:     input  wire clk,
13:     input  wire rst_n,
14:     input  wire [MASTER_COUNT*ID_WIDTH-1:0] m_awid,
15:     input  wire [MASTER_COUNT*ADDR_WIDTH-1:0] m_awaddr,
16:     input  wire [MASTER_COUNT*8-1:0] m_awlen,
17:     input  wire [MASTER_COUNT*3-1:0] m_awsize,
18:     input  wire [MASTER_COUNT*2-1:0] m_awburst,
19:     input  wire [MASTER_COUNT-1:0] m_awlock,
20:     input  wire [MASTER_COUNT*4-1:0] m_awcache,
21:     input  wire [MASTER_COUNT*3-1:0] m_awprot,
22:     input  wire [MASTER_COUNT*4-1:0] m_awqos,
23:     input  wire [MASTER_COUNT*4-1:0] m_awregion,
24:     input  wire [MASTER_COUNT-1:0] m_awvalid,
25:     output wire [MASTER_COUNT-1:0] m_awready,
26:     input  wire [MASTER_COUNT*DATA_WIDTH-1:0] m_wdata,
27:     input  wire [MASTER_COUNT*(DATA_WIDTH/8)-1:0] m_wstrb,
28:     input  wire [MASTER_COUNT-1:0] m_wlast,
29:     input  wire [MASTER_COUNT-1:0] m_wvalid,
30:     output wire [MASTER_COUNT-1:0] m_wready,
31:     output wire [MASTER_COUNT*ID_WIDTH-1:0] m_bid,
32:     output wire [MASTER_COUNT*2-1:0] m_bresp,
33:     output wire [MASTER_COUNT-1:0] m_bvalid,
34:     input  wire [MASTER_COUNT-1:0] m_bready,
35:     output wire [ID_WIDTH-1:0] s_awid,
36:     output wire [ADDR_WIDTH-1:0] s_awaddr,
37:     output wire [7:0] s_awlen,
38:     output wire [2:0] s_awsize,
39:     output wire [1:0] s_awburst,
40:     output wire s_awlock,
41:     output wire [3:0] s_awcache,
42:     output wire [2:0] s_awprot,
43:     output wire [3:0] s_awqos,
44:     output wire [3:0] s_awregion,
45:     output wire s_awvalid,
46:     input  wire s_awready,
47:     output wire [DATA_WIDTH-1:0] s_wdata,
48:     output wire [DATA_WIDTH/8-1:0] s_wstrb,
49:     output wire s_wlast,
50:     output wire s_wvalid,
51:     input  wire s_wready,
52:     input  wire [ID_WIDTH-1:0] s_bid,
53:     input  wire [1:0] s_bresp,
54:     input  wire s_bvalid,
55:     output wire s_bready,
56:     output wire busy,
57:     output wire [OWNER_WIDTH-1:0] owner,
58:     output wire error,
59:     output reg [4:0] error_flags
60: );
61:     localparam [1:0] IDLE = 2'd0, ADDRESS = 2'd1,
62:                      DATA = 2'd2, RESPONSE = 2'd3;
63:     reg [1:0] state;
64:     reg [OWNER_WIDTH-1:0] owner_reg, rr_next;
65:     reg [ID_WIDTH-1:0] awid_reg;
66:     reg [ADDR_WIDTH-1:0] awaddr_reg;
67:     reg [7:0] awlen_reg;
68:     reg [2:0] awsize_reg;
69:     reg [1:0] awburst_reg;
70:     reg awlock_reg;
71:     reg [3:0] awcache_reg;
72:     reg [2:0] awprot_reg;
73:     reg [3:0] awqos_reg, awregion_reg;
74:     // Nine bits deliberately represent all AXI4 lengths, including 256 beats.
75:     reg [8:0] beats_left;
76:     reg pick_valid;
77:     reg [OWNER_WIDTH-1:0] pick;
78:     integer offset, candidate;
79: 
80:     always @* begin
81:         pick_valid = 1'b0;
82:         pick = {OWNER_WIDTH{1'b0}};
83:         candidate = 0;
84:         for (offset = 0; offset < MASTER_COUNT; offset = offset + 1) begin
85:             candidate = rr_next + offset;
86:             if (candidate >= MASTER_COUNT)
87:                 candidate = candidate - MASTER_COUNT;
88:             if (!pick_valid && m_awvalid[candidate]) begin
89:                 pick_valid = 1'b1;
90:                 pick = candidate;
91:             end
92:         end
93:     end
94: 
95:     assign busy = rst_n && (state != IDLE);
96:     assign owner = owner_reg; // Meaningful only when busy is asserted.
97:     assign error = |error_flags;
98:     assign s_awid = awid_reg;
99:     assign s_awaddr = awaddr_reg;
100:     assign s_awlen = awlen_reg;
101:     assign s_awsize = awsize_reg;
102:     assign s_awburst = awburst_reg;
103:     assign s_awlock = awlock_reg;
104:     assign s_awcache = awcache_reg;
105:     assign s_awprot = awprot_reg;
106:     assign s_awqos = awqos_reg;
107:     assign s_awregion = awregion_reg;
108:     assign s_awvalid = rst_n && (state == ADDRESS);
109:     assign s_wvalid = rst_n && (state == DATA) && m_wvalid[owner_reg];
110:     assign s_wdata = (state == DATA) ?
111:                      m_wdata[owner_reg*DATA_WIDTH +: DATA_WIDTH] : {DATA_WIDTH{1'b0}};
112:     assign s_wstrb = (state == DATA) ?
113:                      m_wstrb[owner_reg*(DATA_WIDTH/8) +: DATA_WIDTH/8] : {(DATA_WIDTH/8){1'b0}};
114:     assign s_wlast = (state == DATA) && m_wlast[owner_reg];
115:     // Gate BVALID as well as BREADY. An early B must never retire upstream.
116:     assign s_bready = rst_n && (state == RESPONSE) && m_bready[owner_reg];
117:     assign m_bid = {MASTER_COUNT{s_bid}};
118:     assign m_bresp = {MASTER_COUNT{s_bresp}};
119:     genvar i;
120:     generate for (i = 0; i < MASTER_COUNT; i = i + 1) begin : master_routes
121:         assign m_awready[i] = s_awvalid && (owner_reg == i) && s_awready;
122:         assign m_wready[i] = rst_n && (state == DATA) && (owner_reg == i) && s_wready;
123:         assign m_bvalid[i] = rst_n && (state == RESPONSE) && (owner_reg == i) && s_bvalid;
124:     end endgenerate
125: 
126:     always @(posedge clk) begin
127:         if (!rst_n) begin
128:             state <= IDLE;
129:             owner_reg <= 0;
130:             rr_next <= 0;
131:             awid_reg <= 0;
132:             awaddr_reg <= 0;
133:             awlen_reg <= 0;
134:             awsize_reg <= 0;
135:             awburst_reg <= 0;
136:             awlock_reg <= 0;
137:             awcache_reg <= 0;
138:             awprot_reg <= 0;
139:             awqos_reg <= 0;
140:             awregion_reg <= 0;
141:             beats_left <= 0;
142:             error_flags <= 0;
143:         end else begin
144:             if (s_bvalid && state != RESPONSE)
145:                 error_flags[3] <= 1'b1;
146:             if (state == RESPONSE && s_bvalid) begin
147:                 if (s_bid != awid_reg)
148:                     error_flags[1] <= 1'b1;
149:                 if (s_bresp != 2'b00)
150:                     error_flags[2] <= 1'b1;
151:             end
152:             case (state)
153:                 IDLE: if (pick_valid) begin
154:                     // Selection is not acceptance: no upstream READY here.
155:                     // Snapshot every field before first presenting slave VALID.
156:                     owner_reg <= pick;
157:                     awid_reg <= m_awid[pick*ID_WIDTH +: ID_WIDTH];
158:                     awaddr_reg <= m_awaddr[pick*ADDR_WIDTH +: ADDR_WIDTH];
159:                     awlen_reg <= m_awlen[pick*8 +: 8];
160:                     awsize_reg <= m_awsize[pick*3 +: 3];
161:                     awburst_reg <= m_awburst[pick*2 +: 2];
162:                     awlock_reg <= m_awlock[pick];
163:                     awcache_reg <= m_awcache[pick*4 +: 4];
164:                     awprot_reg <= m_awprot[pick*3 +: 3];
165:                     awqos_reg <= m_awqos[pick*4 +: 4];
166:                     awregion_reg <= m_awregion[pick*4 +: 4];
167:                     beats_left <= {1'b0, m_awlen[pick*8 +: 8]} + 9'd1;
168:                     state <= ADDRESS;
169:                 end
170:                 ADDRESS: begin
171:                     // Contract diagnostic only; never cancel a presented AW.
172:                     if (!m_awvalid[owner_reg] ||
173:                         m_awid[owner_reg*ID_WIDTH +: ID_WIDTH] != awid_reg ||
174:                         m_awaddr[owner_reg*ADDR_WIDTH +: ADDR_WIDTH] != awaddr_reg ||
175:                         m_awlen[owner_reg*8 +: 8] != awlen_reg ||
176:                         m_awsize[owner_reg*3 +: 3] != awsize_reg ||
177:                         m_awburst[owner_reg*2 +: 2] != awburst_reg ||
178:                         m_awlock[owner_reg] != awlock_reg ||
179:                         m_awcache[owner_reg*4 +: 4] != awcache_reg ||
180:                         m_awprot[owner_reg*3 +: 3] != awprot_reg ||
181:                         m_awqos[owner_reg*4 +: 4] != awqos_reg ||
182:                         m_awregion[owner_reg*4 +: 4] != awregion_reg)
183:                         error_flags[4] <= 1'b1;
184:                     if (s_awready)
185:                         state <= DATA;
186:                 end
187:                 DATA: if (s_wvalid && s_wready) begin
188:                     if (s_wlast != (beats_left == 9'd1))
189:                         error_flags[0] <= 1'b1;
190:                     beats_left <= beats_left - 9'd1;
191:                     if (beats_left == 9'd1)
192:                         state <= RESPONSE;
193:                 end
194:                 RESPONSE: if (s_bvalid && s_bready) begin
195:                     rr_next <= (owner_reg == MASTER_COUNT-1) ?
196:                                {OWNER_WIDTH{1'b0}} : owner_reg + 1'b1;
197:                     state <= IDLE;
198:                 end
199:                 default: state <= IDLE;
200:             endcase
201:         end
202:     end
203: endmodule
