# -*- coding: utf-8 -*-
"""patch_top.py -- byte-exact patches: wire cam1 vip_kf_stream read master to
crossbar slave S05 (npu_s3_*). Idempotent.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "source/top.v"


def patch(old, new):
    p = os.path.join(ROOT, PATH)
    d = open(p, "rb").read()
    O = old.encode("ascii")
    N = new.encode("ascii")
    if N in d:
        print("SKIP  (already) :: %s" % new[:56])
        return
    c = d.count(O)
    if c != 1:
        print("FAIL  count=%d :: %s" % (c, old[:70]))
        sys.exit(1)
    open(p, "wb").write(d.replace(O, N, 1))
    print("ok    :: %s" % new[:56])


# 1) enable KF on cam1
patch("    .MEDIAN_EN     (1'b0)        , // [MEDIAN] cam1/left path only; cam2 remains raw\n"
      "    .MEDIAN_RSVD   (3'd0)\n"
      ") ov5640_top(",
      "    .MEDIAN_EN     (1'b0)        , // [MEDIAN] cam1/left path only; cam2 remains raw\n"
      "    .MEDIAN_RSVD   (3'd0),\n"
      "    .KF_EN         (1'b1)        , // [VKFS] cam1 temporal filter over the DDR previous frame\n"
      ") ov5640_top(")

# 2) cam1 KF read-master ports -> crossbar S05
patch("    .cam_dma_done(cam_dma_done),\n"
      "    .xdma_clk (pcie_clk) ,\n"
      "    .xdma_irq (cam_irq ) \n"
      "\n"
      ");",
      "    .cam_dma_done(cam_dma_done),\n"
      "    .xdma_clk (pcie_clk) ,\n"
      "    .xdma_irq (cam_irq ) ,\n"
      "\n"
      "    // [VKFS 2026-09-25] previous-frame read master -> crossbar S05 (npu_s3_*)\n"
      "    .kf_arvalid (npu_s3_axi_arvalid),\n"
      "    .kf_arready (npu_s3_axi_arready),\n"
      "    .kf_araddr  (npu_s3_axi_araddr ),\n"
      "    .kf_arlen   (npu_s3_axi_arlen  ),\n"
      "    .kf_arsize  (npu_s3_axi_arsize ),\n"
      "    .kf_arburst (npu_s3_axi_arburst),\n"
      "    .kf_arlock  (npu_s3_axi_arlock ),\n"
      "    .kf_arcache (npu_s3_axi_arcache),\n"
      "    .kf_arprot  (npu_s3_axi_arprot ),\n"
      "    .kf_arid    (npu_s3_axi_arid   ),\n"
      "    .kf_rready  (npu_s3_axi_rready ),\n"
      "    .kf_rid     (npu_s3_axi_rid    ),\n"
      "    .kf_rdata   (npu_s3_axi_rdata  ),\n"
      "    .kf_rresp   (npu_s3_axi_rresp  ),\n"
      "    .kf_rlast   (npu_s3_axi_rlast  ),\n"
      "    .kf_rvalid  (npu_s3_axi_rvalid )\n"
      "\n"
      ");")

# 3) drop the S05 tie-off: it is now driven by cam1's read master
patch("// S04/S05/S06 read (npu_s2/s3/s4)\n"
      "assign npu_s2_axi_arvalid  = 1'b0;\n"
      "assign npu_s2_axi_rready   = 1'b1;\n"
      "assign npu_s3_axi_arvalid  = 1'b0;\n"
      "assign npu_s3_axi_rready   = 1'b1;\n",
      "// S04/S05/S06 read (npu_s2/s3/s4)\n"
      "assign npu_s2_axi_arvalid  = 1'b0;\n"
      "assign npu_s2_axi_rready   = 1'b1;\n"
      "// [VKFS 2026-09-25] S05 (npu_s3) is driven by cam1's vip_kf_stream read master\n"
      "// (was tied off). Keep S02/S04/S06 tied off.\n")

print("TOP PATCHES APPLIED")
