# Frozen V7 DDR / gate simulation (2026-10-06)

## Scope and actual run

All new files are confined to `board_v7/rtl_diagnosis`. No board access, bitstream compilation, or production/frozen edits. Read root/project AGENTS; source inspection/search used Python `read_bytes()` and byte matching (GBK-safe).

From workspace root, actually executed twice, final run 14:56:42–14:57:04:

```powershell
python project/fpga_v8_migration/board_v7/rtl_diagnosis/run_ddr_boundary.py
```

Runner invokes `C:\modeltech64_10.6e\win64\vlog.exe -sv -work work` on frozen `whole_candidate_v7_route_01/rtl/ov5640_ddr_tc04.v`, frozen `inputs/source/ov5640/ov5640_ddr/{ov5640_ddr_w_en,ov5640_ddr_w,ov5640_ddr_w_ctrl}.v`, and the two local SV files. It then actually executes:

```text
C:\modeltech64_10.6e\win64\vsim.exe -c -voptargs=+acc -l ddr_boundary.log work.tb_ddr_boundary -do "onerror {quit -code 1}; run -all; quit -code 0"
```

Working directory: `rtl_diagnosis/ddr_modelsim`. Full compiler/runner command is printed by the runner. Final transcript: `ddr_modelsim/ddr_boundary.log`. Result: **19 full-size scenarios, 61 assertions, 0 failures**, simulated 58,375,926 ns; compile 0 errors/warnings, simulation 0 errors / one inherited ModelSim `-novopt` performance warning. Frozen file hashes were checked before/after and saved in `ddr_frozen_sha256.txt`.

Actual wrapper, gate, packer, and write controller run unchanged. Only the two vendor FIFOs use local behavioral models: 32→128 conversion with one-cycle registered read, followed by 128-bit FWFT output. No claim about vendor primitive timing, CDC, sensor capture, DMA completion/publication, or physical timing. AXI ready is always high, command ready high, dma_done/abort low; the frame stays in DATA so its short status is observable. All tests assert no overflow in the boundary sweep. No forced DUT registers or preloaded pixel counts; each full-size frame is clocked through RTL.

## Last real valid relative to next raw_sof

`delta = raw_sof sample clock - last REAL valid sample clock`. First SOF is followed by 12 idle clocks. Exactly 307200 valid samples are driven; the final seven are consecutive. VSYNC markers are one clock. Positive delta means the last real pixel precedes the next marker.

| delta | wrapper input snapshot | accepted / pixel_count | short | good | AXI beats |
|---:|---:|---:|---:|---:|---:|
| -3 | 307196 | 307196 | 1 | 0 | 38399 |
| -2 | 307197 | 307197 | 1 | 0 | 38399 |
| -1 | 307198 | 307198 | 1 | 0 | 38399 |
| 0 | 307199 | 307199 | 1 | 0 | 38399 |
| +1 | 307200 | 307200 | 0 | 1 | 38400 |
| +2 | 307200 | 307200 | 0 | 1 | 38400 |
| +3 | 307200 | 307200 | 0 | 1 | 38400 |

**No last-pixel NBA off-by-one was found for a legal complete frame whose final real valid precedes raw_sof, including exactly one clock earlier.** The completed count is visible to `capture_complete` at the following edge.

For delta=0, `!s_vsync` in w_en suppresses the real pixel; short uses the already accumulated 307199. The raw_sof branch latches the previous input count and assigns the coincident valid to the NEW interval. For negative delta, remaining tail valids lie at/after the boundary; capture_bad stops them. These tests drive 307200 total samples, but they are not 307200 real samples inside the old frame's SOF interval. Therefore they demonstrate a boundary/marker contract failure under overlap, not proof of false-short on a conforming old frame.

## Dummy pixel and VSYNC semantics

DDR length is 38400 128-bit beats = 307200 16-bit REAL pixels. It does not require a 307201st dummy to complete. A normal 307200-input frame produced 38400 beats/good, and 307201 inputs (one extra dummy) still produced exactly 307200 accepted/38400 beats/good. The extra sample is cut off by capture_complete.

Additional actual tests place raw_sof relative to the dummy:

| raw_sof minus dummy clock | wrapper input snapshot | accepted | short |
|---:|---:|---:|---:|
| -1 (marker on final REAL pixel) | 307199 | 307199 | 1 |
| 0 (marker on dummy) | 307200 | 307200 | 0 |
| +1 | 307201 | 307200 | 0 |

Thus normal trailing-dummy suppression cannot alone explain a missing REAL pixel. The workspace's W*H+1 rule is a preprocess contract, not a requirement that DDR store W*H+1. `cam_prep_link.v` explicitly injects a preprocess tail dummy. `ov5640_top.v:338–343` says median retimes sync and removes camera tail dummy; however, a comment must not establish that every current source path emits one. The examined frozen `cmos_capture.v:124–149` emits valid for completed input pixel bytes, with no explicit extra-frame-dummy generator; `ov5640_cdc.v:142–156` transfers pixel valids without an explicit dummy injector. The other capture investigation must identify the exact active capture implementation before asserting a source-domain 307201 contract.

VSYNC here is a frame-boundary/blanking level, not per-pixel valid. `raw_sof` is local to the DDR input (`s_vsync && !raw_vsync_q`), not necessarily the raw camera pin. w_en blocks pixels for the entire VSYNC high interval, detects its rising edge through registers, and admits a frame two clock edges after raw_sof sampling. In the frozen CDC, VSYNC level has a two-flop synchronizer separate from the pixel FIFO. That structural separation motivates further upstream relative-timing tests, but this DDR simulation does not establish that actual board streams overlap.

## First-pixel gate latency

A separate test drives 307200 valids strictly between SOF markers but varies idle clocks between a one-clock initial SOF and first valid:

| idle gap after initial SOF | wrapper input snapshot | accepted | short |
|---:|---:|---:|---:|
| 0 | 307200 | 307198 | 1 |
| 1 | 307200 | 307199 | 1 |
| 2 | 307200 | 307200 | 0 |
| 3 | 307200 | 307200 | 0 |

This is a real startup admission constraint: valids before DATA becomes active are lost even though raw input count is complete. It does NOT lower the wrapper's input snapshot, and cannot itself explain an upstream source count deficit. Whether an upstream producer promises at least this gap must be checked at its actual output; the 307200-count condition alone does not guarantee admission.

## Relation to board source evidence

**Do not equate the test log's `source=` with board `source_pixels`.** In this test it names `ov5640_ddr_tc04.dbg_input_pixels`, a post-filter/DDR-input SOF-window count. Board `diagnose_camera_input.py` maps `source_pixels` to **+0x190**, `cdc_pixels` to +0x1a0, `cdc_drops` to +0x1b0, and `post_filter_pixels` to +0x30. Frozen `ov5640_reg.v:270` maps +0x190 to `dbg_cdc_input`; `ov5640_cdc.v:213–234,267` captures that counter in the **camera/CDC write domain**, upstream of this DDR gate. The DDR gate has no feedback path to alter that source counter.

Controls with safely separated markers and 307199, 307198, 307193 inputs report the same accepted/input values and one short, with fault snapshots `4004afff`, `4004affe`, `4004aff9`. This confirms downstream rejection is expected if its input really is short; it does not explain how the upstream source acquired those deficits.

The board evidence (CAM1 intermittent source=307199/198/193, CDCdrops=0; CAM2=307200; delay 0..240 remains short with variable repetitions) is therefore **not explained solely by the DDR gate**. A source-domain VSYNC/count window shift could in principle reassign samples between intervals; the separate counter/capture tests must establish that at the actual source boundary. Coincident valid is assigned to the next interval, not simply erased by the diagnostic counter, so repeated-frame conservation matters. No hardware root cause, cable conclusion, or claim that zero CDC drops rules out all RTL timing issues follows from these tests.
