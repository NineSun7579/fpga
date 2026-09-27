# -*- coding: utf-8 -*-
"""patch_integration.py -- byte-exact (GBK-safe) patches to wire vip_kf_stream
into the camera path. Idempotent: skips a patch if the new bytes are present.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(path, old, new):
    p = os.path.join(ROOT, path)
    d = open(p, "rb").read()
    O = old.encode("ascii")
    N = new.encode("ascii")
    if N in d:
        print("SKIP  (already)  %s :: %s" % (path, new[:48]))
        return
    c = d.count(O)
    if c != 1:
        print("FAIL  count=%d    %s :: %s" % (c, path, old[:60]))
        sys.exit(1)
    open(p, "wb").write(d.replace(O, N, 1))
    print("ok    %s :: %s" % (path, new[:48]))


# ---------------------------------------------------------------------------
# A. ov5640_ddr_w_ctrl.v : expose the current write bank
# ---------------------------------------------------------------------------
patch("source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v",
      "dbg_wd_cnt\n);",
      "dbg_wd_cnt,\n"
      "    output                           w_ping_o      // [VKFS] current write bank (0=buf1,1=buf2)\n"
      ");")

patch("source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v",
      "endmodule",
      "    // [VKFS 2026-09-25] other ping-pong bank = where the previous frame lives\n"
      "    assign w_ping_o = w_ping;\n\n"
      "endmodule")

# ---------------------------------------------------------------------------
# B. ov5640_ddr.v : derive prev_frame_base = other bank
# ---------------------------------------------------------------------------
patch("source/ov5640/ov5640_ddr/ov5640_ddr.v",
      "input  [1 : 0]   xdma_ack        \n);",
      "input  [1 : 0]   xdma_ack        ,\n"
      "    output [AXI_ADDR_WIDTH-1:0] prev_frame_base  // [VKFS] previous frame's ping-pong bank\n"
      ");")

patch("source/ov5640/ov5640_ddr/ov5640_ddr.v",
      "    wire                    engine_busy;   // [IDLEGATE 2026-09-19]",
      "    wire                    engine_busy;   // [IDLEGATE 2026-09-19]\n"
      "    wire                    w_ping_o;")

patch("source/ov5640/ov5640_ddr/ov5640_ddr.v",
      "    .engine_busy    (engine_busy    ),",
      "    .engine_busy    (engine_busy    ),\n"
      "    .w_ping_o       (w_ping_o       ),")

patch("source/ov5640/ov5640_ddr/ov5640_ddr.v",
      "endmodule",
      "    // [VKFS 2026-09-25] prev frame base = the bank NOT currently being written\n"
      "    assign prev_frame_base = w_ping_o ? cam_data_addr_1 : cam_data_addr_2;\n\n"
      "endmodule")

# ---------------------------------------------------------------------------
# C. ov5640_top.v : KF parameters, ports, generate block, DDR hookup (CRLF)
# ---------------------------------------------------------------------------
patch("source/ov5640/ov5640_top.v",
      "MEDIAN_RSVD    = 3'd0\r\n)(",
      "MEDIAN_RSVD    = 3'd0,\r\n"
      "    // [VKFS 2026-09-25] cam1 temporal Kalman/IIR after the median stage.\r\n"
      "    //   KF_EN=0 -> pure bypass (cam2 default). The previous-frame state is\r\n"
      "    //   read back from the other DDR ping-pong bank via kf_* (a free\r\n"
      "    //   crossbar slave port), so no on-chip full-frame buffer is needed.\r\n"
      "    parameter        KF_EN          = 1'b0,\r\n"
      "    parameter [5:0]  KF_THR0        = 6'd3,\r\n"
      "    parameter [5:0]  KF_THR1        = 6'd8,\r\n"
      "    parameter [5:0]  KF_THR2        = 6'd20\r\n"
      ")(")

KF_PORTS = (
    "    output  [1 : 0]               xdma_irq   /*synthesis PAP_MARK_DEBUG=\"1\"*/,\r\n"
    "\r\n"
    "    // [VKFS 2026-09-25] previous-frame DDR read master (driven when KF_EN=1)\r\n"
    "    output                        kf_arvalid,\r\n"
    "    input                         kf_arready,\r\n"
    "    output [AXI_ADDR_WIDTH-1 : 0] kf_araddr,\r\n"
    "    output [7 : 0]                kf_arlen,\r\n"
    "    output [2 : 0]                kf_arsize,\r\n"
    "    output [1 : 0]                kf_arburst,\r\n"
    "    output                        kf_arlock,\r\n"
    "    output [3 : 0]                kf_arcache,\r\n"
    "    output [2 : 0]                kf_arprot,\r\n"
    "    output [3 : 0]                kf_arid,\r\n"
    "    output                        kf_rready,\r\n"
    "    input  [3 : 0]                kf_rid,\r\n"
    "    input  [AXI_DATA_WIDTH-1 : 0] kf_rdata,\r\n"
    "    input  [1 : 0]                kf_rresp,\r\n"
    "    input                         kf_rlast,\r\n"
    "    input                         kf_rvalid\r\n"
    ");"
)
patch("source/ov5640/ov5640_top.v",
      "    output  [1 : 0]               xdma_irq   /*synthesis PAP_MARK_DEBUG=\"1\"*/\r\n\r\n);",
      KF_PORTS)

KF_GEN = (
    "    endgenerate\r\n"
    "\r\n"
    "    // [VKFS 2026-09-25] cam1 temporal filter on the (post-median) pixel stream.\r\n"
    "    // Keeps W*H pixels/frame and the single-beat s_valid contract; only pixel\r\n"
    "    // values change. Previous frame comes from the other ping-pong bank.\r\n"
    "    wire                      kf_video_valid;\r\n"
    "    wire [DATA_WIDTH-1 : 0]   kf_video_data ;\r\n"
    "    wire                      kf_video_vsync;\r\n"
    "    wire [AXI_ADDR_WIDTH-1:0] kf_prev_base;\r\n"
    "\r\n"
    "    generate\r\n"
    "        if (KF_EN) begin : g_kf\r\n"
    "            vip_kf_stream #(\r\n"
    "                .W (H_CMOS_DISP),\r\n"
    "                .H (V_CMOS_DISP),\r\n"
    "                .AW (19),\r\n"
    "                .AXI_ID_WIDTH (4),\r\n"
    "                .AXI_DATA_W   (AXI_DATA_WIDTH),\r\n"
    "                .BURST_LEN    (8)\r\n"
    "            ) u_kf_stream (\r\n"
    "                .clk        (video_clk),\r\n"
    "                .rst        (video_rst),\r\n"
    "                .en         (1'b1),\r\n"
    "                .thr0       (KF_THR0),\r\n"
    "                .thr1       (KF_THR1),\r\n"
    "                .thr2       (KF_THR2),\r\n"
    "                .in_valid   (sh_video_valid),\r\n"
    "                .in_pixel   (sh_video_data ),\r\n"
    "                .in_vsync   (sh_video_vsync),\r\n"
    "                .prev_base  (kf_prev_base),\r\n"
    "                .m_axi_arid    (kf_arid),\r\n"
    "                .m_axi_araddr  (kf_araddr),\r\n"
    "                .m_axi_arlen   (kf_arlen),\r\n"
    "                .m_axi_arsize  (kf_arsize),\r\n"
    "                .m_axi_arburst (kf_arburst),\r\n"
    "                .m_axi_arlock  (kf_arlock),\r\n"
    "                .m_axi_arcache (kf_arcache),\r\n"
    "                .m_axi_arprot  (kf_arprot),\r\n"
    "                .m_axi_arvalid (kf_arvalid),\r\n"
    "                .m_axi_arready (kf_arready),\r\n"
    "                .m_axi_rid     (kf_rid),\r\n"
    "                .m_axi_rdata   (kf_rdata),\r\n"
    "                .m_axi_rresp   (kf_rresp),\r\n"
    "                .m_axi_rlast   (kf_rlast),\r\n"
    "                .m_axi_rvalid  (kf_rvalid),\r\n"
    "                .m_axi_rready  (kf_rready),\r\n"
    "                .out_valid  (kf_video_valid),\r\n"
    "                .out_pixel  (kf_video_data ),\r\n"
    "                .out_vsync  (kf_video_vsync)\r\n"
    "            );\r\n"
    "        end\r\n"
    "        else begin : g_kf_bypass\r\n"
    "            assign kf_video_valid = sh_video_valid;\r\n"
    "            assign kf_video_data  = sh_video_data ;\r\n"
    "            assign kf_video_vsync = sh_video_vsync;\r\n"
    "            assign kf_arvalid = 1'b0;\r\n"
    "            assign kf_araddr  = {AXI_ADDR_WIDTH{1'b0}};\r\n"
    "            assign kf_arlen   = 8'd0;\r\n"
    "            assign kf_arsize  = 3'd0;\r\n"
    "            assign kf_arburst = 2'b01;\r\n"
    "            assign kf_arlock  = 1'b0;\r\n"
    "            assign kf_arcache = 4'd0;\r\n"
    "            assign kf_arprot  = 3'd0;\r\n"
    "            assign kf_arid    = 4'd0;\r\n"
    "            assign kf_rready  = 1'b1;\r\n"
    "        end\r\n"
    "    endgenerate\r\n"
    "\r\n"
    "    // wire video_rst"
)
patch("source/ov5640/ov5640_top.v",
      "    endgenerate\r\n\r\n    // wire video_rst",
      KF_GEN)

patch("source/ov5640/ov5640_top.v",
      "        .s_data         (sh_video_data ),\r\n"
      "        .s_data_valid   (sh_video_valid),\r\n"
      "        .s_hsync        (video_hsync),\r\n"
      "        .s_vsync        (sh_video_vsync),",
      "        .s_data         (kf_video_data ),\r\n"
      "        .s_data_valid   (kf_video_valid),\r\n"
      "        .s_hsync        (video_hsync),\r\n"
      "        .s_vsync        (kf_video_vsync),")

patch("source/ov5640/ov5640_top.v",
      "        .cam_data_addr_2(cam_addr_2),",
      "        .cam_data_addr_2(cam_addr_2),\r\n"
      "        .prev_frame_base(kf_prev_base),")

print("ALL PATCHES APPLIED")
