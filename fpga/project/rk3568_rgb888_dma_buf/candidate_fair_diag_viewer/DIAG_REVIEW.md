# Optional camera diagnostic fallback

This candidate is copied from `candidate_fair_viewer`, excluding build products
and hash manifests. The parent can finish testing fair without diagnostics first.
No device calls, ARM builds, deployment, or commits were performed to prepare it.

`DETVIEW_CAMERA_DIAG=1` enables telemetry; unset or any other value leaves it off.
All six existing workers report every five seconds even while paused, disabled,
or repeatedly returning 0/2/negative. `result0`, `result2`, `result_negative`,
and `result1` are counts since the last report. Pause and disabled are current
state, not failure reasons; disabled includes mode/stereo/HDMI selection.
Reports are initially staggered by 200 ms per camera, with no catch-up bursts.

The default register target is **camera 2**, `0x20000200`, nine 16-byte reads
per five seconds (1.8 reads/second total). `DETVIEW_CAMERA_DIAG_CAM2_ONLY=0`
opts into cameras 1–4, using the verified base array at 0x200 stride.
Cameras 5/6 always emit worker counts with `regs=unsupported_sfp_map`:
the copied RTL does not route their pages through the DVP decoder.
Diagnostics can still read camera 2 while the application is paused/disabled.

Byte-level Python inspection of `hardware_baseline/integrated_six_batch/source`
verified the map and semantics (RTL comments contain GBK). No RTL was changed.

| Offset | Evidence | Interpretation |
| --- | --- | --- |
| 0x00 | ov5640_reg REG_ACK / ov5640_ddr fault snapshot | overflow bit31, short bit30, DMA abort bit29, !frame_active/tag phase bit28, accepted pixels bits27:0 |
| 0x20 | REG_DBG_VSYNCS / ov5640_top dbg_vs_ff rising edge | video-domain VSYNC/SOF count, modulo-32 delta |
| 0x30 | REG_DBG_CAM_WORDS / dbg_input_pixels | offered pixels in previous frame, gauge |
| 0xA0 | REG_DBG_BEAT_CNT / diag_overflows, diag_shorts | overflow high16, short low16; independent modulo-16 deltas |
| 0xF0 | REG_DBG_BEAT_LAST / w_ctrl last_cnt increments on publish | good publication count, modulo-32 delta |
| 0x190 | dbg_cdc_input | source pixels in previous frame, gauge |
| 0x1A0 | dbg_cdc_output | output pixels in previous frame, gauge |
| 0x1B0 | dbg_cdc_drop | dropped pixels in previous frame, gauge |
| 0x1C0 | dbg_cdc_seq | source frame sequence, modulo-32 delta |

`ovreg_axil_decode.v` special-cases 0x190/0x1A0/0x1B0/0x1C0, routing by
addr[11:9] for camera indexes <4. All read addresses are 16-byte aligned.
CDC pixel/drop registers reset per frame; treating them as cumulative counters
would create false wrap deltas. First samples have `delta_valid=0`.
Hardware reset cannot be distinguished from counter wrap by two samples alone.
These are separate read-only observations, not an atomic frame snapshot.

The owner `PangoDev` remains alive until every worker has stopped and joined.
`cameraDiagRead` uses only its existing `regRead`, existing scratch region,
and shared fair DMA transport. Each register takes its own lock. No new opens,
clear writes, frame DMA, or buffer copies are added. Failed/interrupt-uncertain
diagnostic DMA uses existing quarantine immediately and never publishes partial
register values or automatically reopens the device. With diagnostics off the
new loop and result hooks do not run and no additional DMA is submitted.

Host checks: `bash local_camera_diag_check.sh` and `bash local_fair_check.sh`.
The first tests zero-off-I/O, cadence/stagger, all-six worker coverage, early
continues, RTL map, field/log parsing, gauge semantics, wrap deltas, exact
addresses via the actual PangoDev helper, and partial EIO/alarm quarantine.
The second runs the copied fair mutex, extracted real acquisition/protocol,
verification fixtures, and classes-only Qt syntax check. These are host checks;
board behavior and performance remain for the parent session to assess.
