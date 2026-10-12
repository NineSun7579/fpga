1: `timescale 1ns/1ps
2: // Isolated Verilog-2001 two-child router; addresses stay full and untranslated.
3: // 0x000..0x0ff -> m0 cooperative; all other addresses -> m1 exact capture decode.
4: module fpga_v8_coop_axil_router (
5:     input wire clk,input wire rst_n,
6:     input wire [31:0] s_axil_awaddr,input wire [2:0] s_axil_awprot,
7:     input wire s_axil_awvalid,output wire s_axil_awready,
8:     input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,
9:     input wire s_axil_wvalid,output wire s_axil_wready,
10:     output reg [1:0] s_axil_bresp,output wire s_axil_bvalid,input wire s_axil_bready,
11:     input wire [31:0] s_axil_araddr,input wire [2:0] s_axil_arprot,
12:     input wire s_axil_arvalid,output wire s_axil_arready,
13:     output reg [31:0] s_axil_rdata,output reg [1:0] s_axil_rresp,
14:     output wire s_axil_rvalid,input wire s_axil_rready,
15:     output wire [31:0] m0_axil_awaddr,output wire [2:0] m0_axil_awprot,
16:     output wire m0_axil_awvalid,input wire m0_axil_awready,
17:     output wire [31:0] m0_axil_wdata,output wire [3:0] m0_axil_wstrb,
18:     output wire m0_axil_wvalid,input wire m0_axil_wready,
19:     input wire [1:0] m0_axil_bresp,input wire m0_axil_bvalid,output wire m0_axil_bready,
20:     output wire [31:0] m0_axil_araddr,output wire [2:0] m0_axil_arprot,
21:     output wire m0_axil_arvalid,input wire m0_axil_arready,
22:     input wire [31:0] m0_axil_rdata,input wire [1:0] m0_axil_rresp,
23:     input wire m0_axil_rvalid,output wire m0_axil_rready,
24:     output wire [31:0] m1_axil_awaddr,output wire [2:0] m1_axil_awprot,
25:     output wire m1_axil_awvalid,input wire m1_axil_awready,
26:     output wire [31:0] m1_axil_wdata,output wire [3:0] m1_axil_wstrb,
27:     output wire m1_axil_wvalid,input wire m1_axil_wready,
28:     input wire [1:0] m1_axil_bresp,input wire m1_axil_bvalid,output wire m1_axil_bready,
29:     output wire [31:0] m1_axil_araddr,output wire [2:0] m1_axil_arprot,
30:     output wire m1_axil_arvalid,input wire m1_axil_arready,
31:     input wire [31:0] m1_axil_rdata,input wire [1:0] m1_axil_rresp,
32:     input wire m1_axil_rvalid,output wire m1_axil_rready
33: );
34:     localparam [1:0] CAP=0,SEND=1,WAIT_RESP=2,FULL_RESP=3;
35:     reg [1:0] ws,rs;
36:     reg aw_held,w_held,wr_route,rd_route,aw_pending,w_pending;
37:     reg [31:0] aw_addr,w_data,ar_addr;
38:     reg [2:0] aw_prot,ar_prot;
39:     reg [3:0] w_strb;
40:     wire child_awready=wr_route ? m1_axil_awready : m0_axil_awready;
41:     wire child_wready=wr_route ? m1_axil_wready : m0_axil_wready;
42:     wire child_bvalid=wr_route ? m1_axil_bvalid : m0_axil_bvalid;
43:     wire [1:0] child_bresp=wr_route ? m1_axil_bresp : m0_axil_bresp;
44:     wire child_arready=rd_route ? m1_axil_arready : m0_axil_arready;
45:     wire child_rvalid=rd_route ? m1_axil_rvalid : m0_axil_rvalid;
46:     wire [1:0] child_rresp=rd_route ? m1_axil_rresp : m0_axil_rresp;
47:     wire [31:0] child_rdata=rd_route ? m1_axil_rdata : m0_axil_rdata;
48:     assign s_axil_awready=rst_n && ws==CAP && !aw_held;
49:     assign s_axil_wready=rst_n && ws==CAP && !w_held;
50:     assign s_axil_bvalid=rst_n && ws==FULL_RESP;
51:     assign s_axil_arready=rst_n && rs==CAP;
52:     assign s_axil_rvalid=rst_n && rs==FULL_RESP;
53:     assign m0_axil_awaddr=aw_addr;assign m1_axil_awaddr=aw_addr;
54:     assign m0_axil_awprot=aw_prot;assign m1_axil_awprot=aw_prot;
55:     assign m0_axil_wdata=w_data;assign m1_axil_wdata=w_data;
56:     assign m0_axil_wstrb=w_strb;assign m1_axil_wstrb=w_strb;
57:     assign m0_axil_araddr=ar_addr;assign m1_axil_araddr=ar_addr;
58:     assign m0_axil_arprot=ar_prot;assign m1_axil_arprot=ar_prot;
59:     assign m0_axil_awvalid=rst_n && ws==SEND && !wr_route && aw_pending;
60:     assign m1_axil_awvalid=rst_n && ws==SEND && wr_route && aw_pending;
61:     assign m0_axil_wvalid=rst_n && ws==SEND && !wr_route && w_pending;
62:     assign m1_axil_wvalid=rst_n && ws==SEND && wr_route && w_pending;
63:     assign m0_axil_bready=rst_n && ws==WAIT_RESP && !wr_route;
64:     assign m1_axil_bready=rst_n && ws==WAIT_RESP && wr_route;
65:     assign m0_axil_arvalid=rst_n && rs==SEND && !rd_route;
66:     assign m1_axil_arvalid=rst_n && rs==SEND && rd_route;
67:     assign m0_axil_rready=rst_n && rs==WAIT_RESP && !rd_route;
68:     assign m1_axil_rready=rst_n && rs==WAIT_RESP && rd_route;
69:     always @(posedge clk or negedge rst_n) begin
70:         if(!rst_n) begin
71:             ws<=CAP;rs<=CAP;aw_held<=0;w_held<=0;wr_route<=0;rd_route<=0;
72:             aw_pending<=0;w_pending<=0;aw_addr<=0;w_data<=0;ar_addr<=0;
73:             aw_prot<=0;ar_prot<=0;w_strb<=0;
74:             s_axil_bresp<=0;s_axil_rdata<=0;s_axil_rresp<=0;
75:         end else begin
76:             if(s_axil_awvalid && s_axil_awready) begin
77:                 aw_held<=1;aw_addr<=s_axil_awaddr;aw_prot<=s_axil_awprot;
78:                 wr_route<=s_axil_awaddr>=32'h100;
79:             end
80:             if(s_axil_wvalid && s_axil_wready) begin w_held<=1;w_data<=s_axil_wdata;w_strb<=s_axil_wstrb;end
81:             if(ws==CAP && aw_held && w_held) begin ws<=SEND;aw_pending<=1;w_pending<=1;end
82:             if(ws==SEND) begin
83:                 if(aw_pending && child_awready) aw_pending<=0;
84:                 if(w_pending && child_wready) w_pending<=0;
85:                 if((!aw_pending || child_awready) && (!w_pending || child_wready)) ws<=WAIT_RESP;
86:             end
87:             if(ws==WAIT_RESP && child_bvalid) begin s_axil_bresp<=child_bresp;ws<=FULL_RESP;end
88:             if(s_axil_bvalid && s_axil_bready) begin ws<=CAP;aw_held<=0;w_held<=0;end
89:             if(s_axil_arvalid && s_axil_arready) begin
90:                 ar_addr<=s_axil_araddr;ar_prot<=s_axil_arprot;
91:                 rd_route<=s_axil_araddr>=32'h100;rs<=SEND;
92:             end
93:             if(rs==SEND && child_arready) rs<=WAIT_RESP;
94:             if(rs==WAIT_RESP && child_rvalid) begin
95:                 s_axil_rdata<=child_rdata;s_axil_rresp<=child_rresp;rs<=FULL_RESP;
96:             end
97:             if(s_axil_rvalid && s_axil_rready) rs<=CAP;
98:         end
99:     end
100: endmodule
