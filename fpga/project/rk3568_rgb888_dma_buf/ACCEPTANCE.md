# Live RGB888 DMA-BUF acceptance

All new work and evidence are under this directory. Prior FPGA artifacts were
copied read-only into hardware_baseline; their original files were not modified.

| Gate | Evidence | Status |
|---|---|---|
| Current viewer/source-bundle identity | baseline_1791563289001003700/runtime.txt and manifest.json; viewer_build_1791563568743401100/manifest.json | PASS: isolated ARM64 rebuild SHA25673613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100 exactly matches running viewer and bundle binary |
| Snapshot isolation | baseline_1791563289001003700 | Viewer, host protocol and driver copied from board; runtime retained |
| Dedicated inference input layout | candidate_driver/README.md | 8MiB allocation cap, RX input at4MiB; original six slots and scratch below4MiB retained |
| Driver boundary contract | candidate_driver/test_bounds_contract.py | Seven local checks pass; not hardware validation |
| ARM64 kernel module build | driver_build_1791563854046563100/build.log and manifest.json | PASS; AArch64, vermagic6.1.99, SHA2562631405b7bb1f8f0cabb5e219fbbef85ca72def7b4077f2dce16a53c6161462c; not loaded |
| Same-frame RAW/RGB acquisition | candidate_viewer | Review fixes implemented: deferred F2H/BEGIN until consumption, exact model/revision matching, atomic rotation retirement, independent tensor queries and safe unpublished timeout release. Independent re-review approved bounded hardware parity testing of main.cpp a90464e7…; live receipts still pending |
| Initial candidate ARM64 build | viewer_build_1791564838582770900/manifest.json | PASS build rc0, SHA256b7262be290f26567fecef3d0b1ef3c88f35ec9a2274295f4e4b7b3d69c900527. All six target selftests PASS: camera-DMA/frame metrics/HDMI/MVP-round1/MVP/vision. Last three required TMPDIR under /userdata because root /tmp was full. Candidate not deployed; newer parity-enabled source rebuild underway |
| Per-model rectangular/square DMA-BUF binding | candidate_viewer | Pending target validation |
| Actual MVP input metadata | Board query_model tool, /root/npu/mvp/MVP_accuracy_round1_rk3568_int8.rknn | INT8, NHWC 1x480x640x3; size and size_with_stride921600, width stride640. UINT8 user-memory conversion must be tested explicitly before enabling this signed-model contract |
| MVP UINT8 user-memory conversion probe | candidate_viewer/model_contract_probe.cpp; mvp_user_input_parity.log | PASS after management recovery: ALL_3_PAIRS_PASS. Three deterministic921600-byte UINT8 inputs; all six native outputs match exactly (434700 bytes per pair). Native INT8 NHWC, user UINT8 pass_through0, default flags, ordinary RKNN allocated memory; no PCIe access. Actual coherent DMA-BUF parity remains pending |
| Exact live input and native-output parity | deploy_1791567760719372300/candidate_runtime.log and parity_markers.log | BLOCKED: candidate SRAM81eb… programmed, 8MiB driver inserted and viewer PID20108 launched; first DMA ioctl failed and viewer entered SIGSTOP quarantine before parity. No successful pixel/native-output pair. Preserve mappings until DMA quiescence established |
| Parity-capable ARM64 build | viewer_build_1791565869783293600/manifest.json | PASS build rc0, SHA256689016ba67ac0cb4d2417fa6200a88b59d080054de150cca2779d85b0232699c; six device-free target selftests started. This snapshot precedes lifecycle review fixes and is not approved for deployment |
| Lifecycle-fixed ARM64 build | viewer_build_1791566612476544200/manifest.json | PASS build rc0, executable SHA2569b70d27a5d78735aab02f4c0ec501303e06c16be1c6770a4557216d7bf52a9e0; main.cpp897ae199… precedes INT8 user-input support, so this artifact cannot establish scheme2 MVP acceptance. Latest INT8-capable build and target probe receipts still pending |
| INT8-capable reviewed ARM64 build | viewer_build_1791567000564714800/manifest.json | PASS build rc0, executable SHA256e1b0d850ed0f806898ee627bf065a6aada57b90ef802f1c8fc930fd56aade6af; main.cppa90464e7288663ddfdf31978b3702c0aceed0a948e02fc3fe0729386c6d593ba matches independent lifecycle review. Six target selftests started; exact deployment local plan passed with baseline PID18980 |
| Live before/after CPU/capture/display/RKNN | Target receipts | Pending |
| Post-trial original runtime restoration | Target receipts | Pending |
| Reviewed deployment and rollback orchestration | deploy_candidate.py, deploy_remote_helper.py, DEPLOY_CANDIDATE.md | Local plan validates candidate/rollback image, module and copied build identities. Eleven mocked lifecycle tests pass; target deployment waits for viewer review fixes and parity build |

Kernel module builds using Debian GCC12.2 whereas the kernel was built with
GCC10.3; Kbuild reports a compiler-version warning. Compilation and matching
vermagic do not establish runtime behavior. Candidate driver excludes all PCI
DMA during an active NPU lease, so live display/capture contention must be
measured rather than inferred from the standalone benchmark.

## Management recovery

User authorized reboot and explicitly required FPGA reprogramming. Reboot
verified new boot ID17711f18-c916-445c-b63d-c40002553b1a. Original SRAM
image fcb2… successfully programmed with done bit1; original module4506c0f7…
restored. Viewer launch initially failed because LightDM repeatedly restarted
while root filesystem was100% full. syslog476MiB and kern.log276MiB are being
preserved to userdata before verified truncation. First backup verification
failed because syslog.socket reactivated rsyslog; no unverified source truncation
was performed. Revised recovery stops both socket/service before copying.
Display/capture/RKNN recovery acceptance remains pending.

Recovery completed: log backup verified at
/userdata/linaro/ov56401-recovery-logs-1791576402528345876, root527MiB free.
Original viewer PID4968 owns DMA; reboot_original_recovery/health.log confirms
Mali-G52 renderer, all six camera panes, zero camera errors, continuing MVP
decode_ok1 and RKNN completed4/s. Latest pane fresh-tag rates approximately
46/45/26/26/41/41 FPS (startup recovery samples, not scheme2 performance).
Original FPGA SRAM, original module and original viewer are active again.

## Continued failure investigation

Board allocation_evidence.log reports CMA total16384KiB. Candidate startup
requests8MiB TX plus8MiB RX, exhausting that entire pool before Mali/other users.
Original4MiB+4MiB layout leaves headroom. Stopped candidate had no exported fd,
consistent with allocation-stage failure, but original errno was not logged so
ENOMEM remains a hypothesis pending instrumented reproduction. Viewer fix will
retain4MiB TX and8MiB RX, record all failed ioctl details and avoid quarantining
proven pre-DMA allocation errors. Original production files remain unchanged.

Memory fix now implemented: feature-on TX allocation/mapping is4KiB with
dedicated TX scratch offset0; RX remains8MiB with original camera/scratch and
independent inference slot. Legacy feature-off buffers remain4MiB each.
Failed MAP allocations record errno/selector/offset/thread and perform verified
idle cleanup instead of permanent quarantine; uncertain DMA remains protected.
ARM64 single-process build started; updated hardware reproduction pending.
Board-only optional process cleanup retired Thunar, light-locker, two Blueman
processes and tracker-miner-fs with SIGTERM; measured available memory1287→1348MiB.
No files removed or services disabled for that cleanup.

Optimized build viewer_build_1791595611134983200 succeeded, executable
SHA2560135f65beaff3c93bf62bb0a00133810e80a6dc40a47d3be16129a0b127c6545.
All six device-free target selftests pass. Before redeployment, inspection found
no live viewer but a retained module reference and10MiB CMA allocation.
idle_driver_health.log confirms earlier614416-byte camera F2H returned-512
and driver emitted uncertain lifetime/reboot required. Authorized reboot recovery
started to clear that state; original SRAM reprogramming is underway. This is
separate from the optimized build, which has not yet run live.

Optimized live deployment deploy_1791596415577888000 succeeded after verified
clean retirement of original PID2141. Candidate PID2976: at least25 exact
same-frame Cam1 MVP pairs passed. Each input921600 bytes and all6 native
outputs434700 bytes matched; required12-pair marker reached. Six-camera error
counters zero. Evidence candidate_runtime.log and parity_markers.log. Verification
repeats inference and suppresses performance timing; observed reduced FPS in
that mode is not a performance comparison. Graceful switch to verification-off
scheme2 performance mode started; live gains remain unmeasured.

Performance-mode owner3188 verified after launch encountered stale prior identity
receipt (new process was healthy; adopted only after executable/fd/environment
checks).30.008s processCPU sample181.38% (54.43 CPU seconds). Last12 capture
samples mean35.45/27.79/24.12/24.11/34.61/34.75FPS; completion stats mean3.45/s,
paint37.13FPS. Metrics use different log window lengths and are exploratory,
not formal paired acceptance. Last100 consumer leases mean42.04ms, during which
globalDMA exclusion blocks camera acquisition. Sourcefix in separate concurrent
candidates underway; restoring original pair before matched baseline measurement.

Restore completed with receipt deploy_1791596752376736300/receipt.json:
original SRAM fcb2…, original module4506c0f7…, original viewer73613d52…
ownerPID3972. Thirty-second baseline CPU/runtime sample started. Current scheme2
passes correctness but fails capture non-regression; keep original active while
isolated concurrent-lease candidates are developed. SPI Flash unchanged.

Baseline sample completed: processCPU211.81% for30.017s vs scheme2 global-lease
181.38% for30.008s. CPU14.37% lower alongside reduced work; not an efficiency
claim. Original capture trailing means44.13/44.50/25.74/25.75/40.20/40.25FPS and
completions3.91/s. LIVE_RESULT.md records exploratory comparison and limits.
Concurrent candidates implemented with local actual-body range/lease tests;
driver allows only RX disjoint from reservedinput and separate TX during lease.
Viewer permits existing RAW/metadata paths but keeps single converter admission.
ARM64 concurrent driver build started; original runtime remains active.

Concurrent ARM64 driver build PASS:
driver_build_1791597505924607700/manifest.json, module
SHA2560d43b3bc424170da673ecc8bac86151c4814869159c98eb06211559be4342d2e,
source pango_zc.c bcc5f4e944497b80ed61fd96a6a53fa2fd4a997883130c7a544ccb00696fe97f.
Not loaded. Matching concurrent viewer single-process ARM64 build started.

Deployment race fixes implemented and22 local tests pass: stop waits through
same-starttime teardown/zombie transitions but rejects actual PID reuse; launch
uses unique identity/status paths. Explicit --module-build reviewed manifest
supports concurrent module selection with source/hash/vermagic validation.
Local plan for driver_build_1791597505924607700 passed with vermagic
6.1.99 SMP mod_unload aarch64 and module0d43b3bc…. No concurrent deployment yet.

Concurrent live deployment deploy_1791598646233805500 completed. Viewer build
1791597554057206600 f1368886… passed all six ARM64 device-free selftests.
Actual concurrent input/native parity reached required12 marker and at least16
exact Cam1 MVP pairs,921600 input bytes and434700 native output bytes per pair.
All six camera errors zero. Verification adds repeated inference; rates during
verification are not performance acceptance. Graceful verification-off restart
started; performance and capture non-regression remain pending.

Concurrent verification-off PID9011 sample30.009s CPU182.14%; trailing11
capture windows39.67/9.40/25.53/25.55/38.66/38.72FPS, completions3.18/s,
paint33.24FPS. Inputlease last100 mean41.75ms. Cameras3-6 recovered near
baseline, but Cam2 severe regression and inference throughput below baseline:
concurrent candidate fails acceptance. Original restore started. Separate
investigation of Cam2 scheduling/FPGA traffic underway. No performance gain claim.
Evidence concurrent_performance_cpu.json/runtime.log/summary.json.

Original restore deploy_1791598801130368200 completed; activePID9480.
restored_health.log confirms Cam2 recovered44.85FPS, six delivered rates
45.02/44.85/25.68/25.71/40.42/40.32FPS, inference4.00/s and zero camera/NPU
failure counters. This supports candidate-specific regression but does not
identify its root cause. Original runtime remains active during investigation.

Isolated candidate_fair_viewer implemented FIFO transport admission and priority
END after active DMA, releasing transport during converter poll sleep and owned
RAW copy. Sole converter admission/fullRX reservation/model geometry/decoder
remain intact. Local threaded6000-camera/1000-retirement checks, all-six exact
fixtures at480/640 heights, poll negative regression and Qt syntax passed.
Cam2 root cause remains unconfirmed: low tag advancement suggests FPGA publication
loss, not merely skipped host reads. FAIR_REVIEW.md records evidence and limits.
ARM64 fair viewer build started with existing concurrent driver0d43b3bc… planned.
OriginalPID9480 remains active; no fair candidate hardware validation yet.

Read-only copied-RTL diagnostic review identified Cam2 register base0x20000200:
+0x00faultsnapshot,+0x30offeredpixels,+0xA0overflow/short16-bit counters,
+0xF0successful publication count; CDC snapshots+0x190/+0x1A0/+0x1B0/+0x1C0.
Reads are16-byte aligned F2H with first32-bit value and have no ACK/clear side
effects; separate reads are not atomic. Sampling must use existing owner shared
transport/scratch0x3FF000, never another deviceopen/allocator. Separate default-off
diagnostic viewer preparation started for fallback if fair candidate still regresses.

Fair ARM64 viewer build1791599456157085900 completed, executableSHA256
decd934b04c0fe614ec65c366313c96c6a08c63257b10c1487547aefd036d8ea.
All six board device-free selftests PASS. Deployment with concurrentdriver0d43…
and verification enabled started from originalPID9480. Separate diagnostic
candidate_fair_diag_viewer is ready locally, defaultOFF, samples through owner
transport and reports worker empty/retry/error counters before early continues.
No diagnostic hardware/build claim yet; fair hardware results pending.

Fair deployment1791600369555232400 live input/native parity >=30 exact Cam1
MVP pairs. Verification-offPID13211 CPU204.88% over30.013s. Trailing7 windows
capture34.76/44.59/25.77/25.76/40.22/40.36FPS, inference3.29/s, paint32.94FPS.
Cam2 regression recovered with fair scheduling; selectedCam1 and inference
remain below baseline, so candidate still fails full non-regression. No established
efficiency gain. Original restore started; isolated selected-frame hold/request
timing investigation underway. Evidence fair_performance_* files.

Original restore1791600533349097000 completed withPID13717. Health log confirms
six rates44.99/44.89/25.66/25.74/40.38/40.40FPS, inference4.00/s, zero camera
errors/NPU failures. Future sampler now also preserves log byte-window evidence
around CPU sample, reducing reliance on whole-log trailing windows; SSH overhead
and aggregate-window boundaries remain explicit limits.

candidate_short_hold_viewer isolates RAW CPU copy after verified conversion,
camera release and selector restoration. Completed host RAW slot remains owned
by the same single camera worker; sole converter admission stays occupied.
Local actual-body copy-boundary/disjoint-DMA/geometry/native fixtures and negative
old-ordering test pass. ARM64 build started. Consumer lease_ms is not FPGA hold
duration; existing logs cannot establish converter latency or expected FPS gain.
No request scheduling/model/decoder/driver/RTL change. OriginalPID13717 active.

Short-hold build1791601015642641700 c7cae5aa… passed6 target selftests;
deploy1791601917163253000 input/native parity >=91 exact pairs. Verification-off
PID17225 CPU209.59% over30.007s; sample-local6 aggregate windows captured
39.02/44.42/25.73/25.69/40.20/40.24FPS, inference3.17/s, paint32.98FPS.
SelectedCam1 improves vs fair34.76 but still below baseline44-45; no overall
gain accepted. Original restore started. Separate phase timing and request
preparation/cadence analysis underway. Evidence short_hold_performance_*.

Original restored via1791602150521334900, PID17828; health confirms about
45/45/26/26/40/40FPS and4.00 completed/s, zero errors. Timed viewer ARM build
in progress. Source review confirms ordinary preparation begins after cadence
deadline, adding acquisition/READY/dispatch delay before actual submission.
candidate_prefetch_viewer experimentally arms one frame up to120ms early;
submission timestamp/interval and single-slot ownership remain unchanged.
Host clock/lifetime/switch fixtures pass; full vision compilation awaits ARM
OpenCV environment. Preparation delay decomposition remains hypothetical.
Earlier preparation may increase source-frame age, so readiness/source-age
and throughput require measurement; no latency/performance gain accepted.

Timed ARM64 build1791602274321871500 completed SHA256179b2dfa… and all six
target selftests PASS. Deployment started from originalPID17828 with timing and
input/native verification enabled. Timing diagnostics add no DMA and use monotonic
phase clocks; verification-on timing cannot be a performance acceptance sample.
Prefetch ARM build deferred until timing acquisition to avoid compiler contention.

Timed deployment1791603180344213200 passed >=16 exact input/native pairs.
Verification-off timingPID20592 sample30.006s CPU211.16% diagnostic only.
101 sample-window timing rows: command-to-release-ack hold mean22.27ms/max39.06;
converter-start-to-observed-done mean8.64ms/max27.89; command-to-hold-validated
mean12.24ms/max29.92; postrelease CPU-copy interval mean7.36ms; read-entry-to
publish mean31.18ms/max47.51. Wall intervals include scheduling/poll/transport
waits, not isolated hardware cycles. They do not measure arm-to-read wait or
ready-to-dispatch, so 66ms preparation decomposition remains unproven.
Evidence timed_phases.json and timed_diagnostic_sample_window.log. Original
restore started before prefetch build; no timing candidate adoption.

Restore1791603288143321800 completed, originalPID21001. Health confirms4.00
RKNN completions/s and zero errors. Prefetch ARM64 build started; compilation
contends for boardCPU so contemporaneous captureFPS is not a baseline sample.
Independent read-only prefetch lifecycle/ingress/age review started before live
trial; hardware correctness and throughput still pending.

Independent prefetch review found two P2 risks: ingress pin rejects newer RAW
analytics until prefetched dispatch (extra cooldown tracking freeze), and earlier
capture increases detector source age despite higher possible request rate.
No newP1/datarace/busyCPUfallback identified. Existing prefetch candidate will
not deploy. Separate candidate_prefetch_live_viewer work started to retain exact
prepared input/correction snapshot separately from latest RAW tracking ingress,
with actual-pipeline tests and capture-to-request/start/result age evidence.
Default120ms lead is a design allowance, not measured latency limit. Original
runtime remains active. No optical latency claim; capturedMs is hostRAW DMA time.

Old ingress-pinning prefetch build1791603331913753300 c734ae63… completed but
will not deploy. New candidate_prefetch_live_viewer separates retained exact
prepared input from latest two-entry RAW mailbox and tracker processing.
Correction source/replay suffix retained up to64 entries (larger memory footprint;
overflow skips evicted intermediate replay entries). Default-off age events include
publish/request/GUI/start/result. Host fixtures pass; added actual pipeline tests
await ARM build179… started now and independent review. No hardware acceptance.
Board had1190MiB available before this build; no simultaneous compiler detected.

Independent live-prefetch review found P2 dispatch-before-source-history race:
request rereads newly arrived retained input after worker snapshot, allowing
submission before processFrame builds exact correction history. Live candidate
not cleared for hardware. Separate candidate_prefetch_checked_viewer started
with exact processed-history identity gate and deterministic interleaving test.
64-entry overflow correction gaps also require explicit rejection/validation;
sampled mailbox precedent does not prove equivalent replay accuracy. Peak RSS
and replay/source-age evidence remain acceptance requirements.

candidate_prefetch_checked_viewer now implements exact processed frame/Input/
image/grayscale/tracker-snapshot gate before dispatch. Overflow retires unsubmitted
source or rejects pending correction before gaps form; existing live tracks retained.
Actual-worker race/overflow fixtures added but execution awaits ARM compile.
Host preservation/protocol/cadence/native checks pass. Independent rereview started.
Prior live-candidate ARM build still running make-j1/cc1plus; checked build deferred
to avoid simultaneous compilation. Original production remains active.

Independent checked-candidate rereview found no remaining substantiveP1/P2;
approved only for ARM full-pipeline tests, then bounded paired hardware trials.
Exact processed-history gate and overflow invalidation prevent uncorrectable
dispatch/gap replay. Up to65 transient histories ~76MiB images plus snapshots;
memory/source-age acceptance unresolved, no production recommendation.
Runtime sampler extended with1-second observedRSS peak, start/endRSS and kernel
process-lifetime VmHWM (not confused with sample-only peak). ARM tests pending.

Prior live-candidate build1791604192916125800 92997215… completed but is not
approved for deployment due to superseded race. Checked-candidate ARM build
started. Added summarize_infer_age.py: matching generation/camera/frame/tag/
RAWtimestamp identity, publish/request/GUI/start/accepted source-age p50/p95/max,
separate all-event distributions and boundary limits. Synthetic aggregation
checks pass; no actual board age evidence yet. Capture timing excludes exposure.

Checked ARM64 build1791605074176855000 completed executable040b751d….
All6 targetselftests PASS including compiled completeVisionPipeline actualworker
race/cooldown/exactsource/replayoverflow tests (vision.selftest.log). Independent
review already cleared bounded trial. Deploy started from originalPID21001 with
feature, input/native verification and source-age telemetry enabled; no acceptance
claim until >=30 exact pairs and verification-off paired performance/age/RSS.

Checked deploy1791606010791168000 passed123 exact MVP input/native pairs.
ONPID27615 30.082s CPU204.64%, observedpeakRSS181924KiB; sample aggregate
capture38.84/32.82/25.73/25.73/40.39/40.39FPS, completed3.83/s, paint36.00.
Same binary/FPGA/driver OFFPID27931 30.079s CPU212.54%, peakRSS159164KiB;
capture45.03/33.52/25.73/25.73/40.39/40.35FPS, completedaggregate3.67/s.
Both contain118 complete same-ID source-age sets; aggregates straddle sample
boundaries/startup, so aggregate rate difference is not established throughput gain.
ONvsOFF matched accepted age p50=172/103ms,p95=204/138ms,max=236/144ms;
RKNNstart p95=147/86ms. HostRAWtimestamp, not exposure/optical latency.
ON uses22.23MiB more observedRSS; CPU difference also reflects lessCam1work.
Cam2 remains low even OFF on candidate hardware pair; rootcause unresolved.
Candidate fails capture/source-age non-regression; original restore started.
Evidence checked_on/off_* JSON/windowlogs/age_summary and checked_verify_evidence_*.

Restore1791606262941167900 completed, originalPID28361. Health confirms
44.55/44.71/25.72/25.70/39.74/39.94FPS,4.00 completions/s, zero errors.
Cam2 recovers with original hardware/runtime pair. Low-frequency read-only
candidate_fair_diag_viewer ARM build started to diagnose candidate-pair publication
loss without modifyingRTL or independently opening device. Compiler contention
excluded from acceptance samples. Prefetch not adopted.

Diagnostic build1791606313874791300 executable13d4b271… compiled and all6
ARM target selftestsPASS. Deploy with DETVIEW_CAMERA_DIAG=1 started from
originalPID28361, same concurrentdriver0d43… and candidateSRAM81eb….
Cam2 read-only9-register sampling5s through existingowner transport; allsix
worker returncounts recorded. No additional deviceopen, clear/ACK writes.
Diagnostic trial intended to isolate hardware publication loss, not performance
acceptance; pending sample and clean restore after evidence collection.

Diagnostic deploy1791608172505482000 PID32721 sampled30.079s. Cam2first
5.001s window:225SOFs,189successfulpublications,18newshorts,0overflows,
fault0x4004affe short=1 acceptedpixels307198. CDCsource/out307884/drop0.
Nextfive windows:225-226goodpublications per~5s,0newshorts/overflows,CDCdrop0;
Cam2recovered~45publication/s. Separate reads not atomic, fault persists.
These establish intermittent capture-short events coincident with publication
loss, not converter/DDR root cause. Overallcapture39.20/43.77/25.73/25.74/
40.38/40.36FPS, infer3.00/s, CPU213.84% diagnostic only. Originalrestorestarted.
Read-only copiedRTL frame-quota/packing/SOF analysis underway. Evidence
camera_diag_on_sample_window.log and relatedJSON. No candidate acceptance.

Restore1791608274721868300 completed; originalPID33163. Health confirms
43.49/44.40/25.73/25.73/40.15/40.23FPS,4.00 RKNN completions/s, zero camera
errors/NPU failures. Original remains active while intermittent capture-short
source analysis runs. SPI Flash unchanged; all candidate trials remain unaccepted.

User redirected work to restore yesterday's remembered Cam1/2/5/6 display30
version. Board preserved restored_display30.log ends with per-camera uploads
~30FPS; preserved display-fix executable SHA73613d… matches current executable.
Historical board launch scripts specify QT_QPA_PLATFORM=xcb and
QT_XCB_GL_INTEGRATION=xcb_egl; prior restored environment omitted both.
Before restart PID33163 had independently exited SIGTERM(-15), no fuser owner
but module refcnt1. No forced unload/reuse attempted. Authorized reboot cleared
state; new boot ecec42a0-46bc-434b-a12c-ec45433a8437. Original SRAMfcb2…
reprogrammed, original module4506… and preserved display-fix73613d… launched
with EGL and MVP fullscreen. CurrentPID2090, evidence display30_reboot_recovery.
30.085s CPU205.88%, six errors zero, RKNN4/s. Six aggregate display windows
30.295s fresh uploads26.41/25.88/21.72/21.88/26.14/26.21FPS. Preserved
display30 executable/environment restored; sustained per-camera30 not reproduced
in this window. No further candidate rollout. SPI Flash unchanged.

User now authorized resuming unfinished RGB888 DMA-BUF/RKNN work based on
current display30 runtime. Preserved live PID2090/boot ecec42a0… exact argv,
environment, binary identity, SRAM/driver provenance in
display30_baseline_1791610128881772700/baseline.json and artifacts.json.
Fresh30.074s baseline CPU193.29%; delivered42.20/43.59/25.72/25.72/39.87/
39.73FPS, aggregatecompletions3.83/s andpaint26.14FPS. Display still varies;
no claim of stable30 reproduced. Compositor=true/governor=ondemand restored.
Read-only hold/protocol and smaller-prefetch-lead review started; preserve latest
RAW tracking and exact processed-source snapshots. Previous120ms lead not
accepted due source-age/capture regressions. No new RTL deployment authorized
by unproven frame-boundary hypothesis alone; all work confined toov56401.

Host protocol review confirms holdACK may await residual admitted capture,
writer/DMA/pending/flush retirement and32quietcycles; no explicit nextSOFACKwait.
Polling already unlocks and uses1ms sleep/fresh FIFO admission. Blind tighter
polling is not established improvement. Isolated candidate_prefetch_lead_viewer
implementation started: validated0..120ms configurable lead, default30, exact
source-history gate and latest RAW analysis retained. Expectedgain unproven.
Prepared switch_prefetch_trial.py for same-binary0/30/50/OFF comparisons;
requires >=30 preserved same-camera/tag/count exact input/native pairs before
verification-off restart, and checks boot/helper/lock/binary before stopping.
Host checks pass for old123-pair evidence, mismatched tag and nonexact rejection.
No board candidate rollout yet; originaldisplay30PID2090 remains active.

Lead candidate complete: default30ms,0..120ASCIIinteger, invalid=>0warnonce,
effectiveleadclampedtointerval. Default-off seven-stage timing uses monotonicms
and same submitted frame identity; no additionalDMA. Host config/cadence/lifetime/
wrappedprotocol OFF/ONtiming/native/negative checksPASS. Independent review and
isolated ARMbuild started. Full VisionPipeline test pending ARM/OpenCV. Added
summarize_prefetch_timing.py with ordered same-identity wallphase quantiles,
cancelledframe exclusion documented; syntheticphase/empty checksPASS.

Independent lead review reran substantive extractedPangoDev/config/lifetime
checks: no new ownership/DMA/protocol blockers. Full realworker ARM test still
required. Clockhelpers inherit ignoredclock_gettimefailure; summarizer now rejects
anyzero/negative phase ratherthan accepting zero-filled ordered records. Host
zero-clock rejection passes. Age summary now reports observed request/GUI/RKNN
event spacing; actualloggedemission timestamps differ from cadence entry timestamp,
so cadence claims require observedinterval evidence. No hardware rollout yet.

Lead ARMbuild1791610679291473400 SHA75b73970… completed; all6 boardselftests
PASS including actual VisionPipeline race/history/overflow fixtures. Deployment
started from preserved display30PID2090 with30mslead, exact input/nativeverification,
same-ID age and prefetchphase timing. Concurrentmodule0d43… manifest supplied.
Parity collection and verification-off0/30/50 trials pending deployment completion.
Recorded original launchenvironment will be restored on unsuccessful acceptance.

Initial lead deployment stopped at bootstrap snapshot: PID2090 absent, before
any hardware/runtime mutation. Fresh owner inspection found sole PID5727 running
preserved SHA73613d… MVPfullscreen with xcb/EGL. Boot unchanged ecec42a0….
Saved fresh identity/argv/env to display30_current_owner.json. Original restart
cause not yet established; no quarantine/reboot inferred from missing oldPID.
Deployment restarted with verified actualownerPID5727, same reviewed lead build
and concurrent module manifest. Pending automatic deployment completion.

Lead deploy1791611650492874600 completed. Preserved143 same-camera/tag/count
exactinput/nativepairs. Verification-off sequential0/30/50/OFF30s samples:
Cam1=38.64/38.06/37.73/44.37FPS; Cam2~44.57-44.73, Cam3/4~25.73,
Cam5/6~40.1-40.3. Aggregatecompleted=3.50/3.50/3.83/3.83/s (boundaries).
Matchedacceptedagep95=151/144/152/162ms, counts100/110/116/118.
Actualrequestintervalp50=308/277/264/260ms, min281/253/250/250ms.
Thus shortlead reduces preparation-induced request delay without old120msage
penalty in these sequential samples; no full acceptance or efficiency claim.
CPU0/30/50/OFF=198.47/197.70/197.70/204.90%, reducedCam1workconfounds.
ONobservedRSSpeak~192MiBvsOFF172MiB. FreshdisplayC1/2/5/6:
0=25.15/26.77/27.27/26.97,30=24.86/26.87/26.70/27.10,
50=25.12/26.97/24.99/24.92,OFF=26.28/25.92/25.09/25.26.
Timingwallholdmean0/30/50=25.99/25.58/24.73ms; arm-publish45.55-47.60ms.
Lead cannot fixholdloss; originalrestorestarted. Detailed lead_comparison.json
andlead*_sample_window.log preserve boundaries/age/phases. Read-only overlapping
converter/RAWtransfer analysis started; no protocol reorder implemented yet.

Restore1791611991559655900 programmed originalSRAM and launchedPID11081 but
health FAILED: first16byteRAWmetadataDMA timeouterrno110, sixfailuresexit3.
Kernel uncertainDMA/consumer lifetime rebootrequired; refcnt1 withnoowner.
Preserved restored_health.log/dma_failure_kernel.log; noforcedunloadreuse.
Authorizedreboot recovery completed boot19abd024-aaa0-462a-bcc9-214658d0c23c,
originalSRAMfcb2… originalmodule4506… display-fix73613d… EGL/MVPfullscreen
PID2028. Recovery evidence lead_trial_reboot_recovery. Fresh30.094s sample
capture44.04/44.57/25.72/25.73/40.12/40.04FPS, aggregatecompleted3.83/s,
paint29.16FPS CPU203.80%. Original remains active; SPIFlashunchanged.

Read-only review supports isolatedhost conversion-beforeRAWF2H overlap while
hold remains asserted and initialidentity/tag, RAWtag, exactjobs+1 andfinalidentity
allverifiedbeforerelease. Estimate1-3ms possible saving unproven. candidate_overlap
implementation started with genuineasynchronous completion/errorcleanup fixtures;
no newhardwaretrial untilfailuredrain/identity/earlyrelease review passes.

Continued overlap candidate implementation in isolated directory; originalPID2028
retained. sample_runtime.py now accepts bounded --seconds1..1800(default30).
Started180s original observation (overlap_original_long) without profiling.
Added summarize_fresh_display.py pairing complete six-camera upload blocks with
their own display-perf interval, reporting weightedmean/min/max and low-window
counts. Recovery30.415s complete display windows show C1/2/5/6 freshupload
27.09/26.96/26.34/26.60FPS; no completewindow reached30 for these cameras.
Healthy capture/inference does not establish restored stable30 display.

Original180.520s observation complete: CPU203.72%, RSS177004=>177136KiB,
observedpeak177396KiB. 36contiguous complete displaywindows181.901s:
C1/2/5/6weightedfresh27.08/27.36/26.17/26.18FPS; below30windows
31/31/35/35of36; minima24.77/24.57/23.56/24.01FPS. Occasionalpeaks
32.56/33.34/31.48/31.28FPS do not establishstable30. All36capturewindows
mean44.56/44.69/25.73/25.72/40.25/40.26FPS; RKNNcompleted3.92/s.
summarize_runtime.py gained --all-samples because legacysummary truncatedcapture
to12windows; longobservation uses all36. Original staysactive; overlapcandidate
async/failurecleanup implementation remains in progress, no additional deployment.

Overlap candidate implemented. Production delta only reorders jobsread/trigger
before fullRAWF2H after initialidentity/tag gates. Host genuine asynchronous
conversion-beforeRAW and RAW-beforeconversion fixtures pass allsix/bothgeometry,
16rejectioncases and3mutations. Fatal failures use inherited SIGSTOP/quarantine;
this is fail-stop protection, not recoverable failed-frame cleanup. Independent
review and isolated ARMbuild started; no candidate deployed. Fresh original
snapshot confirms PID2028/start4002/boot19abd024… SHA73613d… MVPfullscreen,
saved overlap_original_identity.json. Require parity, performance and actual
restoration health before acceptance; previous rollback timeout remains relevant.

Independent overlap review complete: no production blocker conditional on exact
ARM pipeline tests and quarantine recovery. Review was read-only and inspected
saved tests, not a fresh rerun. Initial fullidentity/newtag gates, exact wrapping
jobs+1, RAWtag/finalidentity-before-release and copy-afterdefaults preserved.
Physicalquiescence remains unproven by exception-based host fixtures. Trial
recovery explicitly requires retained failureevidence and authorizedreboot for
uncertainstate, originalSRAM/module/viewer recovery and livecapture/inference
health checks; no automatic reopen/forced unload. ARMbuild still outstanding.

Overlap ARMbuild1791612684241983800 completed SHAe2d7280c…; exact binary
passed six board selftests including full VisionPipeline. Bounded deployment
started from originalPID2028, 30mslead with exact input/native verification and
same-frame age/phase logging. Candidate hardware parity/performance pending.

Initial overlap deployment aborted in bootstrap before mutation because PID2028
was absent. Fresh snapshot finds sole original ownerPID5393/start133826, same
boot19abd024… SHA73613d… MVPfullscreen; saved overlap_actual_owner.json.
Old process exit cause unestablished. Restarted deployment against verified5393.

Overlap deploy1791613638189975800 succeeded. Preserved129 exact input/native
pairs for Cam1/MVP (921600inputbytes,434700nativebytes); no multi-model/camera
parity claim. Verification-off ON/OFF/ON30s comparison saved overlap_comparison.json:
Cam1capture38.14/44.86/38.72FPS; othercameras~44.8-45.0/25.73/25.73/40.3/40.3.
Matchedacceptedagep95=140/143/121ms, counts111/117/113; requestspacingp50
271/261/272ms. HoldmeanON23.81/23.15ms, validated-to-release9.21/8.51ms.
Earlier serial30mslead holdmean25.58ms, validated-to-release10.60ms: descriptive
cross-session comparison only, no matched causalproof. CPU203.0/213.1/207.3%,
ONpeakRSS~191-192MiB versusOFF~170MiB, capturelossconfounds CPUbenefit.
FreshC1/2/5/6: ON27.12/29.35/27.02/27.31,OFF30.75/30.72/27.92/28.45,
repeatON30.17/32.77/30.40/30.59. Shortdisplayvariation remains; no stable30claim.
Aggregatecompleted3.83/3.67/3.67/s versus matchedcompleted111/117/113 boundary
counts. Cam1capture regression persists -> candidate not accepted. Original
restore started; live recovery health still must be verified after completion.

Overlap rollback1791613903279328100 completed and healthverified, no reboot
needed this time. OriginalPID7729 is sole owner; sixcameraerrors zero in healthlog,
no startupDMA timeout. Fresh30.093s sample CPU212.34%, RSS174252KiB stable,
capture44.76/44.90/25.72/25.72/40.35/40.33FPS andRKNN4.00/s.
Complete30.399s freshdisplay C1/2/5/6=31.91/31.78/30.03/29.77FPS;
C5/C6each3of6windowsbelow30. This shortsample does not supersede preceding
180s failure to sustain30. Artifacts overlap_restored_original_* and
deploy_1791613903279328100/restored_health.log. OriginalSRAM/module/displayfix
active, no SPIFlashchanges, no commits. Overlapcandidate remains unaccepted;
no builds/subagents outstanding. Acquisitionhold remains main observed cost,
but skippedSOF count and graphicswait rootcause not directly measured.

Continued GUI debugging: current externally restarted originalPID9992 samehash
boot19abd024…, log/userdata/surround360/evidence/grab_probe/restored.log.
Five-second GUIstrace106samefutexwaits2.6629s; two boundedgdb snapshots ON/OFF
bothlibc->libmali eglSwapBuffers->Qt xcb EGL. Normaldetach verified, subsequent
capturehealthy. Attribution to sampled swapwait now direct; internalcauseunknown.
CompositorON/OFF/ONfreshC1/2/5/6=25.41/25.25/24.86/24.39 ->
29.04/29.07/27.19/27.26 ->31.51/31.34/29.07/28.90; no reversibleonlycause.
Compositortrue/vblankauto restored. No hardware/runtime replacement. Started
isolated default-off EGLforwarding/timing diagnostic implementation, hostonly.

EGL probe host tests10cases+4smokes reportedPASS. Parent inspection identified
viewerinitialELF lacks EGL, so constructor-only RTLD_NEXT requires earlyMali
load. Native ARM build1791618116956610000 links existinglibmali explicitly,
SHAa45d84ec… readelfdependencyconfirmed. Native invalid-display smoke returned
false and logged interval0, confirming resolution/forwarding, not renderhealth.
Bounded same-original probe trial started: snapshot9992, gracefulq/refcntzero,
sameSHA/args/env pluspreload30s, gracefulverifiedretirement, originalenvrestore
and30s livehealthsample. No FPGA/driverchange. Results pending; earlyMaliload
itselfpotentialconfound. Successful intervalrequests do not prove effectiveinterval.

EGL trial1791618223497539800 completed, exactenvrestored originalPID18602 and
live30shealthy. Actualinterval0requestsuccess1;1031swaps/30.152s mean19.12ms,
max44.03ms,587>=20ms, swapwallfraction65.37%, zero invalidclocks. Probe/restored
freshC1/2/5/6=30.83/30.76/28.33/28.56 vs30.96/30.80/29.48/29.05; capture
~45/45/26/26/40/40 andinference4/3.83. Swapblocking persists despite accepted0.
Started boundedinterval1 request comparison via sameprobe, exactenvrestorethen
healthsample included. No hardware/driverchanges. Performanceacceptancepending.

Interval1 diagnostic completed, requestsuccess1, mean31.32ms vs prior0mean19.12,
freshfour19.24/19.24/19.30/19.27FPS, capturehealthy,inference3.5/s. Exactbaseline
envrestoredPID19091 fresh25.54/25.11/23.80/23.30,capture44.19/44.74/25.75/
25.76/40.28/40.38,inference4/s. CPUdrop183vs203% reflectsreducedwork.
Started bounded samePIDfullscreencompositorbypasshint1 observation with original
hintfinallyrestore and postrestorehealthsample. Hint alone cannot prove WM honors
unredirect; no permanenttuning orhardware/runtime replacement.

Bypasshint trialcompleted andpropertyrestored: freshC1/2/5/6=26.03/26.29/25.60/
25.80vs28.82/28.59/27.34/27.57, sixcapture/inferencehealthy; no gainestablished.
Next bounded trial existingoriginalDETVIEW_TEXTURE_RING=3 vsbaseline1 withEGL
timingprobe and exactenvrestore. Sourceinspection confirms only changedcamera
textureuploadslot rotates, latestslot drawn; no inference/capturechanges.

Ring3trial completed ->originalenvrestoredPID20413. meanswap21.47ms,
fresh27.05/27.35/26.49/26.40vs restored28.94/28.91/26.34/26.40, no gain.
Allthreads stack backend20421 inxcb_request_check whilemaininswapwait.
Main/backend4strace79mainsamefutexwaits1.6735s and79backendwakecalls; wait
produceridentified, notfullinternalcause. Debuggers/tracesdetachnormally;
posttrace6captureerrorszero,originalhealthy. Isolated XCB confirmation perthread
timerimplementationstarted hostonly. Baselineallsettingsrestored,nohardwarechange.

XCBtimingprobe complete: host24cases reportedPASS, parent read-only inspected
exactcookie/errorpointer/errno forwarding and noXCBextraqueries. Native ARMbuild
1791619201636799100 SHA6298a7ef… explicitlibxcbdependency passed realX11checked
noop forwarding smoke. Combined EGL/XCB30s trial started against original20413,
then exactoriginalenvrestore+30shealthsample. Clock/windowinstrumentation remains
diagnostic only, concurrent XCB/EGL durations cannot be added as exclusivewaits.
No FPGA/driver/production-source modifications; results pending.

Combined EGL/XCBtrial completed, exactenvrestored22571 and30shealthverified.
Backend22425 805checks mean19.20ms/51.35%windowwall; EGL806swapsmean25.77ms/
68.90%wall interval0success. Large XCBconfirmationcost directlymeasured; exact
requesttype and Xserver/internalqueuecauseunknown. Sixcapturehealthy~44/45/26/
26/40/40,inference3.83/s; fresh24-25vsrestored24-25, no improvementclaim.
Mali importsPresentchecked/DRI2 APIs. Started isolatedperthreadcookie+connection
requesttype/opcode diagnosisimplementation; no hardware/runtimechangepending.

Requestclassificationprobe host40enabledABIcases plusdisabled/missing/realxcb
smokes reportedPASS. NativeARMbuild1791619881076001100 SHAcb8b267d… passed
realX11checkednoop forwarding. Classify trialstarted from original22571 with
sameEGLtiming, threadlocalconnection/sequenceboundedmatching; unknown stays
unknown, noextraXqueries. Exactenvrestore andlivehealthsample partoftrial.

Classifytrialcompleted/exactoriginalenvrestored24297. Backend830checks all
Presentopcode1/Pixmap checkedflags1, mean17.30ms,max71.17ms; same830swaps
mean23.98ms interval0success. No unknownclassification/clockerrors. Capture
healthy,inference3.83/s, stable30 stillunmet. Xorg historicalfliptimeouts found;
matched30sreadonlyobservation1newHDMIcrtc72timeout,0DSIcrtc96. DRMmapping
verified, fourfresh30.44/30.48/29.26/29.26 withlowwindows. Presentconfirmation
familyidentified but exactserver/DRMfencecauseunproven; don'tequate1fliptimeout
withallreplywaits. Bothoutputs retained, original24297active, settingsrestored.
Noactivebuilds/subagents/trials; diagnosticartifacts retained, noSPIFlashchanges.

FlipFB configuration cycle1791621146547396400 completed with originalenv/session
refresh and exactconfigrestoration, originalviewer29876 samehash73613d…,
configSHAac4d85ee…, sameboot, sixerrorszero, HDMI/DSI retained. Three180s
freshC1/2/5/6original/none/restored=22.59/22.67/21.86/21.94 ->
36.45/36.25/33.51/33.59 ->24.36/24.16/23.19/23.18. Strongdisplayimprovement,
notacceptedstable30: none36windowsbelow30counts2/2/2/3. CPU258.9/235.7/214.1
notreversiblebenefit; capturehealthy,inference3.65/3.83/3.86. Result-ageevents
absent, optical/tearingunverified. Prepared60swarmup/180A/600B/180A repeat
withmatchednewXorglog and uniquefilenames. NoFPGA/driver/SPIFlashchanges.

Warmedrepeat1791621823490481400 complete. Original180/none602/restored180s
freshC1/2/5/6=31.65/31.50/29.49/29.52 ->36.54/36.65/34.63/34.73 ->
25.93/25.88/24.74/24.83. None120windows below30=1/1/1/2: sustainedmean
improvement confirmed, strictstable30unmet. CPU214.59/233.65/202.09%; Cam1
capture44.98/41.79/44.43 (~7.1% loss vsbefore), otherscapture25.7-43.5;
inference3.83/3.85/3.89/s, sixerrorszero. Therefore no whole-system acceptance.
MatchedXorgtimeoutcounts0/0/80; no claim timeouts alone explain regression.
Exactoriginalconfig/executable restoredPID34196, postrestorelivecapture~45/45/
26/26/40/40, errorszero, bothoutputs retained. No active trials or background
work; noSPIFlash/hardware/driver changes. Next: boundeddisplaywork withFlipFBnone
to addresscapturecompetition, preservebaselineuntilallgatespass.

USER-SELECTED CURRENT VERSION: user explicitly accepted the warmed FlipFBnone
version with historical viewer-process CPU~234%, and requested live screenshot.
Adoption1791623759826415100 verified currentowner36192 (externalreplacement),
gracefully retired, atomically persistedFlipFBnone, restarteddesktop, launched
sameoriginaldisplay30 hash73613d… asPID37468 with unchangedmodel/argv and
refreshedsessionkeys.30swarmup+30shealthsample passed6have/6errorszero,
HDMI/DSIlayout preserved, configcandidatehash verified, deploylock released.
The selected configuration remains active; rollback config is preserved in the
adoption directory. This records user selection, not proof all prior performance
gates pass. HistoricalCam1captureloss/CPUcost and unmeasuredopticaltearing remain.
ActualX11 screenshot adopted_flipfb_screenshot/hdmi.png shows HUDnew41fps,
percameraimageC1/2/3/4/5/6=32/35/26/27/36/36 atcaptureinstant.
Screenshot values are instantaneous, not the ten-minute averages. NoFPGA,
driver, SPIFlash, commit orpush changes. No activebackgroundwork.

SSH recovered without a reboot (boot ID644568c5-2252-4240-87b0-d0810cbc4131).
Original viewer had exited with its own no-new-frame watchdog; no OOM kill was
found. Device owner and module reference count were zero. The unchanged original
viewer was restarted after identity/boot/ownership checks: PID18980, receipt
original_resume.json. original_resume_health.log confirms all six cameras,
zero reported camera errors, MVP decode_ok=1 and approximately4 RKNN completions/s.
Observed capture rates during remaining compilation were33.63/37.07/25.48/
25.73/36.57/36.15 FPS; these are recovery health samples, not performance acceptance.
Candidate FPGA image/module remain undeployed. Future viewer builds use make-j1
and must not be launched concurrently.
