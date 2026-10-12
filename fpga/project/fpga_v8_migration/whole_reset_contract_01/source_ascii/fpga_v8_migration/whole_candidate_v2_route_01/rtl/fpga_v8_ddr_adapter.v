1: `timescale 1ns/1ps
2: // Isolated candidate using the actual, read-only generated 16-word FIFOs.
3: // Common reset of adapter, upstream fabric and vendor controller is required.
4: module fpga_v8_ddr_adapter #(
5:     parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000
6: ) (
7:     input wire clk, input wire rst_n,
8:     input wire [3:0] s_awid,
9:     input wire [31:0] s_awaddr,
10:     input wire [7:0] s_awlen,
11:     input wire [2:0] s_awsize,
12:     input wire [1:0] s_awburst,
13:     input wire s_awvalid, output wire s_awready,
14:     input wire [127:0] s_wdata, input wire [15:0] s_wstrb,
15:     input wire s_wlast, input wire s_wvalid, output wire s_wready,
16:     output reg [3:0] s_bid, output reg [1:0] s_bresp,
17:     output reg s_bvalid, input wire s_bready,
18:     input wire [6:0] s_arid,
19:     input wire [31:0] s_araddr,
20:     input wire [7:0] s_arlen,
21:     input wire [2:0] s_arsize,
22:     input wire [1:0] s_arburst,
23:     input wire s_arvalid, output wire s_arready,
24:     output wire [6:0] s_rid, output wire [127:0] s_rdata,
25:     output wire [1:0] s_rresp, output wire s_rlast,
26:     output wire s_rvalid, input wire s_rready,
27:     output wire [3:0] v_awid, output wire [27:0] v_awaddr,
28:     output wire [3:0] v_awlen, output reg v_awvalid, input wire v_awready,
29:     output wire [127:0] v_wdata, output wire [15:0] v_wstrb,
30:     input wire v_wready, input wire v_wlast, input wire [3:0] v_wid,
31:     output wire [3:0] v_arid, output wire [27:0] v_araddr,
32:     output wire [3:0] v_arlen, output reg v_arvalid, input wire v_arready,
33:     input wire [3:0] v_rid, input wire [127:0] v_rdata,
34:     input wire v_rlast, input wire v_rvalid,
35:     output reg [7:0] error_flags,
36:     output wire [4:0] write_water_level,
37:     output wire write_fifo_full, output wire write_fifo_empty,
38:     output wire read_fifo_full, output wire read_fifo_empty,
39:     output wire write_busy, output wire read_busy
40: );
41:     wire fifo_rst = !rst_n;
42:     reg write_active, write_hold, vendor_write_active;
43:     reg [3:0] aw_id, aw_len;
44:     reg [27:0] aw_addr;
45:     reg [8:0] accepted_w, consumed_w;
46:     reg write_failed;
47:     reg read_active, vendor_read_active;
48:     reg [6:0] ar_id;
49:     reg [3:0] ar_len;
50:     reg [27:0] ar_addr;
51:     reg [8:0] received_r, retired_r;
52:     wire [3:0] fifo_rid;
53:     wire [63:0] aw_end = {32'd0,s_awaddr} + ({56'd0,s_awlen}+64'd1)*64'd16;
54:     wire [63:0] ar_end = {32'd0,s_araddr} + ({56'd0,s_arlen}+64'd1)*64'd16;
55:     wire limit_ok = DDR_ADDRESS_LIMIT!=0 && DDR_ADDRESS_LIMIT<=32'h10000000 && DDR_ADDRESS_LIMIT[3:0]==0;
56:     wire aw_ok = limit_ok && s_awlen<=15 && s_awaddr[3:0]==0 && s_awsize==4 && s_awburst==1 &&
57:                  ({1'b0,s_awaddr[11:0]}+({5'd0,s_awlen}+13'd1)*13'd16<=13'd4096) && aw_end<={32'd0,DDR_ADDRESS_LIMIT};
58:     wire ar_ok = limit_ok && s_arlen<=15 && s_araddr[3:0]==0 && s_arsize==4 && s_arburst==1 &&
59:                  ({1'b0,s_araddr[11:0]}+({5'd0,s_arlen}+13'd1)*13'd16<=13'd4096) && ar_end<={32'd0,DDR_ADDRESS_LIMIT};
60:     assign s_awready = rst_n && !write_active && !write_hold && !v_awvalid && !s_bvalid && write_fifo_empty && aw_ok;
61:     assign s_wready = rst_n && write_active && !write_fifo_full && accepted_w<({5'd0,aw_len}+9'd1);
62:     wire push_w = s_wvalid && s_wready;
63:     wire pop_w = rst_n && v_wready && vendor_write_active && !write_fifo_empty;
64:     assign write_busy = write_active;
65:     assign v_awid=aw_id;
66:     assign v_awaddr=aw_addr;
67:     assign v_awlen=aw_len;
68:     ddr_fifo16_w write_fifo (
69:         .clk(clk), .rst(fifo_rst), .wr_data({s_wstrb,s_wdata}), .wr_en(push_w),
70:         .wr_water_level(write_water_level), .full(write_fifo_full), .almost_full(),
71:         .rd_data({v_wstrb,v_wdata}), .rd_en(pop_w), .empty(write_fifo_empty), .almost_empty()
72:     );
73:     // Retain the full route ID until the downstream last R is consumed.
74:     assign s_arready = rst_n && !read_active && !v_arvalid && read_fifo_empty && ar_ok;
75:     assign v_arid=ar_id[3:0];
76:     assign v_araddr=ar_addr;
77:     assign v_arlen=ar_len;
78:     assign read_busy=read_active;
79:     assign s_rid={ar_id[6:4],fifo_rid};
80:     // The vendor interface has no RRESP. Protocol diagnostics remain sticky;
81:     // do not change a queued/stalled response based on a later vendor beat.
82:     assign s_rresp=2'b00;
83:     assign s_rvalid=rst_n && !read_fifo_empty;
84:     wire push_r=rst_n && v_rvalid && vendor_read_active && !read_fifo_full;
85:     ddr_fifo16_r read_fifo (
86:         .clk(clk), .rst(fifo_rst), .wr_data({v_rid,v_rlast,v_rdata}), .wr_en(push_r),
87:         .full(read_fifo_full), .almost_full(), .rd_data({fifo_rid,s_rlast,s_rdata}),
88:         .rd_en(s_rvalid && s_rready), .empty(read_fifo_empty), .almost_empty()
89:     );
90:     always @(posedge clk) begin
91:         if(!rst_n) begin
92:             write_active<=0; write_hold<=0; vendor_write_active<=0;
93:             aw_id<=0; aw_len<=0; aw_addr<=0; accepted_w<=0; consumed_w<=0;
94:             write_failed<=0; s_bvalid<=0; s_bresp<=0; s_bid<=0; v_awvalid<=0;
95:             read_active<=0; vendor_read_active<=0; ar_id<=0; ar_len<=0; ar_addr<=0;
96:             received_r<=0; retired_r<=0; v_arvalid<=0; error_flags<=0;
97:         end else begin
98:             // Unsupported requests are flagged and remain unaccepted; no LEN/address truncation.
99:             if(s_awvalid && !aw_ok) error_flags[0]<=1;
100:             if(s_arvalid && !ar_ok) error_flags[1]<=1;
101:             if(s_awvalid && s_awready) begin
102:                 write_active<=1; write_hold<=1; aw_id<=s_awid;
103:                 aw_len<=s_awlen[3:0]; aw_addr<=s_awaddr[27:0];
104:                 accepted_w<=0; consumed_w<=0; write_failed<=0;
105:             end
106:             if(push_w) begin
107:                 accepted_w<=accepted_w+1;
108:                 if(s_wlast != (accepted_w=={5'd0,aw_len})) begin
109:                     error_flags[2]<=1; write_failed<=1;
110:                 end
111:             end
112:             if(write_hold && !v_awvalid && !write_fifo_empty &&
113:                 write_water_level>=({1'b0,aw_len}+5'd1)) begin
114:                 v_awvalid<=1; write_hold<=0;
115:             end
116:             if(v_awvalid && v_awready) begin v_awvalid<=0; vendor_write_active<=1; end
117:             if(v_wready && (!vendor_write_active || write_fifo_empty)) error_flags[3]<=1;
118:             if(pop_w) begin
119:                 consumed_w<=consumed_w+1;
120:                 if(v_wlast != (consumed_w=={5'd0,aw_len}) || v_wid!=aw_id) begin
121:                     error_flags[4]<=1; write_failed<=1;
122:                 end
123:                 // The vendor's last-consumed indication, not upstream WLAST, mints B.
124:                 if(v_wlast) begin
125:                     vendor_write_active<=0; s_bvalid<=1; s_bid<=aw_id;
126:                     s_bresp<=(write_failed || consumed_w!={5'd0,aw_len} || v_wid!=aw_id)?2'b10:2'b00;
127:                 end
128:             end
129:             if(s_bvalid && s_bready) begin s_bvalid<=0; write_active<=0; end
130:             if(s_arvalid && s_arready) begin
131:                 read_active<=1; v_arvalid<=1; ar_id<=s_arid;
132:                 ar_addr<=s_araddr[27:0]; ar_len<=s_arlen[3:0];
133:                 received_r<=0; retired_r<=0;
134:             end
135:             if(v_arvalid && v_arready) begin v_arvalid<=0; vendor_read_active<=1; end
136:             if(v_rvalid && (!vendor_read_active || read_fifo_full)) error_flags[5]<=1;
137:             if(push_r) begin
138:                 received_r<=received_r+1;
139:                 if(v_rid!=ar_id[3:0] || v_rlast!=(received_r=={5'd0,ar_len})) begin
140:                     error_flags[6]<=1;
141:                 end
142:                 if(v_rlast) vendor_read_active<=0;
143:             end
144:             if(s_rvalid && s_rready) begin
145:                 retired_r<=retired_r+1;
146:                 if(s_rlast) begin
147:                     read_active<=0;
148:                     if(retired_r!={5'd0,ar_len}) error_flags[7]<=1;
149:                 end
150:             end
151:         end
152:     end
153: endmodule
