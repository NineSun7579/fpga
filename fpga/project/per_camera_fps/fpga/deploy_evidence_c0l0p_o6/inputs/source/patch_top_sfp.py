# -*- coding: utf-8 -*-
"""
patch_top_sfp.py -- top.v SFP fiber RX integration (byte-level, GBK safe)
T1/T2/T3: exact-match (verified unique). T4: whitespace-flexible regex.
"""
import re

TOP = r'C:\Users\NineSun\Desktop\ov56401\project\source\top.v'

raw = open(TOP, 'rb').read()
text = raw.decode('gbk')

def sub_once(old, new):
    global text
    n = text.count(old)
    assert n == 1, 'pattern count=%d: %r' % (n, old[:70])
    text = text.replace(old, new)

# ---------------- T1: top-level ports ----------------
sub_once(
"""    output wire                 pclk_led        ,
""",
"""    output wire                 pclk_led        ,

    ////////////////// SFP fiber RX (QR3 HSST CH2) [SFP 2026-09-29] ////////////////
    // ref clock shared with PCIe (ref_clk_p/n F6/E6, 100MHz)
    input                       sfp_l2rxn       ,
    input                       sfp_l2rxp       ,
    output wire                 sfp_l2txn       ,
    output wire                 sfp_l2txp       ,
    output wire                 sfp_tx_disable  ,
""")

# ---------------- T2: wire declarations ----------------
sub_once(
"""wire cam_dma_done;
wire cam2_dma_done;
wire cam3_dma_done;
wire cam4_dma_done;""",
"""wire cam_dma_done;
wire cam2_dma_done;
wire cam3_dma_done;
wire cam4_dma_done;

// ---- [SFP 2026-09-29] fiber RX link / cam5 / cam6 signals ----
wire        sfp_rx_clk, sfp_rx_rst_n, sfp_rx_en;
wire [31:0] sfp_rxd;
wire [3:0]  sfp_rxk;
wire        sfp_vs, sfp_hs, sfp_de;
wire [15:0] sfp_pix;
wire        cam5_vs, cam5_hs, cam5_de;
wire [15:0] cam5_pix;
wire        cam6_vs, cam6_hs, cam6_de;
wire [15:0] cam6_pix;
wire [31:0] cam5_cmd_addr, cam5_cmd_len;
wire        cam5_cmd_valid, cam5_cmd_ready;
wire [AXI_DATA_LEN-1:0] cam5_s_data;
wire        cam5_s_data_valid, cam5_s_data_last, cam5_s_data_ready;
wire [15:0] cam5_s_data_available;
wire [AXI_ID_LEN-1:0]   cam5_axi_awid;
wire [31:0]             cam5_axi_awaddr;
wire [3:0]              cam5_axi_awlen;
wire [2:0]              cam5_axi_awsize;
wire [1:0]              cam5_axi_awburst;
wire                    cam5_axi_awlock;
wire [3:0]              cam5_axi_awcache;
wire [2:0]              cam5_axi_awprot;
wire                    cam5_axi_awvalid, cam5_axi_awready;
wire [AXI_DATA_LEN-1:0] cam5_axi_wdata;
wire [AXI_STRB_LEN-1:0] cam5_axi_wstrb;
wire                    cam5_axi_wlast, cam5_axi_wvalid, cam5_axi_wready;
wire [AXI_ID_LEN-1:0]   cam5_axi_bid;
wire [1:0]              cam5_axi_bresp;
wire                    cam5_axi_bvalid, cam5_axi_bready;
wire [31:0] cam6_cmd_addr, cam6_cmd_len;
wire        cam6_cmd_valid, cam6_cmd_ready;
wire [AXI_DATA_LEN-1:0] cam6_s_data;
wire        cam6_s_data_valid, cam6_s_data_last, cam6_s_data_ready;
wire [15:0] cam6_s_data_available;
wire [AXI_ID_LEN-1:0]   cam6_axi_awid;
wire [31:0]             cam6_axi_awaddr;
wire [3:0]              cam6_axi_awlen;
wire [2:0]              cam6_axi_awsize;
wire [1:0]              cam6_axi_awburst;
wire                    cam6_axi_awlock;
wire [3:0]              cam6_axi_awcache;
wire [2:0]              cam6_axi_awprot;
wire                    cam6_axi_awvalid, cam6_axi_awready;
wire [AXI_DATA_LEN-1:0] cam6_axi_wdata;
wire [AXI_STRB_LEN-1:0] cam6_axi_wstrb;
wire                    cam6_axi_wlast, cam6_axi_wvalid, cam6_axi_wready;
wire [AXI_ID_LEN-1:0]   cam6_axi_bid;
wire [1:0]              cam6_axi_bresp;
wire                    cam6_axi_bvalid, cam6_axi_bready;""")

# ---------------- T3: instantiation block after cam4 ----------------
T3_ANCHOR = (
"""    .xdma_clk (pcie_clk),
    .xdma_irq (          )
);
`elsif USE_HDMI""")
T3_NEW = open('insert_sfp_block.v', encoding='utf-8').read()
sub_once(T3_ANCHOR, T3_NEW)

# ---------------- T4: ddr_w_arb m4/m5 hookup (whitespace-flexible) ----------------
T4_RE = re.compile(
    r"    \.m3_bid\s+\(cam4_axi_bid\s*\), \s*\.m3_bresp\s+\(cam4_axi_bresp\s*\),\r?\n"
    r"    \.m3_bvalid\s+\(cam4_axi_bvalid\s*\), \s*\.m3_bready\s+\(cam4_axi_bready\s*\),\r?\n"
    r"    \.s_awid\s+\(arb_s_awid\s*\),"
)
T4_NEW = (
"""    .m3_bid     (cam4_axi_bid     ), .m3_bresp  (cam4_axi_bresp  ),
    .m3_bvalid  (cam4_axi_bvalid  ), .m3_bready (cam4_axi_bready ),
    // [SFP 2026-09-29] fiber cam5/cam6 join as masters 4/5
    .m4_awid    (cam5_axi_awid    ), .m4_awaddr (cam5_axi_awaddr ),
    .m4_awlen   (cam5_axi_awlen   ), .m4_awsize (cam5_axi_awsize ),
    .m4_awburst (cam5_axi_awburst ), .m4_awlock (cam5_axi_awlock ),
    .m4_awcache (cam5_axi_awcache ), .m4_awprot (cam5_axi_awprot ),
    .m4_awvalid (cam5_axi_awvalid ), .m4_awready(cam5_axi_awready),
    .m4_wdata   (cam5_axi_wdata   ), .m4_wstrb  (cam5_axi_wstrb  ),
    .m4_wlast   (cam5_axi_wlast   ), .m4_wvalid (cam5_axi_wvalid ),
    .m4_wready  (cam5_axi_wready  ),
    .m4_bid     (cam5_axi_bid     ), .m4_bresp  (cam5_axi_bresp  ),
    .m4_bvalid  (cam5_axi_bvalid  ), .m4_bready (cam5_axi_bready ),
    .m5_awid    (cam6_axi_awid    ), .m5_awaddr (cam6_axi_awaddr ),
    .m5_awlen   (cam6_axi_awlen   ), .m5_awsize (cam6_axi_awsize ),
    .m5_awburst (cam6_axi_awburst ), .m5_awlock (cam6_axi_awlock ),
    .m5_awcache (cam6_axi_awcache ), .m5_awprot (cam6_axi_awprot ),
    .m5_awvalid (cam6_axi_awvalid ), .m5_awready(cam6_axi_awready),
    .m5_wdata   (cam6_axi_wdata   ), .m5_wstrb  (cam6_axi_wstrb  ),
    .m5_wlast   (cam6_axi_wlast   ), .m5_wvalid (cam6_axi_wvalid ),
    .m5_wready  (cam6_axi_wready  ),
    .m5_bid     (cam6_axi_bid     ), .m5_bresp  (cam6_axi_bresp  ),
    .m5_bvalid  (cam6_axi_bvalid  ), .m5_bready (cam6_axi_bready ),
    .s_awid     (arb_s_awid         ),"""
)
m = T4_RE.search(text)
assert m, 'T4 anchor not found'
text = text[:m.start()] + T4_NEW + text[m.end():]

open(TOP, 'wb').write(text.encode('gbk'))
print('top.v SFP integration patched OK (T1/T2/T3/T4)')
