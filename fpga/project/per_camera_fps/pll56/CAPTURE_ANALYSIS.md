# PLL56 capture-enable diagnosis and isolated candidate

The latest completed placement run is seed 2, `build_mfwcoqj3`, which failed
at 18:36:13 on 2026-10-04. Seed 1 is not the latest result. No run generated
a bitstream; board acceptance remains pending with the parent session.

| Run | Failing summary rows / 126 | Slow setup failures | WNS ns | TNS ns |
| --- | --- | --- | --- | --- |
| Seed 0 `build_po3co5wg` | 2 | CAM1 PCLK: 3; CAM3 detector: 4 | -0.385 / -0.034 | -0.744 / -0.136 |
| Seed 1 `build_aai6kbmf` | 1 | CAM4 motion record: 5 | -0.086 | -0.378 |
| Seed 2 `build_mfwcoqj3` | 1 | CAM2 motion record: 4; CAM5 debug snapshot: 3 | -0.195 | -0.855 |

All three runs pass every hold, recovery, removal and pulse-width summary row.
The seed1 pin audit passes exact equality for 112 ports; the dedicated PHY audit
passes exact site/pad equality; fresh synthesis and route identify all 32 motion
history banks (eight per local camera, read-before-write). This evidence is
high confidence for those specific gates; it does not establish timing closure
or physical sensor performance. Seed2 has the same passing non-timing gates.

Seed1 CAM1/2/3/4 slow setup slacks are +1.461/+0.843/+2.010/+2.600 ns.
Seed0 CAM1 paths are falling-edge frame-valid to rising-edge source-drop counter
CE, with cascaded counter enable routing. They remain real half-cycle paths;
no false-path or clock relaxation is justified. Registering a new VSYNC flag
on a different phase could change counts and is outside this experiment.
Seed0 CAM3 changed_q reaches blocks_work through a 400-fanout enable; its
pipeline and threshold semantics remain untouched here. Same-edge register
duplication is a separate option requiring actual synthesis proof that PDS
retains each duplicate and a cycle-exact detector regression.

The seed1 failing path is CAM4 vs_q -> rise -> push -> overflow -> N77 -> N368
-> motion_record CE. Four endpoints [136,165,166,202] fail at -0.086 ns; endpoint
[171] fails at -0.034 ns. The path has five logic levels, 0.766 ns logic and
6.372 ns routing (89.269%). Overflow route is 1.972 ns; N368 route is 2.354 ns
at fanout 262. Seed2 exposes the same capture-control family on CAM2, plus a
separate CAM5 diagnostic path. Placement alone has moved the failing endpoints.

`capture_candidate/motion_stream_adapter.v` extracts only motion_record's
existing reset/capture assignment into an independent always block. Its enable
expands the exact original predicate:

    strobe && !overflow_reset && !overflow
    = strobe && !overflow_reset &&
      ((queued != 16) || pop || (!rise && (!acquired || !pixel_valid)))

All 128 Boolean combinations are checked, including unreachable states. No
registered flag, clock phase, publication edge, counter, detector, memory or
FIFO policy changes. The separate process makes the capture predicate directly
visible to synthesis, allowing a flattened LUT mapping instead of inheritance
through the event-control priority branch. This is a mapping hypothesis;
source algebra alone does not prove that PDS reduces delay or closes timing.

`simulate_capture_candidate.py` runs the existing adapter policy testbench with
original and candidate instances side by side, comparing all 320 record bits
on every clock and control/diagnostic counters. It includes full 640x480 black
and white frames (192 blocks / 19200 samples), consecutive and gapped pixels,
coincident VSYNC/pixel0, final sample, short/restarted frames, tolerated dummy,
excess tails, overflow abort/recovery, link-reset and five-clock blanking.
The private simulation receipt binds candidate, original, detector and log hashes.

ModelSim passed in `sim_capture_tav0mfuo`: 614427 compared clock edges across
small, default full-frame and fault-policy instances, with exact records and
control/diagnostic counts throughout. Candidate adapter SHA256 is
`102b5da4a09318ca806ae851b30550a9ecef63f852d3fc43d089fb6fd77cf12d`.
The build started at 19:15:54 as `build_capture_538dxoxa`, using placement seed1.
Its 694-file private input inventory matches seed1 except the adapter file;
`capture_candidate/input_diff_proof.json` records that exact comparison.
The supervisor is `run_capture_candidate.py`; its flushed launch log and receipt
live under `capture_candidate/`, while every vendor stage logs in the build.
This start records an experiment, not a timing result or completion claim.

## Completed capture experiment: rejected

`build_capture_538dxoxa` failed at 19:51:20 on 2026-10-04, after 35m26s.
All 126 timing summary rows are present. Two slow setup rows fail:

| Clock | Failing endpoints | WNS ns | TNS ns |
| --- | ---: | ---: | ---: |
| cmos3_pclk | 6 | -0.785 | -2.484 |
| ddrphy_sysclk | 36 | -0.642 | -11.280 |

The actual violations comprise six CAM3 source-drop counter CEs, 22 CAM2
detector work-state CEs, and 14 CAM4 DDR diagnostic/pixel-control endpoints.
No motion_record endpoint is violated in this report. That is a local result
for this route, not proof of repeatable improvement: the source change also
perturbed mapping and placement of unrelated logic, and overall closure worsened.
This candidate is rejected for deployment. No additional seed rerun is scheduled.

The worst CAM3 path launches at falling-edge `cmos_frame_vsync_r` and ends at
`src_drop[31]/CE`, with clock skew -1.828 ns. It is the same structural half-cycle
counter family previously observed on CAM1. Source lines 226--234 in the private
`ov5640_cdc.v` show a frame-edge priority load of 0/1 competing with a held
32-bit increment (`s_valid && full`). Registering VSYNC on a new phase is not
equivalent. A focused alternative is to separate this counter into its own
process and expose the same-edge frame load/reset and increment control directly
to synthesis, avoiding the cascaded CE mapping. This requires original/candidate
comparison of src_drop and the complete bundled snapshot on every edge, including
first-pixel coincidence, FIFO-full transitions, reset and 32-bit wrap. It must
not alter source counts, notification phase or snapshot contents.

Worst DDR path is CAM2 detector `update_pending` to `max_x_work[0]/CE`, six
logic levels. Its shared N78 enable has fanout 398 and 2.730 ns route delay,
then mark_block[182] and the mark_any reduction reach bbox/statistics enables.
Same-edge bank-local registered acceptance/decision copies are a possible
focused remedy, retaining the original sample+2 update and end+2 publication.
PDS preservation attributes must first be confirmed from vendor documentation;
post-synthesis distinct register count and actual fanout must be measured.
An attribute or RTL duplicate alone is not evidence that duplication survived.
The CAM4 DDR failures also include ddr_init_done (fanout2736), axi_rst and
capture_overflow into diagnostic controls. A detector-only fix would not prove
these independent paths clean; all original strict gates remain required.

Slow/fast hold rows pass with worst slacks +0.108/+0.163 ns. Exact 112-pin and
dedicated PHY equivalence and all 32 attributable read-before-write banks pass.
The gate blocked bitgen; no candidate bit exists and no hardware access occurred.
The preserved `receipt.json` and `final_sta_analysis.json` provide exact paths,
timestamps, input/report hashes and failures for parent review.

All 126 rows for each completed placement run are exported separately as
`capture_candidate/build_*_126rows.csv`; report-bound check totals and audits
are in `capture_candidate/sta_comparison.json`. Seed1 slow/fast worst hold slacks
are +0.247/+0.171 ns; seed2 has +0.242/+0.171 ns. Both have zero hold failures.

A candidate build may start only after that receipt passes. It must use private
input copies, unchanged PLL56 clocks/exceptions and all original strict gates,
with the shared exclusive PDS lock and process-idle guard. Source inventory
must differ from seed1 only at this one adapter file. Exact 112-pin/PHY equality,
32 attributed history banks and zero failures in all 126 final STA rows remain
mandatory. A failure prevents bitgen. No board/SSH/Flash action belongs here.
