#!/usr/bin/env python3
# Byte-level (GBK-safe) patch to top.v:
#   1) add a single-outstanding read gate to the DDR3 read bridge so that
#      ddr_axi_ar_sid (the high 3 bits of the R-channel routing ID) is always
#      correct.  Without it, a 2nd AR from a *different* slave (cam1 KF on S05)
#      latching before the 1st read's RLAST retags the earlier burst's data with
#      the wrong slave ID, the host read never completes, and crossbar M00 wedges.
#   2) re-enable cam1's KF previous-frame read (KF_RD_EN=1).
# Idempotent.
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = os.path.join(ROOT, 'source', 'top.v')

OLD_LATCH = b"wire ar_latch_now    = ddr_axi_arvalid && !ddr3_ar_v && ddr_axi_fifo_empty;"
NEW_LATCH = (
    b"// [VKFS 2026-09-26] single-outstanding DDR read gate.  The bridge keeps ONE\r\n"
    b"// ddr_axi_ar_sid register for R-channel routing; allowing a 2nd AR to latch\r\n"
    b"// (from a different slave, e.g. cam1's KF on S05) before the 1st read's RLAST\r\n"
    b"// retags the earlier burst with the wrong slave ID -> host read never\r\n"
    b"// completes -> crossbar M00 read channel wedges.  Host frame DMA (S00) and\r\n"
    b"// KF prefetch (S05) are both low-bandwidth, so serialising is free here.\r\n"
    b"reg  rd_inflight;\r\n"
    b"wire ar_latch_now    = ddr_axi_arvalid && !ddr3_ar_v && ddr_axi_fifo_empty && !rd_inflight;\r\n"
    b"always @(posedge axi_clk) begin\r\n"
    b"    if (axi_rst)                                rd_inflight <= 1'b0;\r\n"
    b"    else if (ar_latch_now)                      rd_inflight <= 1'b1;\r\n"
    b"    else if (ddr_axi_rvalid_ddr3 && ddr_axi_rlast_ddr3) rd_inflight <= 1'b0;\r\n"
    b"end"
)

RD_OFF = b".KF_RD_EN      (1'b0)         // [RDTEST 2026-09-25] previous-frame DDR read DISABLED (isolation)"
RD_ON  = b".KF_RD_EN      (1'b1)         // [VKFS] previous-frame DDR read enabled (bridge single-outstanding fix in place)"


def main():
    with open(TOP, 'rb') as f:
        b = f.read()

    # --- 1) bridge gate ---
    if NEW_LATCH in b:
        print('  [skip] bridge gate: already applied')
    elif b.count(OLD_LATCH) == 1:
        b = b.replace(OLD_LATCH, NEW_LATCH, 1)
        print('  [ok]   bridge single-outstanding read gate')
    else:
        print('  [FAIL] bridge gate: pattern count=%d' % b.count(OLD_LATCH))
        return 1

    # --- 2) re-enable KF read ---
    if RD_ON in b:
        print('  [skip] KF_RD_EN: already enabled')
    elif b.count(RD_OFF) == 1:
        b = b.replace(RD_OFF, RD_ON, 1)
        print('  [ok]   cam1 KF_RD_EN=1')
    else:
        print('  [FAIL] KF_RD_EN: pattern count=%d (off=%d on=%d)' % (
            b.count(RD_OFF) + b.count(RD_ON), b.count(RD_OFF), b.count(RD_ON)))
        return 1

    with open(TOP, 'wb') as f:
        f.write(b)
    print('RESULT: OK')
    return 0


sys.exit(main())
