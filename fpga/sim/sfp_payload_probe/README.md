Isolated actual-TX payload and RX pair-deletion probe, 2026-10-03.

Run `python run_probe.py` then `python analyze.py` in this directory. Requires
ModelSim at C:/modeltech64_10.6e/win64. No PDS build or production/IP edits.
summary.json records SHA256 of the production TX, RX aligner and decoder;
run_probe.py verifies that these bytes did not change during the experiment.

A source is the 614400-byte saved RGB565 frame from
log/six_50k_pins_fixed_board_20261003/cam5.rgb565 (640x480, little endian).
B is synthetic: rows alternate zero, 0x50BC, and a 16-bit value scan.
This is not a capture of actual sensor B. Actual production sfp_video_tx.v
and video_async_fifo.v produce actual.vec from the 1280x480 merged image,
with continuous DE for 640 A + 640 B and 648 blank input cycles per row.
The production RX wrapper (including same-cycle alignment fix) and decoder
receive this byte/K stream through the existing HSST stub. This is a parallel
replay, not physical 8b10b/PCS/CTC simulation.

| Injected mutation | Pair events | Decoded pixels | Exact payload | SOF | Overflow |
| --- | ---: | ---: | --- | ---: | ---: |
| None | 0 | 614400 | yes | 1 | 0 |
| BC(K)/28(D) in last control before B, every fourth row | 120 | 614160 | no | 1 | 0 |
| Same pair, one control earlier | 120 | 614400 | yes | 1 | 0 |
| All BC(K)/50(D) cross-boundary matches | 424 | 613552 | no | 1 | 0 |

Each mutation removes two symbols from the continuous byte/K stream and then
repacks it into four-byte words. No discontinuous word rotation is substituted
for deletion. The before-B case removes exactly 240 original B pixels and
zero original A pixels; every surviving pixel matches its original value and
order. BC/50 deletion removes exactly 48 original A + 800 original B pixels,
also preserving all survivors exactly. K=0 payload bytes 0xBC and 0x50 never
form a K-qualified skip pair by themselves. Actual BC(K)/50(D) matches occur
when the final K28.5 of a control precedes a data word whose low byte is 0x50.
All 424 such matches in this capture cross a 32-bit word boundary.

CRITICAL COUNT INTERPRETATION: production sfp_rx_cam_if counts DE pixels modulo
1280 from SOF and routes the first 640 to CAM5. It does not reset at row gaps.
For any total 614400-D with 0 <= D <= 640, regardless of where pixels vanished,
CAM5 gets 307200 and CAM6 gets 307200-D (assuming no separate FIFO loss).
Thus board CAM5=307200, CAM6=306938..306970 DOES NOT prove B-selective loss.
The injected 240-pixel case predicts CAM5=307200, CAM6=306960 purely from this
splitter rule. Count validity also does not prove CAM5 image integrity: missing
pixels earlier in the frame shift subsequent A/B assignment. Splitter counts
in summary.json are computed from this rule, not separately simulated CDC.

The inspected production 100H hsst_sfp.v has GE/2SKIP with
SKIP_REG0=0x1BC and SKIP_REG1=0x050, whereas actual TX controls contain BC/28.
The literals prove a configuration/comment discrepancy. They DO NOT prove
what GE automatic mode deletes, or that a deletion occurred on the board.
Installed vendor pcs_ctc_ge_auto_data.vp and pcs_ctc_del_data_pro.vp models
are encrypted; their presence provides no readable algorithm evidence.
Dark zero pixels are not BC(K)/50(D) matches. A 230..262 board deficit is
consistent with 115..131 two-pixel losses but is not evidence of that cause.

Next diagnostic instrumentation (proposal only, no production changes):

1. 50K: latch per-frame merge input DE count, TX FIFO accepted DE count,
   FIFO full/drop count, and actual emitted K=0 words times two. Include
   CRC over emitted data words and cross-boundary BC(K)/50(D) match count.
   Counts alone cannot separate image identity/order failures.
2. 100H: latch raw K-mask histogram, raw decoder/disparity error counts,
   raw cross-boundary BC/50 and BC/28 counts, alignment phase-change count,
   aligned K=0 word count, decoded DE count, CRC, and frame sequence.
   Preserve a small raw {data,K,error} trace around a rotation change,
   including preceding control and following payload words. Pre/post aligner
   counts localize alignment losses; they do not expose internal PCS deletion.
3. Compare 50K wire count/CRC with 100H aligned count/CRC on the same frame.
   If wire count is short, inspect upstream merge/TX. If wire count is full
   but received payload is short, investigate link/PCS/alignment using trace.
   Raw errors and phase changes help distinguish possible mechanisms.
4. LEDs can provide latched count-mismatch/full/error indications. Exact
   frame counters and traces require a configured JTAG debug core or a new
   readable register path. No existing JTAG counter read interface was
   established by this probe. Link-ready LEDs alone cannot diagnose loss.
