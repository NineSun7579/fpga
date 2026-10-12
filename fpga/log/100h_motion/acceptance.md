# 100H motion detection acceptance

Accepted on 2026-10-03: four local CAM1–4 detectors, six video channels,
simulation, full build/STA, verified SRAM programming, 120-second live audit
and directly inspected RK3568 screenshots. Candidate run212303 remains in
SRAM; original detview restored. Same-scene baseline comparison reproduces
dark CAM3. The implementation is isolated in `project/motion_100h`.
The milestones below retain build history; final evidence is indexed by
`deliverable_checklist.md`, `final_byte_hash_audit.json` and the final entries.

## Baseline

- FPGA capture baseline: `bitstream_six_recovery_20261002_192245/top.sbit`.
- SHA256: `c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a`.
- All 197 archived RTL files match the original production source.
- FPGA NPU is tied off in this six-camera baseline. Motion metadata is intended
  for host inference scheduling; this task does not restore an FPGA YOLO engine.
- RK3568 baseline capture: `baseline.png`. Six images are present.
- Valid 120-second runtime observation: `baseline_live_observation.json`.
  Mean swaps 38.760 fps, uploads 38.751 fps, paint 7.694 ms, upload 6.463 ms.
  No nonzero unstable capture count; Xorg flip-timeout count increased by one.
- Viewer launch configuration is saved in `viewer_launch_baseline.json`.
  Its actual stderr path differs from the older candidate log path.
- `baseline_observation.json` contains an empty stale log and is excluded from
  performance acceptance.

## Implementation contract

- Four independent local sideband detectors; CAM5/6 reserved motion slots zero.
  Camera image data, valid timing and DDR
  packing retain their existing paths. No detector backpressure.
- 640x480 RGB565; sample stride four; 160x120 8-bit previous-frame luminance.
- Luminance uses `(R + 2*G + B)/4`, RGB expanded to eight bits.
- 16x12 blocks; 100 samples per block; raw block size 40x40 pixels.
- Absolute luminance difference >=16 counts as changed; >=8 changed samples
  marks a block. The first complete frame seeds history.
- Partial frames invalidate the reference. Surplus tail pixels cannot update
  sampled history. Frame adaptation must retain pixel zero even when VSYNC and
  valid coincide.
- Published metadata contains source-frame sequence, comparison validity,
  frame error, changed samples/blocks, inclusive block bounding box and bitmap.
  It is labelled latest source metadata, not a DDR-tag-synchronized overlay.
- AXI page 0x20000800 contains selector/capture, frozen-word read, generation,
  ABI magic and geometry. Legacy pages and SFP candidate slots are retained.
- The viewer reads metadata using its existing DMA owner and mutex, with scratch
  storage separate from camera buffers. All host register accesses are aligned
  16-byte transactions containing one low 32-bit register value.

## Required completion evidence

1. Detector, frame adapter and register integration self-checking simulations.
2. Four inferred history arrays with read-before-write behavior; resource fit.
3. Full setup/hold/recovery/removal timing at slow and fast corners; original
   clock and pin assignments retained; bitgen from the exact audited route.
4. Verified target PG2L100H, programming receipt and candidate bit hash.
5. Live metadata sequences, coherent snapshots, valid sample/block ranges and
   six normal RGB images after programming.
6. Runtime observation and RK3568 screenshot after deployment, compared with
   this baseline. A static screenshot alone cannot prove motion correctness.
7. Rollback image and viewer configuration remain available. New production
    sources and startup defaults are changed only after candidate acceptance.

Verification limits: physical movement was observed on CAM1/2, while CAM3/4
published valid static comparisons; all four movement paths pass simulation.
Reserved CAM5/6 zeros are verified by simulation and mapping, not direct board
readback. Full-top simulation and full mapped arithmetic equivalence are not
claimed. Final byte audit rehashed 702 current inputs, 694 frozen source/IP
inputs, 493 protected IP files in both candidate/original trees, and five
regression logs. Original viewer restoration screenshot is
`detview_restored_motion.png` (six live capture HUDs, about 21fps display).

## Verified implementation milestones

- Detector regression includes the literal six-frame 640x480 sequence, exact
  luma thresholds 15/16/17, eight-hit block boundaries, final sample at
  (636,476), unsampled-only changes and malformed-history recovery. Evidence:
  `project/sim/motion/motion_results.log`.
- Frame adapter regression covers coincident VSYNC/pixel zero, continuous
  full-resolution frames, gaps, short frames, one dummy, extra tails, FIFO
  overflow and SFP link reset. Evidence: `adapter_results.log`.
- Motion register tests preserve legacy camera/CDC/SFP candidate slots and
  validate all six frozen records, strobes, invalid indices and backpressure.
  Evidence: `project/sim/motion/transcript` (rerun on October 3 at 18:38).
- Integrated AXI128 bridge test passed 83 writes, 128 reads and 640 stalled-read
  cycles while 1,374 live publications updated six snapshots. Deliberate read
  corruption returned a failing exit code. Evidence: `bridge_results.log` and
  `bridge_fault_check.log`.
- Final 192245 baseline resource attribution was corrected: archive
  `previous_place_route` is not the final route. Final diagnostic baseline logs
  independently show 38.5/155 DRM and 18,642/66,600 LUT. Resource predictions are
  estimates until motion synthesis mapping is inspected.
- PDS source registrations require their `_timespec` fields. Failed preparation
  attempts are preserved as `work_failed_pds_184411` and `work_failed_pds_185008`.
  These runs stopped at project parsing, before RTL synthesis or programming.
- Candidate viewer compiled on RK3568; its standalone ABI test then failed a
  transaction-count assertion. This is not accepted host validation yet.

## Integration failure and corrected host validation

- Run `run_20261003_185204` compiled, synthesized and mapped, but its six-history
  gate was not met. Actual mapping used 54.5/155 DRM and 21,499 LUT; only CAM5/6
  histories remained. No placement, bit generation or programming was performed.
- CAM1–4 dimensions were inherited as 11-bit parameters. Untyped multiplication
  truncated 640*480 to zero; histories and frame-completion logic were removed.
  The fix requires integer geometry parameters and regression with sized
  `11'd640`/`11'd480` caller values. The failed inputs remain in the run's inputs.
- Each surviving history maps to eight 36K DRM primitives in single-port
  READ_BEFORE_WRITE mode, rather than the earlier estimated five. Six histories
  therefore predict 48 DRM plus the baseline 38.5; this remains an estimate until
  the corrected full build is inspected.
- RK3568 viewer rebuild and standalone ABI regression passed in
  `/userdata/linaro/100h_motion/viewer_529113f9d9e5`. The optimized test retains
  assertions and verifies 23 register operations, failure paths, torn generation,
  bounds and 48-digit bitmap formatting. Receipt: `viewer_build.json`; binary
  SHA256 `f78cbf45b567b41d4c364346597006117d8bae69f95c2a078608a6b36861d88e`.
- Six concurrent default-size detector/adapter/bank instances passed ten phases
  in 3,378,505 cycles; injected corruption failed with exit 1. Logs:
  `project/sim/motion/six_motion_results.log` and `six_motion_fault.log`.
  This simulation used default integer dimensions and did not cover the original
  camera caller's packed parameter widths; the additional regression is required.
- Integer dimension and total declarations now pass both packed-width adapter
  and direct-core tests: 307,200 pixels, 19-bit counters, 19,200 samples and 192
  blocks. All prior core/adapter cases also pass. Evidence:
  `project/sim/motion/packed_dimension_fix_evidence.json` and updated PASS logs.
  Failed work is retained as `work_failed_geometry_185204`; corrected synthesis
  is a fresh run and requires new resource evidence.
- A new pre-programming screenshot `preprogram_live.png` shows all six complete
  images with the original FPGA/viewer still running. Its instantaneous HUD is
  approximately 28.3 swap/upload fps, below the earlier 38.76-fps bounded mean.
  This is an observed pre-candidate fluctuation, not a measured motion overhead.
  Runtime evidence is retained in `preprogram_live_runtime.txt`.
- The subsequent bounded 120-second pre-programming observation has mean
  swap/upload 31.402 fps, paint 10.034 ms and upload 8.545 ms. All six cameras
  have zero unstable reads; mean source sequence rates are approximately
  45.04/45.02/25.72/25.73/40.39/40.39 fps. Viewer PID remains 31185 and Xorg
  flip-timeout count remains 390 throughout. Evidence:
  `preprogram_live_observation.json` and `preprogram_live_summary.json`.
- Corrected run `run_20261003_192131` passes compile, synthesis and mapping.
  Attributed synthesis rows now contain all six histories. Mapping totals:
  86.5/155 DRM, 26,111/66,600 LUT, 29,663/133,200 FF and 0/240 APM.
  Individual mapped RAM/address/enable/mode review is still required before
  routing. The first CAM1 specialization explicitly elaborates WIDTH/HEIGHT as
  32-bit 640/480; PDS reuses that specialization for identical module parameters.
- Corrected mapped ADIF review passes every RAM/control/geometry check for all
  six paths, including 15 common address bits, ordered data, shared axi_clk,
  disabled extra output registers, READ_BEFORE_WRITE, decoded enable/reset LUTs
  and next-cycle comparison alignment. Export log names the exact hashed ADF.
  Parent inspected the six check summaries and saved `mapping_audit.json` and
  `resource_review.json` in run192131, with 858 source/netlist evidence quotes.
  Serial build resumed toward strong PnR and complete final timing.
- Programmer review found that an initial DONE=1 scan could satisfy the flash
  parser before the final scan. The tool now requires a completed scan after the
  program/verify operation, confirms one PG2L100H and asserted DONE, and rechecks
  flushed logs after normal client shutdown. Unresolved flash work retains its
  owned client/server instead of terminating an active operation. Parser checks
  reject missing final scans, wrong targets, DONE=0 and vendor errors. Actual
  vendor execution remains to be validated after final bit acceptance.
- Read-only board inspection found an external viewer change after the baseline
  observation: camview PID31185 is no longer running; detview PID33846 owns DMA,
  launched October 3 at 11:28:02 UTC with wb_v4_combo, fullscreen, no tracking and
  stereo_pairs.example.json. Exact executable/cwd/log/argv are retained in
  `changed_dma_owner.txt`. No current viewer was stopped. Future quiesce must
  account for this live owner rather than assuming baseline camview still runs.
  Endpoint identity is recorded in `board_identity.json` (0755:0755, pango driver).
- Strong placement/routing completed successfully for run192131. PHY audit
  initially failed while reading the baseline: its parser expected PAD_* ports,
  but actual reference pads use PAD and lane pads use P_RX/ TX_SDP/SDN; PCIe
  vectors also use ARRAY nets with per-bit CONNECT blocks. Parser now follows
  the actual top-port CONNECT blocks. Baseline and candidate compare identical
  for all 14 dedicated connections and all five HSST lane/PLL placements.
  The resume path verifies the live route hash against the archived route and
  reuses the completed exports, then continues full STA and bit generation.
- Current detview read-only preflight passed with sole DMA owner PID33846 and
  WM_DELETE_WINDOW support on window 0x2e00006. Executable hash is
  dbbe29cf09c2954df421f9d826f61040e8efaa22d35b2845b7a134038719eada;
  stereo config hashes and private launch environment were captured for restore.
  Receipt: current_viewer_preflight_d7d89f9b31ef41339b6edce966d5d44e.json.
  Initial preflight exposed sudo credential caching leaving the password line
  in Python stdin; requests now use a shell-quoted argv value, with stdin used
  only for sudo. No viewer was stopped by either preflight.
- Saved `detview_before_motion.png` immediately before candidate switch work.
  All six images are present and complete; current detview HUD shows new-frame
  19 fps and per-camera display rates 19–21 fps. This is a different running
  viewer from the earlier camview baseline and must not be used to attribute
  motion overhead without accounting for the application change.
- Final STA for run192131 is a genuine failure: slow DDR setup -0.398ns,
  309 endpoints, TNS -52.576ns; slow DDR recovery -0.221ns, 8 endpoints.
  Of the setup failures, 304 are detector paths and five are existing DDR
  diagnostic snapshot enables; all recovery failures are CAM6 reset paths.
  Detailed path evidence: `timing_violations_192131.md`; independent coverage
  audit: `final_timing_review.md`. Both corner pulse checks pass for this route,
  but that does not override setup/recovery failures. No bitgen/programming ran.
  The full work directory is retained as `work_failed_timing_192131`.
  Comparison/counter, event tuple, and local reset-release repairs are underway.
  STA gates now explicitly retain pulse rows at both corners and scan large
  reports in bounded chunks instead of decoding the entire 2GB file at once.
- User clarified the implementation scope: local cameras CAM1–4 only.
  Candidate top removes both SFP detectors/reset chains and ties their reserved
  320-bit slots to zero; all six video paths remain. New scope gates require
  exactly the four local history hierarchies. Runtime audit requires CAM1–4
  motion plus all six capture logs, and rejects SFP motion records.
  Updated core and event adapter regressions pass; the preceding six-instance
  pipeline regression also passed but is historical support, not acceptance of
  the new four-camera integration. Dedicated four-camera regression is underway.
  New immutable work/project.pds was prepared after retaining failed work.
- Four-camera combination regression now passes all ten phases, 3,378,505
  cycles; injected snapshot corruption exits 1. `four_motion_integration.log`
  confirms actual top retains four local taps, reserves zero CAM5/6 motion
  records and preserves video/DDR/DMA wiring. Fresh FPGA build started from
  these inputs. Four-camera viewer ABI passes locally; revised RK3568 viewer
  compilation is running in isolated viewer_eaf579139acf. A --help invocation
  unexpectedly launched compilation because the old script lacked argument
  parsing; that script now handles --help without connecting or building.
- Revised four-camera RK3568 viewer build completed with target ABI PASS.
  Binary: `/userdata/linaro/100h_motion/viewer_eaf579139acf/camview_motion_private`,
  SHA256 dc9ca56440e3b10e2241ef52ad99e1e8fd8e692d0bebda27b9e20fcf88d2e5e9.
  Receipt `viewer_build.json` binds all five inputs and successful target output.
  It has not been launched; current detview remains the DMA owner.
  Runtime audit selfcheck passes four motion/six video fixtures and rejects
  seven corruption/missing/stopped-camera cases, recorded separately from live
  evidence in `runtime_audit_four_selfcheck.json`.
- Independent final source/test review `four_pipeline_boundary_review.md`
  found no protocol defect in compare/update alignment, earliest legal next
  start, delayed publication/clear, local counters, restart or overflow paths.
  It verifies literal oracle coverage and names the exact reviewed hashes.
  This source review is not mapped or routed timing/hardware acceptance.
- Actual four-camera map: four 19200x8 histories, eight DRM36K each, 32 total;
  global map uses 25,861 LUT, 27,201 FF and 70.5/155 DRM. Parent verified 1,950
  RAM/connection quotes, 25 control quotes, 4,875 pipeline quotes and nine
  register-scope quotes against current-run file hashes. Control reset N1615
  and RAM enable N63 resolve stale helper node assumptions. Registered decision,
  metadata and local counter functions support the sample+2 update schedule.
  CAM5/6 reserved captured records map to zero; active four-camera selector,
  frozen packet and magic/geometry/config map correctly.
- Current run resource_review.json now passes build.resources for the exact
  frozen synthesis/map. Layout/routing resumed with --run --resume. The RAM
  resource verdict does not claim complete mapped arithmetic equivalence:
  four bitmap arithmetic cones, luma/difference and some adapter predicates
  cross undocumented gopA/gopAL6Q MODE bindings. Those limits are preserved in
  pipeline_arithmetic_review.json, with 409 additional current-dump quotes.
  Functional RTL regressions remain the behavioral evidence for those cones;
  final timing, bit/programming receipts and live board results remain pending.
- Initial run212303 PnR invocation failed before layout because the pnr wrapper
  rejects -clustering (and its help does not list -gplace_timing, -optimize or
  -slack_router). Retained failed script/log with .unsupported_options suffix.
  Direct installed-version `help pnr` output is in pnr_help.log. Build now uses
  documented -slack_prior_in_global_router TRUE and -logic_optimize_enable TRUE,
  preserving multi-corner and strong hold repair options. Same mapped input
  resumed; no new synthesis or input changes were needed.
- Run212303 completed layout/routing, pin/PHY comparison, full final STA and
  same-route bit generation. All ten corner/check groups have positive slack:
  slow setup 0.022ns, hold 0.158ns, recovery 1.040ns, removal 0.308ns,
  pulse width 0.011ns; fast setup 2.183ns, hold 0.118ns, recovery 2.167ns,
  removal 0.248ns, pulse width 0.011ns. The 193ps router hold-margin warning
  is below a requested 200ps optimization target, not a negative final slack.
  All 112 pins and dedicated PHY/HSST placement match baseline. Candidate bit
  SHA256 e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7.
  Candidate programming precheck and independent baseline rollback --check
  passed. Current detview preflight still identifies PID33846 as sole DMA owner;
  graceful stop was launched. Actual programming and candidate runtime pending.
- Current detview graceful stop succeeded, receipt
  current_viewer_stop_294f0ab9e4fb420ab83c32a5552cdd05.json. First quiesce attempt
  exposed Linux pgrep's >15-character pattern diagnostic for alternation even
  though each name is short. Board helper now queries camview and camview_motion_
  separately; observer and screenshot query text also corrected. Second quiesce
  succeeded, receipt board_session_cad9fb99bddd42cabaae46630684fe22.json:
  no viewer/DMA owner, module unloaded and PCIe endpoint removed. Candidate
  SRAM programming launched using absolute bit/status paths.
- Candidate SRAM programming succeeded, retained directory
  project/motion_100h/program/run_20261003_232438_0d8973c0: all six stage gates
  true, no stage errors, exact candidate hash and post-operation single PG2L100H
  DONE=1. PCIe reconnect succeeded against baseline identity, receipt
  board_session_e0faa80171c046df822782edf22efba3.json. Candidate viewer start
  launched; live metadata, screenshot and bounded observation remain pending.
- Live acceptance completed: motion_four_live_observation.json covers 120s;
  motion_four_live_audit.json accepted=true, errors empty. Each of four local
  cameras has 123 valid advancing snapshots; CAM1/2 maximum changed blocks 5/9,
  CAM3/4 static. All bitmaps, counts and bounding boxes consistent, no frame
  errors or unstable reads. Six average capture rates: 44.40, 44.32, 25.73,
  25.73, 40.13, 40.13fps. Display average swap/upload 35.86/35.82fps.
- Direct screenshot review found very dark scene/CAM3 nearly black, prompting
  actual baseline SRAM A/B. Baseline rollback succeeded with exact hash and
  post-operation DONE=1, directory rollback/run_20261003_233409_480f6211550546cf81ce867e8dc0062e.
  motion_same_scene_baseline.png reproduces darkness and same visible content;
  no candidate-specific display corruption observed. See motion_four_visual_review.md.
  Rollback ownership guard now requires absent driver/endpoint and allows the
  DMA node to disappear during normal quiescence. Eight rollback tests pass.
- Candidate reprogramming succeeded again, exact e3da6e1f… bit, retained
  project/motion_100h/program/run_20261003_233610_c8c9d9dd; PCIe reconnect receipt
  board_session_f977cfff0e35460899900bbe1f2ca7e4.json. Original detview restored
  successfully as PID42262 with original executable/config/environment and
  visible window, receipt current_viewer_restore_e023736cc5604fa09c1a447335b9311e.json.
  Board now runs candidate SRAM bit and original detview; flash unchanged.
