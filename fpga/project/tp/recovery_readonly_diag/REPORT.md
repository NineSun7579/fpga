# cam1/cam2 rejection diagnosis — 2026-09-27

Board access and diagnostic RTL work completed without PDS, programming, FPGA register writes, SCCB transactions, or PLL changes. This is a diagnostic patch, not a proven cure for the rejection. Existing bitstream does not expose enough information to distinguish overflow from short input; no data-path repair is justified yet.

## Board evidence

`tools/diagnose_recovery_readonly.py` killed run_camview.sh first, then camview, reloaded pango_pci_driver, opened PciDriver exactly once, and read all 16 aligned camera registers 21 times over 5.130902 s. Its finally block reloaded the driver and restarted the watchdog. Final process evidence: camview PID 2844, run_camview.sh PID 2840. `session.log` contains commands and output, `registers.json` contains the raw samples. No deploy/burn helper was executed.

| Camera | PCLK delta | processed/raw VSYNC delta | HREF rising delta | successful tag delta |
|---|---:|---:|---:|---:|
| 1 | 431003013 (~84 MHz) | 231 / 231 | 110894 | 21 (2 -> 23) |
| 2 | 431046040 (~84 MHz) | 231 / 231 | 110907 | 21 (2 -> 23) |
| 3 | 246338814 (~48 MHz) | 132 / 132 | 63384 | 111 (5037 -> 5148) |

These are sequential reads, not atomic snapshots; the PCLK counters cross clock domains without coherent sampling. Rate estimates should not be used as precision clock measurements. HREF/VSYNC is approximately 480 per frame on all cameras. In the first 1.800882 s, cam1/2 each had 81 VSYNCs and zero successes; cam3 had 46 VSYNCs and 46 successes. Later, cam1 and cam2 started succeeding together at about 6/s while cam3 lost some frames. Thus prior zero-success observation is reproducible as a time window, but not a permanent inability to produce any accepted frame.

In the early failure window, cam1/2 +A0 frequently reads 2288..2400 accepted 128-bit beats and then zero; full payload is 38400 beats / 307200 pixels. +60 frequently reads state=IDLE, and its low command counter advances about once per VSYNC (252 commands versus 231 VSYNC and 21 tags across the whole observation). There is continuing capture/retry activity, not a permanently stuck owner. +B0=2 while success remains 2 is a retained old bank request; it does not imply current capture success.

No excess raw VSYNC edge count appears over these intervals; cam1/2 have filtering disabled while cam3 uses 64 PCLK samples. This does not prove absence of a very short pulse or CDC loss, but does not justify blindly applying cam3's filter. The synchronized cam1/cam2 success windows and failures early in the frame make shared service/backpressure and FIFO capacity a useful next hypothesis. They do not prove overflow: current registers expose neither capture_bad cause nor pixel_count.

## Actual old register decode

Source of truth: `source/ov5640/ov5640_reg.v` read case, not localparam names or historical comments.

| Offset | Old live read meaning |
|---|---|
| +00 | transient xdma_ack pulse, usually zero |
| +10 | free-running PCLK counter |
| +20 | video_vsync rising count |
| +30 | cam_s_data_valid cycles, including backpressure; NOT input pixels |
| +40 | cam_en |
| +50 | dbg_i2c_status (all zero in samples; not zero-pixel count) |
| +60 | {state-age[7:0], state[7:0], command count[15:0]} |
| +70 | {B count[15:0], AW count[15:0]} |
| +80 / +C0 | configured DDR bank addresses |
| +90 | raw HREF rising count |
| +A0 | accepted camera stream beats in current video frame |
| +B0 | bank valid/request bits |
| +D0 | sensor/SCCB status, observed 0x420D; NOT DMA address |
| +E0 | raw VSYNC rising count |
| +F0 | successful tag publication count |

## Diagnostic RTL patch

Only `source/ov5640/ov5640_ddr/ov5640_ddr.v`, `source/ov5640/ov5640_top.v`, and `source/ov5640/ov5640_reg.v` changed. Each has an exact prior `.rejection_diag.bak`. `rejection_diag.diff` is a review copy and `source_hashes.txt` identifies the final files. Python byte replacement preserved all original non-ASCII lines. No top-level camera parameter or DMA/arbiter/FIFO control expression changed. The new registers have no feedback into capture or DMA control.

| Offset | New read meaning |
|---|---|
| +00 | retained last fault snapshot: bit31 overflow, bit30 short at next SOF, bit29 DMA abort without an already latched source fault, bit28 non-payload phase, bits27:0 accepted pixels at the fault |
| +30 | total offered `kf_video_valid` pixels between the last two raw SOFs at the DDR wrapper; independent of admission, flush and quota |
| +50 | {minimum, last} completed video_vsync high pulse widths, each 16 bits in video_clk cycles, saturating at 65535 |
| +A0 | {overflow events[15:0], short events[15:0]}, modulo counters; one event per failed capture, retained through flush |

ACK writes at +00, delay writes at +30 and all remaining write behavior are preserved. +D0 and +F0 retain their old meanings. +50 replaces currently uninformative SCCB ID diagnostics; raw VSYNC/HREF counts remain available at +E0/+90. Pulse widths are measured after the existing sensor filter/capture/CDC, before FIR; for cam1/2 (filter bypass) this exposes short pulses that survive CDC. It does not measure rejected cam3 glitches or pulses lost by CDC. The minimum can include the first partial post-reset pulse. Input pixels count an SOF-coincident valid in the new interval; +30 latches only at the next SOF. No additional register page or undocumented +100 access is required.

Snapshot is the latest failure, retained over successes until a new failure/reset. Bit29 separates DMA-only aborts from source faults, but does not distinguish watchdog from BRESP without more DMA instrumentation. A simultaneous short+overflow can set/count both. A read of multiple fields is not atomic; sample repeatedly and compare counters.

## Tests

Run `python sim/dma_timeout_repro/run_rejection_diag.py` from project, or run it in that directory. Final `rejection_suite.log` checks PASS markers and rejects simulator Fatal/Error text, rather than trusting exit status alone.

* Behavioral FIFO: PASS; 10 successes, 7 aborts, AW/B=61/61, 75 zero-strobe filler beats.
* Actual Pango FIFO RTL/primitives: PASS; 10 successes, 7 aborts, AW/B=1425/1425, 75 zero-strobe filler beats; natural full-FIFO fault around accepted pixel 8331.
* New assertions: exact short snapshot=13, watchdog snapshot=11, natural overflow classified/counts once, counters retained across flush, full offered interval count=512 / 16384.
* Every successful frame remains checked pixel by pixel including first/last, with tags/banks/requests, AW/W stability, WLAST, actual B retirement, and no premature flush.
* Register read-case simulation: PASS for new offsets and unchanged +D0/+F0; ACK/delay/enable writes preserved. ov5640_top compiled with the register test. Unconnected diagnostic-only ports in the standalone register TB generate warnings; vendor FIFO water-level warnings are pre-existing.

The first diagnostic test version incorrectly expected the final full interval to be latched before its next SOF. It was corrected to issue the next SOF before checking. No RTL behavior was changed to satisfy that assertion. Final logs supersede that failed exploratory run. No full-top elaboration, sensor-to-DDR full-resolution simulation, timing closure, or board validation of this patch is claimed. VSYNC width logic has compiled but has no dedicated pulse-width simulation here.

## Initial FIFO / synchronization assessment and next action

Existing recovery flush resets packer phase and both DDR capture FIFO validity/pointers for four axi_clk cycles only after legal DMA retirement. It does not reset the upstream asynchronous pixel FIFO or align that FIFO's pixels to the separate VSYNC synchronizer. Existing boundary evidence in `sim/dma_timeout_repro/boundary_report.md` shows at least three axi_clk edges from sampled short SOF to first pixel are needed; gap=2 can lose pixel zero and a trailing dummy can conceal that loss. None of today's old-bit register readings measures that actual gap. It is therefore not evidence that this boundary is the current cause.

Main session should build/program this diagnostic patch using its authorized flow, then run the same read-only survey during both a zero-success window and a partial-success window. For each camera compare +30 with quota 307200, +00 low28 with quota, +A0 changes, +50 widths and +20/+E0 deltas.

1. Overflow rising with input=307200 and failure pixels well below quota: quantify incoming pixels minus consumed beats*8 (using additional live instrumentation if needed), shared DDR service gaps, and FIFO capacity. Preserve AXI ownership through real B; fix buffering/service only after reproducing the measured stall envelope.
2. Short rising with offered pixels below 307200: investigate upstream capture/HREF/CDC losses. If offered is exactly 307200 but admitted count is smaller, investigate SOF-to-first-valid and local admission/flush alignment.
3. Short rising with tiny VSYNC width or extra raw edges: reproduce pulse behavior before choosing a filter. Do not change PCLK or waive validity.
4. DMA-only aborts: add/watch explicit BRESP and starvation cause, since this patch cannot separate them.

The board is restored to camview on the original bitstream. Root-cause data-path repair remains blocked on this new evidence; no speculative frequency, filtering, quota or AXI change was made.
