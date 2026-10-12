# Video and inference throughput / DDR optimization

Objective: implement improvements to video frame rate and actual inference
frame rate while reducing DDR pressure. Retain six-camera display, correct
raw-image inference inputs, bounded detection refresh and rollback capability.

| Requirement | Evidence required | Status |
|---|---|---|
| Video frame rate improves | Same viewer/model/config baseline vs candidate: delivered new frames and display rates, capture stability and screenshots | Baseline inspection started |
| Inference frame rate improves | Completed model executions per second and latency, camera coverage and accuracy sanity checks; skipped work reported separately | Processing architecture under review |
| DDR pressure decreases | Measured FPGA DDR transferred bytes/transactions or validated transfer counters; RK3568 memory traffic considered separately | DDR path under review |
| Motion information reduces unnecessary work | Explicit freshness, fallback and periodic full-frame policy; active/static observations | Not implemented |
| Build and deploy evidence | Relevant simulations/tests, target builds, isolated artifacts, verified board receipt | Pending |
| Recoverable deployment | Retained run212303 SRAM bit and original detview source/binary/settings | Known-good sources downloaded read-only |

Baseline reproduction completed on RK3568: isolated build
build_2d29b9cebff2244a generates dbbe29cf09c2954df421f9d826f61040e8efaa22d35b2845b7a134038719eada,
exactly matching the running original. Fresh 320.902s observation establishes
22.730 fresh composite paints/s over 313.896s complete windows; 80.302 MB/s
camera GPU upload plus 8.170 MB/s HUD payload. See baseline/metrics_review.md.
Candidate worker preprocessing/history changes have passed byte parity tests;
capture pacing behavior passed on RK3568. Candidate target build is running.

Build053c691e05d07408 passed target compile and follow-up vision/camera-DMA/
frame-metric selftests. Ring1 unrestricted measured23.531 fresh paints/s and
14.105 successful worker executions/s. Ring3 unrestricted measured23.127 and
14.374 respectively. Both keep six streams live; neither establishes improved
inference throughput versus baseline checkpoint bounds14.522–14.846/s.
Acceptance remains pending. Ring1/30fps capture-admission experiment is running.
Ring1/30fps complete observation verifies26.209 fresh paints/s and14.236
successful inference/s; sixcamera overlap passes. Capture DMA payload measured
101.514 MB/s vs baseline estimated134.755 MB/s. Inference improvement remains
unverified. Direct-completion build689a1ad36932d0f5 passes target selftests and
is deployed with receipt candidate_start_6036539dc8b44f439ad3e063c11b4731.json.
Its acceptance observation waits for compiler/RKNN test interference to end.
Output-cache source is prepared in output_cache/src; no build or runtime
claim is made for it. Observation interference checks have eight passing tests.

Remaining acceptance requirements are explicit:

| Criterion | Remaining direct evidence |
|---|---|
| Video throughput higher with six streams | Stable final candidate vs matched original complete windows and screenshot |
| Actual completed inference throughput higher | Instrumented-original successful completion totals vs final candidate, same model/source/settings; no inference skipping counted as gain |
| DDR read pressure reduced | Matched original/candidate completed DMA payload counters, no read errors; document camera writes and physical-bandwidth limits |
| Correct detections | Pinned original/final candidate RKNN shared-image output tuple checks, nonempty results, repeated frames |
| Reliable deployment | Target build/selftests, pinned identity/config/assets, observation without compiler/extra RKNN interference, verified graceful stop/rollback |

Output-cache isolated build started. Separate cache parity and metrics-only
original snapshots are being prepared locally. No final acceptance claim yet.

Pre-cache real RKNN parity audited PASS in parity/final_review.md:
bright scene has two exact class/score/box matches on each of three repetitions,
dark scene empty on both sides, all four processes exit0 (12 completions,
zero errors). Model/binary/image/source/log pins agree. This establishes
original-versus-pre-cache pixel/decode equivalence on retained scenes only;
output-cache parity and final runtime performance remain required.

Instrumented original build5ad75c7b2e51e76a succeeded, binary
58b42ab575118b195934b6f1d0b09a4f3e09a8cc34d658c1cdc2d5b9a368071c.
Target vision/camera-DMA/frame-metrics selftests passed. Cache parity runner
has launched after quiescent-host verification, reusing hash-pinned original
harness619b6eb48a32ca26. Actual cache output comparisons remain pending.

Exact-baseline comparison parser now accepts instrumented-original observation
receipts and requires matching configuration/assets/settings, verified120s
receipts, zero inference failures, sixcamera overlapping delivery and all
three metric improvements. Eighteen regression tests pass, including stale
generation/configuration rejection. Historical estimated DMA cannot establish
performance acceptance. Direct request ingress is being implemented in a
separate snapshot; it remains unbuilt/unmeasured.

Cache parity independently audited PASS in cache_parity/final_review.md:
six scene/reload comparisons, 36 completed inferences, zero errors, exact
two-target bright-scene class/score/box equality across three loads and three
frames each. Actual current model exposes four outputs. Dark-scene empty
agreement remains inconclusive for positive correctness; other model formats
and lane are not covered by this real-image audit.

User selected "保留标定，继续本地工作" after reviewing the proposed board switch.
Preserve the calibration viewer; do not replace it for performance acceptance
or add remote work during this local phase. Exact-baseline and cache builds
remain ready, but final matched throughput/DMA observations await board access.
Direct-ingress source is prepared (mainfb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04);
local threaded validation is underway. No final performance acceptance yet.

Direct-ingress local gate validation completed PASS with Qt6.11.1/GCC13.1:
100 submit/close races, 200 concurrent configuration commits, 200 wait/stop
joins, blocked-GUI submission, pending clearing and stale request/rate checks.
Twenty retained artifact hashes freshly match local_validation/receipt.json;
production main remainsfb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04.
This compiles/exercises extracted production gate/mailbox code, not the full
Qt5 controller, actual VisionPipeline replies, device shutdown or RKNN SDK.
ready_for_validation.json pins three current source snapshots and lists
remaining target-build/controller/metric/screenshot/deployment requirements.
Calibration is preserved per explicit user selection. Goal stays incomplete.

Current local-input preflight verifies all three source inventories and
snapshot digests,20 gate-test artifact hashes, successful step exits and the
exact production-source digest bound by the extraction manifest. It reports
local_inputs_verified and explicitly goal_complete=false. VALIDATE.md gives
the remaining pinned target-build, actual-controller transition, matched
original/candidate metrics, screenshot and restoration procedure. Final
direct-ingress image parity preparation is in progress locally; no board
work is performed during the calibration-preservation phase.

Final ingress parity preparation completed and freshly rechecked locally:
manifest/source/scene/tool digests match; candidate snapshot
786b876843460deeab1b56d53abed1caaa3f3428069977af62a946824056300f.
It remains unbuilt/unexecuted. Controller acceptance instructions retain
actual generation, pause, pending, mode transition and shutdown requirements.

The remaining completion gate requires target work: user explicitly selected
preserving the calibration viewer and local work only. No further local audit
can establish the requested actual inference throughput improvement or final
six-camera deployment behavior. Resume target validation when board resources
and authorization become available; do not close the goal as complete based
on prepared manifests, local tests or earlier video-only gains.

Current FPGA baseline: project/motion_100h/run_20261003_212303/top.sbit,
SHA256 e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7.
Current viewer: original detview restored PID42262; actual current state must
be checked before any switch. Earlier lightweight camview FPS is not a
detview baseline. Reducing inference frequency is not proof of improved
actual inference throughput. A frame repeated on screen is not a newly
delivered video frame. FPGA DDR traffic and host DDR traffic are distinct.
