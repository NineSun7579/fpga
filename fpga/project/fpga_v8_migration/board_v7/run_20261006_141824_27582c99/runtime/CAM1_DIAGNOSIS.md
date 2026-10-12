# CAM1 input diagnosis

CAM1 is local CMOS1, not SFP. Diagnosis used the frozen V7 register mapping and exclusive finite read-only transfers. Input diagnosis and compact repeat both completed without DMA exceptions.

Thirty wide samples showed CAM1 source/post-filter counts of 307199 or307200; observed CDC drop counts were0. CAM1 DDR reject counts changed7918→7949, all in short-frame low16 bits, with high16 overflow0. Fault snapshot1074049023 = 0x4004afff, short-frame bit30 plus307199 pixels. CAM2 input remained307200 and reject count0. Wide CAM1 samples all crossed a source sequence boundary, so they do not establish an atomic per-frame correlation across all fields. CAM1 publication count13255→13503 shows that later valid frames exist; initial failure is not permanent total capture loss.

Compact sampling read sequence/input/drop/sequence. Of60 CAM1 samples,44 kept the same source sequence:38 input counts307200 and6 input counts307199, all drops0. Of60 CAM2 samples,50 were stable and all input counts307200/drops0. This directly verifies intermittently short captured source frames. No claim is made about the fraction of all physical frames, because samples can duplicate or omit frames.

Observed scope: CAM1 DVP capture or upstream input timing can produce a one-pixel short frame. Sensor/electrical timing versus capture boundary logic is unresolved. CDC drop=0 is only the sampled prior-frame statistic, not an exhaustive no-loss certificate. Motion flags4 alone cannot distinguish queue overflow, short frame or excess pixels. Internal motion error counters are not exported. No RTL, production source, constraints, IP or Flash were changed for these diagnostics.

## Further frozen-source review

One wide-sample stored DDR fault was0x4004affd, short-frame with307197 pixels; the other recorded short faults were307199. Thus not every observed DDR short frame was exactly one pixel short. Stable compact source-window samples established307199 only for those sampled windows, not every rejected frame.

Frozen default IODELAY steps differ: CAM1=140, CAM2=40. Both use identical geometry and VSYNC qualification0 and both instantiate FIR. Runtime register writes may override delay. `REG_DLY_STEP` at camera base+0x30 is write-only for this purpose: read decode at that address returns post-filter pixel count, not dly_step. No direct runtime readback exists in this V7 ABI, so reading it cannot verify actual delay.

Candidate mechanisms remain HREF sampling/byte-pair interruption and VSYNC count-window boundary ownership. CDC source counters latch old count on frame start and assign coincident valid to the new window; a307199 window is therefore not independent proof of sensor loss. Independent VSYNC and FIFO pixel transport, downstream VSYNC valid gating, and DDR old-count SOF judgement also need cycle-level boundary evidence. Do not pad pixels, weaken307200 length acceptance or choose a timing/RTL correction from the current trace alone.

The later followup trace passed all28 motion snapshot checks and CAM1 publication resumed. This bounds the observed error as intermittent rather than permanent, without clearing the recorded source/DDR failures.

## Actual RTL simulation evidence

See `../../source_counter_diagnosis/REPORT.md` (under board_v7). ModelSim compiled the frozen capture/counter RTL and checked3,369,986 cycles. Normal1280-byte lines ×480 produced307200 valid pulses. Sparse/continuous/random increments and all nibble carry boundaries matched the reference model. Coincident source-frame-start/valid moved a pixel between count windows:307199+307201=614400, without loss. Artificial odd HREF fragments and shortened byte input reproduced actual valid deficits, but those stimulus conditions are not established for this board.

The FIFO was a stub, so these results do not validate actual FIFO data transport or DDR. Normal snapshot events30/30 were received; an intentionally unrealistic4ns frame interval lost notifications. This does not establish a normal-frame CDC failure. No source-counter arithmetic bug or hardware defect is demonstrated. DDR boundary simulation remains a separate pending check. The user's selected direction is local RTL diagnosis, not physical camera/cable exchange.

## Integration and sensor-configuration limits

Subsequent `../../capture_boundary_integration/REPORT.md` joins capture, actual negedge stage, vendor FIFO models, FIR and DDR control.649 scenarios completed with zero assertion errors, including explicitly expected stressed failures. For12ns camera /16ns video periods and1PCLK tail blank, source snapshot and total FIFO output both remained307200/drop0, but the output frame window and DDR admission were307199. Increasing tail blank to3PCLK restored publication. This demonstrates independent VSYNC overtaking queued tail pixels under that stimulus; it still cannot explain the observed upstream source-count deficit.

The recorded board VSYNC-width word388241189=0x17241725 means minimum5924/recent5925 video-clock high cycles, measured after CDC and before FIR. It does not measure last-HREF-to-VSYNC spacing. Frozen sensor initialization is the same forCAM1/2 (PLL54, geometry640x480, HTS1896, VTS984, SCCB address0x3c); their default input delays and DDR/control addresses differ. No runtime sensor readback establishes the untouched sync-mode register values. Neither VTS-minus-height nor the VSYNC pulse width establishes the tail blank. Accordingly the1PCLK simulation remains a boundary stress reproduction, not a verified board waveform or root cause. The isolated CDC candidate must cover long VSYNC levels as well as short-tail stress and preserve exact pixel ordering/counts; it must not weaken frame-length acceptance.
