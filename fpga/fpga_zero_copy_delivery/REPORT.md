# FPGA shared input and display offload: verification in progress

The user clarified NPU removal means the FPGA legacy NPU. RK3568 RKNN stays
enabled. The running baseline already excluded legacy NPU instances and
project entries, so this work cannot claim an additional NPU resource saving.

## Verified hardware shared-input path

FPGA RGB888 preprocessing writes a separate DDR output; PCIe F2H DMA writes
the coherent RX input slot at offset2MiB. The driver exports its4MiB allocation
as a DMA-BUF, RKNN imports and binds the slot, and a driver lease prevents
overlapping DMA until synchronous inference completes. There is no application
input memcpy or inputs_set on this candidate path. Importer addresses are mapped
for the importing device and checked against the backing pages; PCI bus
addresses are not passed as NPU physical addresses.

The successful two-pair smoke compared all1228800 input bytes and all native
outputs exactly. CPU versus FPGA stage totals were33.206 vs32.851ms. This is
too short for a performance conclusion. A240-pair exploratory run also passed
parity but overlapped a target build and is archived separately. A clean formal
run subsequently passed:10 warmups+240 timed alternating pairs with no target
build processes. Mean CPU37.3971ms versus FPGA36.6025ms; reciprocal stage
throughput26.7401 versus27.3205/s (+2.1708%). Inputs and all native outputs matched
on every pair. Mean RAW DMA+copy6.2899ms, CPU preprocess3.3227ms, FPGA preprocessing
plus RGB DMA8.9400ms, RKNN26.8060/26.6841ms. Input submission0.6967ms versus
shared submission/lease0.02379ms. Evidence:shared_pairs240.jsonl and summary.
Tests use the pinned V8 model, viewer paused, and frozen source
frame per pair; do not transfer these numbers to the live MVP completion rate.

An additional240-pair run instruments CLOCK_PROCESS_CPUTIME_ID around each
complete path, including allocation, preprocessing, metadata/DMA submission,
RKNN calls and the common native-output parity copy. CPU time per pair averages
16.9661ms for CPU and7.05638ms for FPGA shared input (-58.41%). Stage wall time
56.5152ms versus54.9588ms gives+2.83195% reciprocal throughput. All input/native
output bytes matched. Evidence:shared_pairs240_cpu_accounting.jsonl and summary.
RKNN latency was materially higher in this run (~44.6ms versus~26.7ms in the
earlier run), so compare arms within each run rather than absolute results
between runs. Devfreq was not sampled during these two inference-only runs;
clock/thermal conditions cannot be assumed identical across runs. This CPU
accounting result is not a measured58.4% reduction in total six-pane viewer CPU.

An earlier pointer-only shortcut was correct but slow: inputs_set read the
coherent mapping in15.50ms versus0.73ms from ordinary memory. DMA-BUF binding
removes this call. RGB888 PCIe payload remains twice the original RAW payload;
zero-copy does not remove that transport cost or prove no internal RKNN copy.

## FPGA display candidate

640x480 RGB565 becomes320x240 RGB565 using nearest-neighbor even coordinates.
Payload is153600 instead of614400 bytes per display frame. RAW YOLO/stereo input
is preserved. Current hardware command integration leases C5 only; continuous
six-camera offload still requires generalized frame ownership.

Scaler, DDR endpoint and fabric integration tests passed full-frame parity,
random stalls, error quarantine, mode guards and final-write completion order.
Full PDS placement/routing passed All Constraints Met. Baseline versus candidate
LUT counts in the two physical categories are14691+5994 versus15244+6671;
DRM42.5 versus44.5, APM0 in both. This is added display hardware, not an NPU
resource reduction. Candidate SRAM bitstream generation completed with SHA256
09359b8508de3f5b1dafbe515a06129052ae1c46732b07784b327ac65ef02306 and JTAG
programming reported done-bit=1. A subsequent PCIe re-enumeration left the
endpoint absent and board SSH became unavailable, so live display performance
and post-program hardware capability readback remain outstanding.

The complete isolated thumbnail viewer built on RK3568 and passed thumbnail,
display-latency and vision selftests. It uses actual320x240 texture uploads and
falls back to full RAW when C5 is needed for vision/stereo/HDMI. Source
preservation evidence records unchanged inference and RAW conversion code.

The separate `integrated_six` candidate generalizes the C5 lease to six
independent admission holds with latched camera/output-bank selectors, explicit
writer-idle/pending/flush/B-retirement checks, no-frame pending status, and
allowlisted per-camera thumbnail banks. ModelSim validation passed selective C1
hold while C5 published, delayed C1 DMA retirement, later publication after a
no-frame state, selector/mode guards, and all six output-bank addresses. It
preserves C1 S05 history and S06 delivery. Six-camera PDS place/route completed
successfully (return code 0, 660.17 seconds). Its post-route timing summary is
`All Constraints Met`, with slow-corner DDR setup WNS 0.546 ns and hold WHS
0.083 ns. The two LUT categories use 15946+6492 (22438 total), DRM 44.5,
and APM 0. `fpga_resources_compare.json` includes baseline, C5 and six-camera
physical reports. Subsequent SRAM programming and initial hardware checks are
recorded below; full six-camera thumbnail acceptance remains pending.

The generated candidate was regenerated and `verify_six_camera.py` passed
again. `build_six_fpga.py` is the guarded PDS place/route entry point; it has
completed locally and never performs board access or programming.
`generate_six_bitstream.py` checks the completed build receipt, input hashes and
timing before generating an SRAM image. PDS rewrote project timestamps and flow
output metadata; the prebuild project was reconstructed with an exact hash
match, and its diff was audited before recording the postbuild project hash.
Six-camera bitstream generation passed (return code 0), producing 3791112 bytes
with SHA256 `1c3bb4783847c35bce7cd480195674cc3faa41372cc05c8742b4a8fd99fa1982`.

The latest board recovery check timed out connecting to 192.168.10.203:22.
The host currently has WLAN address 10.20.200.179 and no 192.168.10.x interface;
neither Ethernet interface has a routed IPv4 address (both are link-local).
Win32_SerialPort exposes no serial recovery port. A board-network connection or
an accessible board address is required before hardware acceptance can resume.

After the user restored SSH, the board boot log showed the PCIe root controller
had failed initial link training. `program_six_recovery.py` verified no PCI
devices/viewer owners, programmed only SRAM and reported done-bit=1. Binding
`3c0800000.pcie` to `rk-pcie` then restored Gen2 x2 link and endpoint
`0002:21:00.0` (0755:0755). The shared driver loaded and bound successfully.
The existing C5 hardware thumbnail test passed 10 frames / 1536000 exact bytes,
mean thumbnail delivery 5.6054 ms; this is correctness and isolated delivery
timing, not a full-viewer performance comparison. The production viewer was
restored and reported have=111111 and err=0/0/0/0/0/0 on the six-camera image.

Viewer/RTL reconciliation corrected source-bank diagnostics (+100/+110), freeze
admission status (+120), unpublished-frame release and sequence-wrap handling.
163 local host cases passed with strict compiler warnings and RAW/inference
source preservation. The full six-camera Qt viewer then built on RK3568 with
return code 0, and thumbnail/display-latency/vision selftests all passed.
The same binary/model ABAB display comparison (60 seconds per arm) is running;
all-camera hardware pixel parity has now passed: `thumbnail_six_parity.jsonl`
contains 10 fresh frames for each of six cameras and both output banks (120
frames, 18432000 exact thumbnail bytes). The test validates frozen RAW stability,
publication, source sequence and lease generation; no camera/bank is omitted.

The initial ABAB display run failed at 4B: `six thumbnail idle/default owner
required`. The old candidate lacked a SIGTERM handler, allowing termination
while a thumbnail lease was held; 3A also left C3 effectively frozen (one GL
upload). Results are archived in `six_display_measurement_failed_shutdown`.
2B used 51.07% CPU versus A mean 140.35% (one core = 100%), but fresh capture
fell to about 3.4 fps on C1 and 6.8 fps on other cameras, with RKNN completion
rate 3.41/s versus A 3.88/s. This incomplete run establishes neither stability
nor overall acceleration and must not be presented as final improvement.
The candidate now routes SIGTERM/SIGINT through Qt quit so its existing
controller destructor stops and joins workers after current transactions.
The benchmark waits up to five seconds for device retirement and requires
fresh capture/upload evidence from each camera. The same six-camera SRAM
image was reprogrammed to clear orphaned endpoint ownership; PCIe and pango_zc
re-enumerated successfully. Corrected viewer build and all three target selftests
passed. A new ABAB run (30 seconds/arm) passed all fresh-camera/error checks and
restored the original viewer PID 13735. CPU mean 140.8001% versus 51.0806%
(-63.72%, one core=100%), peak RSS mean 159084 versus 137190 KiB. However RKNN
completion fell 3.9083/s to 3.3137/s (-15.22%), and fresh thumbnail capture was
3.09-3.53 fps on the selected RAW inference camera versus 6.46-6.96 fps on peers.
The SIGTERM repair addresses ownership stability, not this throughput regression.
`six_display_measurement/summary.json` records these results; scalar thumbnail
offload remains an opt-in candidate rather than the default production viewer.

An independent `integrated_six_batch` / `six_camera_batch_viewer_src` candidate
is being prepared to reduce control transactions. The current AXI-to-Lite bridge
returns one beat only, so a 304-byte register read is unsafe on the deployed
image. The planned PCIe engine change forces single-beat AXI requests only within
the delivery register window and advertises a new capability before host snapshots
can be enabled. Ordinary DDR bursts and all lease/pixel-validation stages must
remain intact; simulation, timing, snapshot/scalar equivalence, hardware parity
and live A/B are required before accepting any new performance claim.

The batch candidate is now implemented with capability bit3 (caps15), scalar
fallback, and fresh snapshots at every original validation stage. ModelSim
passes 19 single-beat register addresses, backpressure, ordinary DDR burst sizes,
and actual enqueue counts up through RAW/RGB payload sizes; the old-engine
negative control fails as expected. Host reader/transport tests pass 530/1545
checks; 361 baseline hashes are verified. Vendor FIFO/PCIe and crossbar behavior
are not established by this isolated simulation (see SIX_BATCH_REPORT.md).
Guarded batch PDS place/route and isolated RK3568 Qt build have been launched.
Production viewer remains on the tested six-camera scalar image; no batch
hardware programming or performance result is claimed yet.

Batch Qt/aarch64 build and thumbnail/latency/vision selftests passed. Batch PDS
completed with return code 0 and unchanged source inputs, but the physical
timing gate FAILED: slow-corner cmos2_pclk setup WNS -0.400 ns, TNS -0.818 ns
across four endpoints. No batch bitstream has been accepted or programmed.
Timing diagnosis/closure is ongoing without weakening clock constraints.
`build_six_fpga.py` now distinguishes flow return code from timing acceptance.
The aarch64 `thumbnail_six_snapshot_parity` tool builds warning-clean and adds
snapshot/scalar checks before and after each frozen frame conversion for all
six cameras/two banks, plus the existing exact pixel/RAW stability checks.
`run_six_parity.py --snapshots` requires explicit snapshot evidence on every
frame and remains gated on the new image capability. Hardware execution waits
for passing batch timing and programming; no snapshot hardware success claimed.
Batch programming additionally verifies generated image/timing hashes and unchanged
build source hashes before any board connection. Programming logs/manifests use
candidate-specific prefixes to preserve previous SRAM receipts. Syntax checks
pass; the current unaccepted batch image is rejected before board access.

Current scope correction: Camera5/6 image defects are explicitly deferred by the
user. Future `run_six_parity.py --snapshots` defaults to physical cameras 1–4
(80 frames across two banks), with scope-specific artifact names; six-camera
coverage remains available when explicitly selected. The C++ tool validates
camera selection before opening the device. Its updated aarch64 compile succeeds
with `-Wall -Wextra -Werror`; duplicate selection returns code 2 before opening.
The display runner retains all-six traffic/logs but gates camera-specific
availability, fresh frames and capture errors on Camera1–4 by default, recording
that acceptance scope alongside each measurement. Process quarantine/crash still
fails the complete run. This scope change does not constitute new hardware or
performance evidence and does not change past six-camera test results.

Seed 2 was rejected for Camera2 hold and DDR setup violations. Seed 3 now
passes BOTH the post-hold-fix and independent detailed timing reports with
`All Constraints Met`; sources remain byte-identical to the intended batch
candidate. `integrated_six_batch/project/seed_3_closure_receipt.json` records
the actual build, source/report hashes and engine tests. `adopt_batch_seed.py 3`
revalidates this evidence before preparing the common generation manifest;
batch SRAM image generation has started. No batch hardware parity or display
improvement is established yet. The board preflight found PCIe enumerated but
no viewer owner; the original application's last log reports its no-frame
watchdog exit. Application recovery and fresh Camera1–4 checks remain required.

Batch bitstream generation completed with PDS return code 0 after 807.660 s.
Image size is 3,791,112 bytes, SHA256
`81eb0c05b40eff2887f1b81770fece6beafedc25f77fd1bbfbebe487e9dbb192`.
The scheduled continuation independently checks the final timing report and
source/image hashes before SRAM programming; generation alone is not deployment
or hardware parity evidence. SPI Flash remains outside the programming scope.

Final generated-image timing/source/hash checks passed, and batch SRAM programming
reported `done bit is 1` / success (`six_batch_program.log`). PCIe re-enumerated,
but the shared driver did not bind: kernel evidence shows earlier interrupted
RAW DMA (`-512`) at uptime 6998 s had already quarantined the driver, requiring
reboot; re-probe returned `-16`. No parity test was attempted on the unbound
driver. A coordinated RK3568 reboot was requested to clear this protection state;
PCIe, driver binding and capability bit3 must be revalidated before any batch DMA.

Recovery correction: the user clarified that RK3568 reboot requires FPGA
reprogramming. The first post-reboot snapshot attempt was invalid: initial
16-byte F2H DMA timed out (errno110), PID2380 stopped in quarantine, and the
driver again required reboot. No frames passed. Evidence is archived in
`snapshot_before_reprogram_failed.stderr`. The endpoint was unbound/removed to
disable DMA, then RK3568 rebooted again. `program_fpga.py --batch --post-reboot`
requires the endpoint absent, validates the same batch image/timing/source hashes,
programs SRAM, then restores the root controller and shared driver. This corrected
sequence has been launched; no new pixel parity result is claimed yet.

The corrected post-reboot SRAM reprogram reported success/done bit=1. The root
controller subsequently established Gen2 x2 and pango_zc bound; a premature
recovery check initially failed before enumeration completed, so the recovery
script now waits for endpoint/driver readiness. Camera1–4 hardware verification
then PASSED all 80 fresh frames across both output banks: 12,288,000 exact
thumbnail bytes, frozen RAW stability, publication/generation/sequence guards,
and batch snapshot/scalar parity before and after each conversion. Evidence:
`thumbnail_six_snapshot_parity_c1234.jsonl` and matching stderr (empty).
No Camera5/6 image diagnosis was performed. Same-binary/model batch display
ABAB (60 seconds per arm, all-six traffic with Camera1–4 acceptance scope) is
now running; no batch display performance claim is made before complete analysis.

Batch display ABAB completed all four 60-second arms, passed Camera1–4 freshness
and error checks, and restored original viewer PID3580. Subsequent live log shows
`have=111111`, zero capture errors and ongoing RKNN completions. Measured process
CPU (100%=one core) mean A139.0915%, B47.0711%, reduction66.1582%; mean peak RSS
173606→150652 KiB. RKNN completion mean 3.87584→3.57301/s (-7.81%). Fresh B capture
C1 3.53–3.63 fps, C2–4 7.01–7.25 fps versus A about23–25 fps. Therefore batching
has NOT resolved the display throughput regression and is not accepted as overall
acceleration. GL upload bytes and submit FPS are recorded separately in
`six_batch_display_measurement/summary.json`; they are not optical FPS/latency or
direct DMA traffic measurements. Remaining control/lease waits are under diagnosis.

Read-only diagnosis found the shared DMA mutex remains held throughout lease
admission/conversion polling (including 1 ms sleeps), all validation/control
transactions and restoration. The selected RAW inference camera takes two
separate mutex turns for RAW and thumbnail. B log successful read times are
roughly134–138 ms on peers and275–278 ms on C1, while final thumbnail payload
DMA is about0.3–0.4 ms. Source selects caps15 batching correctly, but viewer
logs do not explicitly attest per-transaction batch selection. Current minimum
batched healthy path still has28 ioctls (14 snapshots); lease admission must
drain existing capture/DMA, and resumed capture awaits eligible VSYNC. Release
itself has no unconditional frame timer. Attribution between mutex queueing,
admission and control calls remains unmeasured. Opt-in aggregated stage/lock
timing is being added while retaining all lease guards and stage boundaries.

Opt-in `DETVIEW_THUMBNAIL_TRACE=1` instrumentation now builds on RK3568 and
passes thumbnail/display-latency/vision target selftests. Local verification
passes 530 reader cases, 1545 transport cases and 192 paired trace on/off
transactions with identical operations/bytes/failure behavior. Aggregated
five-second lock/stage/transport counters are emitted only after unlocking DMA;
disabled tracing introduces no clock reads. A separate 30-second B diagnostic
has started with automatic original-viewer restoration. Trace results will be
kept separate from the completed formal ABAB performance evidence.

The 30-second trace B run passed freshness/errors and restored original PID7211,
which subsequently shows continuing capture/RKNN and zero errors. Trace evidence
in `six_batch_display_measurement_trace_1791537145428353100/trace_summary.json`
confirms caps15/batch selection (no scalar fallback). Physical Camera1–4 thumbnail
mean mutex waits are118.93/111.57/98.23/100.55 ms, mutex-held means
19.03/18.17/32.73/28.76 ms. Admission means12.46/11.82/26.07/22.03 ms;
conversion3.78–3.92 ms, payload DMA0.325–0.336 ms. C1 RAW additionally waits
116.92 ms and holds6.48 ms per operation. Aggregated timing confirms serialized
queueing dominates these reads; phase/ioctl timings overlap and must not be summed
indiscriminately. A separate host candidate is being reviewed to distinguish global
thumbnail lease ownership from individual DMA scratch-buffer ownership, retaining
guards and serial endpoint lease control. No new concurrency correctness or
throughput result is claimed until tests and live validation establish it.

The isolated `six_camera_async_viewer_src` candidate now retains a lease lock
through the complete thumbnail Reader transaction while each individual transport
operation and scratch copy takes the DMA lock. RAW readers can run between polls;
borrowed callbacks acquire lease then DMA and retain both (no current call sites).
Global thumbnail transactions remain serial. Local tests pass534 reader cases,
1545 snapshot transport checks and QMutex concurrency cases covering all-six RAW
interleaving, reserved detection-buffer canaries and epoch-fault quarantine.
Baseline47 files, entire Reader guards, RAW validation/copy, capture worker and
inference remain preserved (async_source_preservation.json). Isolated aarch64
full build is running; actual RAW freshness/RKNN improvement is not yet measured.

Async aarch64 build/selftests pass after correcting its distinct target binary
name. First live trace failed with no frames: kernel uptime3959 shows SIGTERM
interrupted the original production viewer's RAW DMA (-512), quarantining the
driver before async capture. Thus the run is invalid for evaluating async locks,
and restored original PID11811 likewise had no valid capture. Recovery requires
RK3568 reboot followed by FPGA SRAM reprogram (not the reverse). Future diagnostic
runner `--restore-candidate` restores the already-tested graceful-exit batch
viewer in RAW mode, avoiding repeated original-binary abrupt SIGTERM interruption.
Original production binary is preserved for rollback; no permanent installation.

After reboot/reprogram/driver recovery, async B trace passes Camera1–4 and
restores graceful batch RAW PID2528 healthy with ongoing RKNN and no quarantine.
`six_async_display_measurement_trace_1791539366985198700/trace_summary.json`
shows C1 RAW DMA-lock wait0.0197 ms (previous116.92 ms), hold6.84 ms;
all-six display capture approximately7.53–7.56 fps (C1 previously3.6fps),
RKNN3.8452 completions/s. Thumbnail lease-lock queues still94–108 ms, admission
11.8–21.7 ms and global endpoint leases remain serial. Diagnostic CPU55.52%
is not a formal comparison. Trace-disabled async ABAB60s now runs against the
same binary/model; restored RAW uses the graceful batch viewer to avoid the
original application's unsafe SIGTERM behavior. Sustained display acceleration
relative to RAW baseline remains unproven.

Trace-disabled async ABAB completed four60-second arms and passed Camera1–4
freshness/error checks. Evidence: `six_async_display_measurement/summary.json`.
Mean process CPU139.3685→53.4106% (-61.6767%); RKNN completion3.874108→3.860637/s
(-0.35%, not a statistical equivalence claim). B fresh display capture6.5–7.4fps
versus A about21fps. Therefore RAW interference is largely removed, but display
throughput regression persists. Restored PID3779 is the graceful-exit batch
viewer with thumbnails disabled, not the original production binary.

An independent capture-side thumbnail candidate is now under implementation:
tap admitted RAW pixels without backpressure, decimate even x/y, write independent
thumbnail banks, and publish only after RAW identity and DDR retirement checks.
Busy/generation/sequence guards bracket host reads into owned storage. FIFO
overflow drops only a thumbnail attempt. This removes the global display lease
from the intended read path; achieved throughput, resource fit and timing remain
unverified. Existing deployed batch RTL and all rollback candidates are retained.

The standalone background host Reader is implemented with explicit cursor commit,
stable guard/sequence brackets before and after owned DMA-copy transport, and
exact tag checks. 128 fake-transport adversarial tests pass under C++17 warnings
as errors and ASan/UBSan, including every metadata boundary, writes during DMA
and copy, failed same-sequence rewrites, wrap0 and retained-frame isolation.
Metadata constants remain provisional and DDR tag mapping is deliberately
abstracted until the RTL writer contract is established. Pure ARM64 reader tests
have been launched without opening the driver or altering the running viewer.
Restoration runner now checks accepted-camera freshness/zero errors and RKNN
log evidence before declaring a started viewer healthy.

RK3568 ARM64 pure-reader build and all128 adversarial tests now PASS (rc0),
recorded in `background_host_target_manifest.json` and
`background_host_target_selftest.log`. Source SHA256:
reader `bb66f6fa6ea134f52704b29a964c4137af48d2a520ea318b4a90b04eeca373a0`,
selftest `38a3dec242e8f06fc7e8e7e9d059a44be85806bf7b81f05cdfd13a6df445fbad`.
This test used only fake transport, opened no PCIe device and did not change
the running viewer. Actual RTL publication and adapter/hardware validation remain
pending; no display throughput gain is established by these tests.

Capture-side RTL implementation is now complete in isolated
`integrated_six_background`, with protocol in `BACKGROUND_PROTOCOL.md`.
Caps31, background control+0x180 and guarded records+0x200..+0x370 are implemented.
Tag starts at destination+153600 under the retained HMIC burst16/stride256
convention. ModelSim covers full-resolution six-camera pixels, partial bursts,
RGB arbitration, RAW publication barrier, wrap0, overflow/deadline, quarantine,
legacy handoff and actual PCIe metadata/snapshot reads. Independent RAW replay
matches10 complete frames,7 failures and61 AW/B retirements. All319 baseline
hashes and non-ASCII bytes remain preserved. These are component tests, not
full-top vendor simulation or timing acceptance.

First PDS attempt stopped at project parse before synthesis: added source entries
omitted required `_timespec` fields. Generator now includes those fields and
regenerates only the isolated source clone with byte-preserving substitutions.
Full PDS build has been restarted; viewer integration and independent RTL
correctness review run separately. No board image has changed.

Background viewer integration is complete in `six_camera_background_viewer_src`:
full128-bit record identity/address/geometry validation, owned153616-byte DMA,
explicit capability negotiation and enable/drain lifecycle, and cursor commit
after worker generation/eligibility checks. Eight local suites and protected
RAW/analytics/RGB preservation pass. Complete RK3568 viewer build/selftests have
started. Background A/B runner support uses both required environment switches
and retains separate evidence folders; no new live run has started.

Independent static review found no established correctness defect for production
640x480/DEPTH64, but identified coverage gaps in actual RAW successful publication
through a serviced background writer, faults during stalled owned AW/W/B, and a
shared HMIC memory write/PCIe-read round trip. Additional directed simulations
are being implemented without changing RTL inputs during PDS. Odd HEIGHT has a
latent parameter completion defect and is outside supported production dimensions;
the current candidate must not be generalized to odd geometry without correction.

First complete background FPGA synthesis/place-route finished rc0 in1044.86s,
with source hashes unchanged, but failed slow DDR setup: WNS-0.517ns,
TNS-1.543ns across5 endpoints. All other reported clock setup domains and
hold constraints pass. DRM use59.5/155 and APM0; resource fit alone is not
timing acceptance. A separate detailed timing report has started to identify
the actual paths before choosing a closure change. No failed candidate image
is generated/programmed and no constraints are relaxed.

Background viewer full target build lost SSH after its600-second wait timeout.
A follow-up SSH connection also timed out; ping reported destination host
unreachable from192.168.10.184 while the local Ethernet adapter remained up.
Therefore remote compile completion, binary identity and viewer health are
unknown, not failed/passed by inference. No duplicate target build or remote
process termination was issued. Local detailed timing and additional simulations
continue independently; reconnect must inspect existing make/compiler processes
and logs before rebuilding. Any board reboot still requires FPGA reprogramming
before DMA tests.

Independent additional simulations now pass12 executions/45 scenarios, with
all130 protected hashes unchanged. The serviced real RAW-controller/tap chain
passes11 reduced successes/7 aborts and4 full640x480 successes/1 failed tagB,
including unchanged-counter retry and ffffffff→0. Eight fault/deadline cases
drain stalled AW/middleW/finalW/tagB without premature quiescence; both fullFIFO
boundaries pass. Six cameras/two banks write through one HMIC model and read
through the real PCIe AXI read engine:153616 bytes each match pixel/tag golden,
with921600 inter-burst gap units retaining poison. Evidence is
`SIX_BACKGROUND_EXTRA_VERIFICATION.md` and `sim_six_background_extra/receipt.json`.
The real RAW chain covers one physical camera; six-camera transport supplies
publication inputs and vendor endpoint/FIFO models remain stubs. This closes
the identified directed functional coverage gaps without claiming physical
DDR/link or full-top validation. Follow-up board SSH remains unreachable;
full viewer target completion and live state remain unknown.

User restored board power; SSH returned with bootID
`c7d53141-35e6-4837-8a6f-84d019340340`, no remaining compiler/viewer and no PCIe
endpoint. The prior background compile had not produced a binary. Validated batch
image was absent at the expected path but present in `generate_bitstream/bak`;
its SHA256 and passing timing SHA256 exactly matched the original generation
receipt. The exact image was copied back without changing the backup, then SRAM
reprogram succeeded/done1 and pango_zc/PCIe endpoint restored. Graceful batch RAW
viewer has been started and background viewer incremental target build resumed.

Detailed background timing reports worst DDR setup-0.592ns (different detailed
analysis than placement-0.517ns). Paths originate in SFP camera FIFO read pointers
and terminate in new background producer DRM inputs through the passive pixel tap.
A coherent one-cycle register stage for pixel/SOF/valid/fault/publication/sequence
is being implemented on the new branch only, with full functional regressions
before rebuilding. This is timing closure, not deferred Camera5/6 image repair;
RAW logic and clock constraints remain unchanged.

Resumed background viewer ARM64 full build now finishes rc0; thumbnail,
display-latency and vision target selftests all return0. Evidence:
`six_background_viewer_build_manifest.json` and companion build/selftest logs.
This validates target compilation and selftests, not background hardware DMA
or drain. Current graceful batch RAW viewer PID2357 is confirmed healthy:
sampled logs show have111111, err0/0/0/0/0/0, C1–4 fresh rates around22–27fps
and continuing RKNN completions. Selftests did not replace the live viewer.

Timing correction now registers the entire six-camera passive tap tuple by one
AXI clock before the producers. Both ordinary and additional ModelSim suites
pass, including1536340 full-resolution RAW-chain phase checks, failed RAW
publication and sequence wrap. Unsupported odd/zero geometry stays idle.
Canonical/generated module hashes and25 verification log references are in
`background_timing_fix_receipt.json`; all319 baseline and130 protected hashes
remain intact. Post-change full PDS rebuild has started; timing improvement is
not yet established. Bitstream generation script now supports the isolated
background target and retains passing-timing/source-hash pre/post gates.

Background bitstream generation completed rc0 in1084.05s:3,791,112 bytes,
SHA256 `6d430d6c3e257b65a04b22ff35ee0270a86b15aa6f12c6e46559c57597314ae6`.
Post-generation timing passes, timing hash unchanged, source hashes intact.
`program_fpga.py --background` now selects the corresponding image/build receipts,
checks identity and refuses any active device owner; unsolicited production
pkill was removed from the programmer. Deployment preflight could not connect:
SSH timed out and two pings received no response. Thus no viewer was stopped,
no SRAM programming started and current live state is unknown. On reconnect
inspect bootID/device ownership, gracefully retire only a known running viewer,
then program and run parity. SPI Flash remains unchanged.

User restored connectivity; new bootID72f3c4f2-b195-4a84-845a-dbec252ef729
and no endpoint/device owner confirmed a post-reboot recovery state. Background
candidate then programmed into SRAM successfully/done1, PCIe0755:0755 and
pango_zc binding restored. Evidence: six_background_program.log and manifest.
Camera1–4/two-bank80-frame hardware parity with snapshot checks has started
via run_six_parity.py --background --snapshots. No pixel/performance pass is
claimed until complete evidence returns. SPI Flash remains untouched.

First background hardware parity attempt fails atC1/bank0/sample0 with bounded
fresh RAW/background alignment failure, before any accepted pixel comparison.
No exact pixel result is claimed. Tool safely released its device; follow-up
fuser shows no owner and kernel has no DMA/quarantine error. Diagnostic counters
are being added to distinguish absent valid publication from RAW sequence
advancement during disable/drain/claim. A RAW-only background-viewer15-second
health smoke is running with graceful RAW restoration; no B performance test
is started before correctness is established.

RAW-only background candidate health smoke completed15.098s, C1–4 acceptance
passed. Graceful batch RAW PID2807 restored and its health checks verify fresh
capture/zero accepted-camera errors/ongoing RKNN. Evidence lives in
`six_background_display_measurement` (A-only smoke, not a formal ABAB or B
performance measurement). The background same-sequence matching diagnosis
continues; restored RAW health does not establish autonomous thumbnail parity.

ARM64 diagnostic build passed selftests/compatibility compiles; hardware run
`background_alignment_diagnostic_1791554267708741900` returned2. All16 attempts
had fresh stable background publication but failed exact RAW sequence matching:
no_fresh_publication0/frozen_not_fresh0/raw_sequence_mismatch16/exception0.
Example thumbnail29317 versus frozen RAW29319, then29320 versus29322.
Thus absence of thumbnail publication is excluded for these attempts; sequencing
between disable/drain and RAW claim is under investigation. No pixel comparison
or performance acceptance follows from this diagnostic. RAW PID4133 restored;
subsequent live log confirms have111111, C1–4 capture27/9/25/25fps, all errors0,
RKNN completion4/s in the sampled window. These are health observations, not
a formal before/after measurement. Host-only freeze-before-disable sequencing
is being reviewed against RAW/producer RTL without loosening exact-match guards.

User reports Cam2 image issue/low FPS. Live RAW log confirms C2 delivered14.17–
14.24fps versus other cameras about25–28fps before a later all-camera CPU-load
slowdown; C2 observed tag-advance19.56–19.58/s versus earlier RAW A logs about45/s.
DMA payload time remains1.09–1.14ms, unstable0/errors0. These counters cannot
exclude image corruption or capture regression; prior '>1fps/zero errors'
health smoke was too weak to establish preservation of Camera2 throughput.
Background RAW smoke itself already showed C2 delivered11.90–18.76fps.
Cause remains unproven. `check_cam2_rollback.py` preserves current RAW logs,
gracefully retires only the recognized RAW viewer, verifies original rollback
image hash, programs batch SRAM and runs30s RAW A smoke/restoration to test
whether the regression follows FPGA image. No new background deployment or
performance acceptance proceeds while Camera2 preservation is unresolved.

Requested original production version restored: verified original FPGA archive
fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122
and viewer73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100
(before-latency-fix-20261008 backup). Previous active viewer preserved; SRAM
only, SPI unchanged. PID8257. Evidence restore_display30_1791555503108808000:
95s observation,19 capture samples/camera, mean delivered C1/2/3/4/5/6 FPS
38.57/42.47/25.67/25.70/39.06/39.19, unstable0/pane error maxima all0,
RKNN3.965 completions/s. C1 minimum5-second rate25.34fps; no every-window30fps
guarantee or optical latency claim. Original display defaults verified:
update_idle_ms0/texture_ring1/publish_min_ms24/hud_stats_ms1000.
Background candidate tests paused per user restoration request.

User authorizes a new inference-only FPGA RGB888 before/after experiment with
RGB565 display retained. Board preflight observed a new bootID
644568c5-2252-4240-87b0-d0810cbc4131, absent PCIe endpoint/driver/viewer, and an
externally changed active viewer hash99e3be09…; no attribution is established.
Original display30 archive/viewer pair restored after reboot before benchmarking.
Fresh baseline `restore_display30_1791560767926101900`:95s/19 capture samples
per camera, mean C1/2/3/4/5/6=44.60/44.84/25.74/25.74/40.33/40.36fps,
unstable0 and RKNN3.844 completions/s. Standalone alternating same-frame tests
are being prepared for conversion-only conventional inputs_set and conversion
plus DMA-BUF to distinguish the two effects. Standalone V8 stage throughput
must not be reported as live MVP viewer FPS; full viewer integration is separate.
Trial orchestration must use graceful UI exit for the production binary rather
than interrupting in-flight DMA with SIGTERM, retain exact parity/owner guards,
and restore the documented production SRAM/viewer pair after the experiment.

New inference-only RGB888 trial completed: rgb888_trial_1791561582715191600.
Both conventional and DMA-BUF240-pair runs pass exact input/native-output
parity. Borrowed coherent-RX inputs_set throughput25.640→20.155/s (-21.391%),
inputs_set0.720→11.379ms; not beneficial. DMA-BUF stage24.850→25.149/s
(+1.204%), process CPU14.002→6.183ms (-55.839%). FPGA conversion+RGB transfer
10.231ms roughly equals CPU RAWcopy+conversion10.384ms, limiting wall gain.
Original SRAM/viewer restored, PID5650 verified;95s restoration means C1/2/5/6
41.92/43.17/39.38/39.48fps and RKNN3.905/s. Paint/swap means34.04/35.02fps
are below baseline38.62/41.03 though configured85% health threshold passes;
equal display performance is not claimed. See RGB888_TRIAL_RESULT.md for scope
and measured submission/transport limitations. No live viewer FPGA input was
enabled by this standalone test; original active production pair is retained.

Background hardware parity utility is now ARM64-built with warnings-as-errors,
pure target selftests and all three legacy session caller compatibility checks
passing. `background_thumbnail_parity_build_manifest.json` records the current
background protocol/RTL identities and executable SHA256
`2bc8681dac77364f82021ddb8fb7635d05b952b5778d8d54b36741a6c1528f75`.
It has not opened the hardware. Future acceptance requires80 fresh exact
RAW-sequence-matched comparisons across C1–4 and both background banks;
bounded alignment failure must be reported rather than comparing nearby frames.

Seed3 retry finished rc0 with unchanged source hashes but still failed timing:
placement DDR-0.386ns and cmos2-0.275ns, plus free_clk hold-0.121ns.
Audit showed the background clone already inherited gplace_seed3 from the batch
project, so this retry duplicated its prior configuration rather than exploring
a different placement. Seed4 is now running with identical RTL and constraints;
both failed runs and their backups remain preserved. No deployment is authorized
by tool rc0 without passing placement and detailed timing reports.

Seed4 closes background timing: placement and independent detailed report both
state All Constraints Met; detailed report contains zero violated paths.
Slow DDR setup is0.195ns placement/0.135ns detailed and detailed fast hold0.029ns,
so margin is positive but limited. Source hashes remain unchanged. The seed4
receipt is adopted into six_background_pds_manifest.json, preserving the prior
failed receipt separately. Background bitstream generation is now running with
source/timing checks before and after generation; SRAM deployment remains pending.

Registered-tap full rebuild finished rc0 in1360.26s with source hashes intact,
but timing still fails. Placement slow DDR WNS improves from-0.517 to-0.386ns,
TNS-0.617ns across3 endpoints; cmos2_pclk now has WNS-0.275ns/TNS-0.276ns
across2 endpoints. cmos1_pclk margin is only0.003ns in this placement. A new
detailed report is running to identify remaining paths before further closure.
No corrected candidate bitstream is generated or programmed on this evidence.

See ACCEPTANCE.md for requirement coverage. No final improvement is claimed
until clean timing and live six-camera acceptance are recorded.
