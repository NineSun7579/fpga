# Actual violating paths — run_20261003_192131

Read-only analysis; no PDS invocation and no RTL changes. Only this file is owned/written by this subagent. Frozen sources are under `project/motion_100h/run_20261003_192131/inputs/source/`.

## Result

The dominant failure is **history RAM output → absolute difference / threshold → detector state clock enables**, not sample-counter increment or history address arithmetic. There are also wide block-counter selection paths and long frame-start control paths. **304 of 309 failing setup endpoints are in motion detectors; five are existing DDR diagnostic snapshot endpoints.** All eight recovery failures belong to camera 6's detector reset distribution.

Actual report: `project/motion_100h/run_20261003_192131/final_sta/report_timing/top.rtr`, 2,098,480,827 bytes, dated Oct 3 20:30:10 2026. Parsed with binary line iteration, holding at most one path block in memory; only selected path blocks were decoded. A full streaming marker scan found exactly 309 violated setup paths and eight violated recovery paths, matching the report summaries. Subsequent detail inspection sought directly to the violating path regions. Byte offsets below refer to this report.

| Evidence | DDR slow setup WNS / TNS / endpoints | DDR slow recovery WNS / TNS / endpoints |
| --- | --- | --- |
| Preserved baseline `project/motion_100h/baseline/top_timing_summary_after_hold_fix.txt` | +0.796 / 0 / 0 | +2.666 / 0 / 0 |
| Current `routed/top_timing_summary_after_hold_fix.txt` | −0.335 / −35.092 / 255 | −0.170 / −0.434 / 8 |
| Actual final STA `final_sta/report_timing/top.rtr` | **−0.398 / −52.576 / 309** | **−0.221 / −0.868 / 8** |

All values are ns. The target DDR/AXI period is 7.619 ns (131.25 MHz). Both current analyses fail; the final report worsens setup WNS by 0.063 ns and recovery WNS by 0.051 ns relative to the router summary. Those differences alone do not identify the timing-engine/model cause. Final slow DDR hold slack is +0.246 ns, with zero failures; fast hold also passes.

## Setup endpoint inventory

Counts and TNS below were computed from all 309 negative setup path blocks (`-nworst 1` gives the reported worst path per endpoint). Instance prefixes are exact report hierarchy names.

| Detector instance prefix | Endpoint register | Count | Worst slack | Sum slack |
| --- | --- | ---: | ---: | ---: |
| `ov5640_top/u_motion_tap` (cam1) | `bitmap_work` | 192 | −0.398 | −39.092 |
| `ov5640_top/u_motion_tap` | `blocks_work` | 7 | −0.268 | −1.502 |
| `ov5640_top/u_motion_tap` | `bbox_work_valid` | 1 | −0.113 | −0.113 |
| `cam2_ov5640_top/u_motion_tap` | `block_hits` | 72 | −0.270 | −7.415 |
| `cam2_ov5640_top/u_motion_tap` | `bitmap_work` | 6 | −0.148 | −0.640 |
| `cam3_ov5640_top/u_motion_tap` | `bitmap_work` | 4 | −0.380 | −1.520 |
| `cam3_ov5640_top/u_motion_tap` | `block_hits` | 1 | −0.086 | −0.086 |
| `cam4_ov5640_top/u_motion_tap` | `bitmap_work` | 8 | −0.130 | −0.696 |
| `cam4_ov5640_top/u_motion_tap` | `block_hits` | 1 | −0.088 | −0.088 |
| `u_cam6_motion` | `block_hits` | 4 | −0.138 | −0.552 |
| `u_cam6_motion` | `bitmap_work` | 8 | −0.077 | −0.324 |

Cam5's detector has no reported negative setup endpoints. Remaining five endpoints:

- `cam5_ov5640_ddr/dbg_fault_snapshot[19]/opit_0_inv/CE`: −0.152 ns; launch `u_sfp_rx_cam_if/u_fifo5/rbin[3]/opit_0_inv_AQ_perm/CLK`.
- `cam3_ov5640_top/ov5640_ddr/dbg_fault_snapshot[{19,21,26,27}]/opit_0_inv/CE`: each −0.099 ns; launch `ddr3/u_ddrphy_top/ddrphy_dfi/dfi_init_complete/opit_0_inv_L5Q_perm/CLK`.

Total sum is −52.576 ns. No failing setup endpoint in this inventory is `sample_address`, `pixel_count`, or x/y coordinate state.

## Critical setup paths and source interpretation

**Worst setup, byte offset 79,433,044:**

```text
Startpoint: ov5640_top/u_motion_tap/u_detector/history_1/gopdrm_36k/CLKA[0]
Endpoint:   ov5640_top/u_motion_tap/u_detector/bitmap_work[78]/opit_0_L6Q_perm/CE
Slack: −0.398 ns; arrival 13.007 ns; required 12.609 ns
Clock skew: −0.235 ns; logic levels 5
Data-path logic: 2.493 ns (33.662%); route: 4.913 ns (66.338%)
```

The path is RAM QA → `history_q[1]` → magnitude comparison → subtraction selection (`nb0[4]`) → subtraction carry/output → `difference[7]` → `N2323` → bitmap CE. RAM clock-to-output is 1.565 ns. `difference[7]` has fanout 195 and a 2.080 ns route; `N2323` has fanout 200. The first four endpoints, bitmap bits 78/87/110/126, all have −0.398 ns slack. All 200 cam1 failures launch from `history_1`; all 78 cam2 failures launch from `history_3`.

Frozen `motion/block_motion_detector.v`:64–73 implements read-first synchronous history RAM; lines 80–81 compute the unsigned absolute difference; lines 179–190 combine pixel threshold, selected saturating block hit count, bitmap update and statistics/bbox update in the next cycle. This is the relevant pipeline boundary.

**Cam3 marker/control path, offset 79,483,018:** FIR `out_valid` → `kf_video_valid` → adapter `push` → `overflow` → `core_start` → detector `N2323` → bitmap bit 136 CE. Slack −0.380 ns; four logic levels; logic 0.978 ns, route 6.460 ns (86.851%). `core_start` fanout is 419; final enable fanout is 199. Four cam3 bitmap endpoints share this failure family. Merely pipelining the arithmetic does not directly cut this marker path.

**Cam4 wide block selection, offset 81,993,486:** `block_q[4]` → block-hit selection muxes (`N1300`) → threshold/update-enable logic → `N2323` → bitmap bit 72 CE. Slack −0.130 ns; logic 1.266 ns, route 5.926 ns. `block_q[4]` fanout is 577. Cam6 has the same family from `block_q[6]/opit_0_L6QL5Q1_perm/CLK` to bitmap bit 139 CE (offset 82,566,604), slack −0.077 ns, six levels, route 5.813 ns; the packed launch output drives `block_q[5]`, fanout 579. This substantiates the large dynamically selected saturating-counter bank as a secondary bottleneck.

**Cam6 marker/control path, offset 81,894,526:** FIFO6 read-pointer → distributed-RAM VSYNC output → adapter `rise` → `core_start` → block_hits[99][0] CE (also bits 1/2/3). Slack −0.138 ns; logic 1.169 ns, route 6.040 ns; core_start fanout 207.

**Existing DDR snapshot paths:** Cam5 (offset 81,781,197) traverses FIFO5 read-address/memory/mux → raw_sof → capture_open logic → snapshot CE, with 6.069 ns routing (84.374%). Cam3 (offset 82,392,989) traverses dfi_init_complete → ddr_init_done (fanout 2857, route 2.314 ns) → capture_overflow → snapshot CE, with 6.272 ns routing (87.708%). These require rechecking after detector changes; a detector pipeline alone does not guarantee they disappear.

## Recovery paths

All launch from `sfp_status_bits[1]/opit_0/CLK`, and all end under `u_cam6_motion/u_detector`:

- `min_x_work[3]/opit_0/RS`: worst, −0.221 ns.
- `block_hits[148][2]/opit_0/RS` and `[148][3]`: −0.145 ns each.
- `block_hits[136][2]/opit_0/RS` and `[136][3]`.
- `min_x_work[0]/opit_0/RS`, `[1]`, `[2]`.

The first violating recovery block is immediately before byte offset 695,249,077 (the latter starts block_hits[148][2]). Worst-path arrival is 12.851 ns vs required 12.630 ns; 20 levels, logic 1.807 ns, route 5.483 ns (75.213%). It traverses status bit Q → 2.780 ns status route → detector reset-combine `N78` → 2.703 ns route with fanout 464 → a long sequence of physical `RSCO`/`RSCI` reset cascade arcs (mostly 0.075 ns each) → min_x_work RS. This is reset distribution, not pixel-data arithmetic.

Frozen `top.v`:1792–1793 combines `~axi_rst`, `sfp_sigdet_sync[1]`, and sfp_status_bits[3/1/0] into `sfp_motion_rst_n`; both SFP adapters use it. `motion_stream_adapter.v`:67 further combines reset with `!overflow_reset`. The detector's entire state/counter bank uses asynchronous reset at `block_motion_detector.v`:92–128. Thus link-status release and overflow recovery drive a large asynchronous reset network.

## Minimal fixes recommended to parent

1. **Add one detector compare/update stage.** Register the changed-pixel decision after absolute difference/threshold, together with pending/enabled and block/bbox metadata; consume this registered decision for counter/bitmap/statistics updates. This cuts the history-RAM path to the large state-enable network. To address the secondary block_q mux path in the same stage, capture the selected block-hit count alongside that decision, then perform saturation/threshold/update in the following stage. If a previous update targets the same block while the count is being captured, forward the newest count (or use equivalent per-block local update logic); neighboring accepted samples can hit the same block in consecutive cycles. Avoid silently using a stale count.
2. **Preserve frame ordering while adding the stage.** Carry/delay end/publication until every pending comparison has committed. On frame restart or overflow, invalidate old pending work; keep publication-before-clear behavior where intended. The current adapter comment assumes two idle clocks for markers, so audit that contract and result capture after latency changes. Register the adapter-to-detector event tuple (`start`, `end`, `valid`, pixel) together to cut the observed push/overflow/core_start paths if the arithmetic stage leaves these failures. Registering start alone would misalign pixels. Preserve immediate overflow suppression and queued-event flush semantics.
3. **Treat recovery independently.** Replace status/overflow-driven combinational asynchronous release with local AXI-domain reset/clear handling. A small local asynchronous-assert, synchronous-release reset register can cut the status→detector path, but the downstream reset tree must still meet recovery; use local release replication/distribution as needed. For already synchronous link-status/overflow events, a synchronous detector clear/abort input is another small architectural option; retain required power/reset behavior and history-RAM inference. Do not false-path these timed same-domain releases.
4. **Recheck the five DDR diagnostic CE paths after placement.** If still failing, pipeline diagnostic trigger/snapshot capture with corresponding data alignment, or improve placement/fanout. They are not on the motion comparison path and should not be mistaken for sample-counter logic.

The router log has +0.757 ns worst slack after detailed placement (`routed/run.log`:615/645), then 143 detailed-route iterations and six router hold-fix iterations (1123–1139), followed by one additional hold-fix pass (1149–1151). Its post-hold timing summary is already negative. This supports routing/hold-repair pressure as a possible contributor, but **does not prove a hold-fix setting of 100 caused the setup loss**: no comparable routed pre-hold path measurements were preserved here, and placement uses estimated routing. The actual critical path contains functional RAM/compare logic and long high-fanout routes, not an explicitly identified hold-only delay chain. Parent should handle tool-option experiments separately and retain the actual final STA gate.

Validation for any implementation: run existing detector/adapter/overflow/restart/end-marker regressions with consecutive same-block samples, then require final multi-corner setup, hold, recovery and removal closure. This document recommends changes only; no fix has been implemented or claimed to close timing.
