# Executed hardware acceleration experiments

The active goal is not complete. These are isolated experiments, not accepted
six-camera inference/video rates. The model, full 640x480 source, gray114
640x640 input, stereo configuration and restoration copies remain preserved.

## Persistent FP32 output allocation

Receipt: `runs/rknn_experiment_b9e50337984a4575bbddf6f4b4fca9b0/receipt.json`.
Report: its `artifacts/results/report.json`.

All four pinned fixtures passed full float-array certification and exact FP32
detection tuple checks, including the retained bright fixture's two detections.
Sixteen paired AB/BA rounds completed 50 timed inferences per profile, 800 per
profile in total, with no failures. Baseline arithmetic mean of per-run FPS was
29.124; preallocated outputs were 29.049. Median paired FPS ratio was 1.000440,
range 0.964941..1.024800. Persistent FP32 allocation has no demonstrated gain.
Input preprocessing, camera acquisition, display and stereo were outside these
windows. The current HDMI viewer was normally closed and restored successfully.

Actual runtime is RKNN 2.3.0, NPU driver0.9.8, library SHA256
`73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`.
There is one input and four outputs. Native query9 box tensors use NC1HWC2 with
C2=8. Classification tensors logically have 3 channels, but query9 reports
C1=2/C2=8, and query11 reports 8 NHWC channels. The initial adapter rejects this
additional padding. A revised, bounded adapter needs real output parity before
any native-output acceleration claim.

The revised padded-channel adapter compiled in private build
`5725cc96e8b746eeb55ca1a41058b075`. Experiment
`892e53bcaad44f23bcb0c617dd6c77dd` failed its first NC1HWC2 certification:
baseline produced the retained2 detection tuples; native produced0 detections
on all3 completions. All logical FP32 snapshots are retained locally. No
performance comparison was accepted, and the current HDMI viewer was restored.
Native memory binding, synchronization and layout correctness are under
investigation. Attempts to use query11 were rejected before execution because
another compiler/parity process appeared; both attempts preserved/restored the
viewer. Competing processes were not terminated.

After a stable idle preflight, query11 experiment
`71d108400c43406381ff66fb55cf1490` also failed its first historical detection
certification and restored the viewer. Both layouts require further diagnosis;
accepting either layout from its metadata or local arithmetic tests would be
incorrect. The parent supervisor now downloads raw FP32 snapshots and private
native-byte diagnostics, checks interference before closure, and defers the
probe while another compiler/parity task is active.

Direct full-native-I/O diagnostic
`4ad952c78e814a14b87784e51ec250de` did write all outputs and reproduced2 close
detections. The output-only profiles' box arrays were all zero; their class
arrays were the value obtained by dequantizing zero. This runtime therefore
needs a bound native input as well as bound native outputs for this candidate.
One diagnostic completion does not certify that behavior across models.

The full-I/O diagnostic still differed from baseline FP32 tuples. Independent
Python IEEE-binary16 checks compared all536,000 logical values. Rounding each
dequantized result to half did not match. Rounding only the queried scale to
binary16, then multiplying the integer `(q-zp)` in FP32 matched every baseline
value exactly. This single-fixture observation is pinned by raw snapshot hashes
in `artifacts/independent_half_scale_check.json`; it supports an explicit scale
policy experiment, not a general runtime rule. Exact arrays and tuples remain
required over all fixtures before timing is accepted.

The explicit FP16-scale native-I/O path passed the actual four-fixture gates in
`rknn_experiment_f39aaaf111014a1fb8ac5e6542fe8e21`: every certification array,
every detection tuple, and the first/last timed arrays matched baseline within
the unchanged rules. Sixteen paired rounds completed800 inferences per profile
with zero failures. Mean per-run FPS was29.037 baseline versus28.242 native;
median paired ratio0.968684 (range0.951655..1.017851). Scalar deblocking and
dequantization costs negate the avoided output-get call. This correct version
does not establish acceleration and will not be accepted as a faster viewer.
An AArch64 SIMD implementation of the same conversion is the next experiment.

NEON build `52a7160ffcb1429590d9728d8238b01f` and experiment
`0266179cb55d488f9b1bde85c96b17e5` passed all four certification fixtures and
all retained timed arrays **bit for bit** (max absolute difference0); exact
detection tuples matched. Each profile completed800 timed runs without failure.
Mean per-run FPS was29.01193 baseline versus29.68186 native; paired median
ratio1.021677 (range0.971170..1.070043). Conversion averaged3.654ms, replacing
baseline float-output retrieval5.733ms, while native input copy+sync averaged
2.025ms against legacy input-set1.054ms. The independent probe indicates a small
gain with overlapping round distributions, not accepted live six-camera gain.
Viewer restoration was verified. The frozen viewer helper and cumulative
acceptance path are being compiled and will be checked separately.

Viewer bundle `65a02d87142e090416db84bf` compiled in build
`68a954a146d54d54accfed377d56d8bd`, executable SHA256
`ed49b9ed1ff2ee1918b9fdf6d13f513ebc93758fcb08ca13bf657267405f1d7c`.
The visual, camera-DMA and DFL selftests passed. Actual helper parity experiment
`565bab03996340108b8e9b36d49ca5c5` compared12 completions over4 fixtures:
6,432,000 logical values were finite and bit-identical to legacy. It executed
the exact frozen `HardwareInference` input/output binding and full-frame CPU
preprocessor; the decoder remains byte-identical by the preparation audit.
That helper probe does not time a live viewer. HDMI restoration was verified.
The first matched legacy six-camera/stereo trial is now running with cumulative
acceptance counters and a lightweight observer.

First legacy viewer trial `f2236d646bcb4a1d904d58897cbf449b` completed and
restored HDMI. Post-warmup cumulative endpoints span131.245524seconds:
1,592 successful inferences, zero failures,12.129937/s. Per-camera fresh swap
rates were24.527/24.481/21.875/22.005/24.976/24.923fps; complete delivered
camera pixels were43.217/43.224/25.723/25.723/50.242/50.013fps. These are
distinct measurements and demonstrate why delivery alone cannot meet the
40/30 fresh-display target. Requested pixel payload in this interval totals
19,203,072,000bytes; tag/trailing metadata requests are counted separately.
This is requested DMA payload, not total DDR bandwidth. Observer CPU was
4.785955seconds during the150-second observation; it is lighter, not zero-cost.
The native profile is now running in the same executable/configuration.

First native trial `bc45576e21194aedae2eb87ccef09cc3` covered136.584072seconds
with1,718 successful inferences and zero failures:12.578333/s, ratio1.036966
against the first legacy interval. Actual fresh swaps were
24.849/24.725/22.074/22.060/25.076/25.113fps; delivered pixels were
43.087/43.072/25.728/25.713/49.420/49.779fps. Both trials bind the same
executable, argv, calibration/stereo assets and environment digest
`2bd9bfe21ff63afe8f7ec177339147baf1875d0320ea176788d46ace54114645`.
Requested pixel bytes are19,870,924,800 across that longer interval; compare
request rates rather than unequal-window byte totals. Observer CPU was4.456367s.
HDMI restoration passed. This one pair is positive; repeated reverse-order
measurement is required before retaining the gain as stable evidence.

Reverse-order native attempt `52195d8615cb4897b71a489fec7ba63c` was rejected
before measurement because the monitor included a default-model initialization
log preceding selection of the pinned model. It is excluded from FPS evidence;
restoration passed. The monitor now follows logs from the first pinned-model
binding onwards and continues to reject later model changes, fallback and
unavailable states. Fifteen local supervisor/proof/startup regression checks
passed. Repeated native trial `33275e114ad1494694c74c5fd34e5e68` then covered
136.422974seconds,1,729 successes, zero failures,12.673818/s. Its matched
legacy reverse-order control is running. All successful trial raw logs are
downloaded through the privileged reader with size/hash verification.

Reverse-order legacy control `2900789574294b0490b053a23e8b5917` covered
131.702689seconds with1,586 completions and zero failures:12.042275/s.
The second native/legacy ratio was1.052444. Across the two opposite-order pairs,
the median observed ratio is1.044705; both pairs improved. All four measured
intervals retain continuous successful five-second stereo records for the pinned
C1/C2 pair, spanning their complete accepted counter endpoints with zero stereo
failures. The strengthened acceptance also rejects missing, stale, idle or failed
stereo windows for every configured pair. Twenty local checks passed.

`runs/viewer_abba_neon_stereo_verified.json` holds the matched endpoints, deltas,
stereo windows and request rates. Pixel request rates were146.314/145.485MB/s
for the first legacy/native pair and146.035/145.359MB/s for the second; this
does not prove DMA reduction and does not include total DDR traffic. The live
scene was not instrumented as a fixed fixture, and four trials do not establish
statistical significance. The consistent observed gain belongs to the full
native NPU I/O path plus CPU NEON conversion; the FPGA bit and model were not
changed during these trials. Fresh Qt-swap rates remain around22..25fps, so
the40/30 six-camera display target is still unmet. All four trials and the
excluded startup attempt restored the saved HDMI process and configuration.

The `native_io_single_copy` probe is prepared with local optimized/sanitizer
checks and strict input-layout/buffer guards. Inspection of the frozen viewer
helper shows that `writeInput` already performs one full memcpy per frame and
that its gray fill happens only during setup. The new probe therefore isolates
redundant writes in the earlier independent `native_io` benchmark, aligning it
more closely with the viewer. Any measured delta is software-copy attribution;
it is not an extra live-viewer change or gain to add to the4.47% observed above.
New prepared manifest: `401bdab0769a38a4cb2b0d8c4767d8c5a9d0e5d2bf96ebdfad08eddb3b30d1df`.

Single-copy target build `4bc48205e42742118589c5ca82336f77` and experiment
`0a2ca7a3216b431e8aa8b216d98461c9` succeeded and preserved/restored HDMI.
Eight certifications (legacy versus candidate/control across four fixtures)
and sixteen timing pairs retained exact detection tuples and bitwise-identical
float arrays with max_abs=0. Full input-copy hashes match. Each timed path
completed800 inferences with zero failures. Original native and single-copy
mean rates were29.723897 and29.756542/s; paired median ratio1.013862,
range0.956737..1.040392. Mean input write cost fell1.74106->1.22738ms; input
sync was0.32977->0.37088ms, conversion3.64558->3.77985ms and NPU run
24.00451->24.11891ms. Timing variation overlaps the small total gain. This
measures a probe difference already present in the viewer, not extra live gain.

Private DMA module build `3ffc96a5052c414ba81224a97f6159cd` completed using
the actual6.1.99 generated headers, Module.symvers and582 retained compiler
dependency hashes. Module SHA256 is
`15383dc7d0b87fe1e3d15ddc350cd74e220408f129583f296ab980735ff75b16`;
vermagic is `6.1.99 SMP mod_unload aarch64`. Target GCC12.2 differs from the
kernel's GCC10.3.1; the build warning is retained. Compilation does not establish
runtime compatibility or equality to the original module.29 deterministic
lifecycle model cases and the executed shared C range/UNMAP predicates passed
in WSL (`dma_export/host-executed-validation.json`). The module was downloaded
and hash-checked but never loaded. The original HDMI identity was preserved.
The candidate returns EOPNOTSUPP for export/lease until drain and importer
completion evidence exists; no FPGA-to-RGA copying or speedup is claimed.

RGA same-format heap experiment `dd71e4cc135c4be7a62a1d198bbd3e8a` passed
all12 changing correctness frames (7,372,800 checked bytes) and100 paired
cached-heap copies, with124 real RGA completions including warmups. The full
RGB565640x480 snapshot matched every byte; sources remained unchanged and
snapshot guards passed. Persistent FD imports and synchronous copies work on
this target's RGA2 Enhanced, API1.10.1. Mean full RGA-to-owned-CPU-snapshot
time was1.253847ms, thread CPU0.588335ms: device copy0.900475ms, destination
START_READ0.037632ms, snapshot memcpy0.259401ms, END_READ0.033423ms.
Cached CPU copying averaged0.317750ms. This is heap calibration, not an
uncached PCIe comparison or a live inference gain. FPGA slot importing and
its drain/lease lifecycle remain unverified. HDMI restoration passed with
PID135312/starttime23753980 and the original executable hash.
Independent source/receipt review reproduced the stage means and verified all
12 correctness frames,100 pairs, source preservation, snapshot guards and
actual runtime/header binding; no P1/P2 was found in that narrow heap-copy review.
This review does not certify the future PCIe exporter or importer backend.

Independent review excludes the first compiled DMA prototype from deployment:
enabled legacy ioctl usercopy can invert the mmap lock, and its64-bit coherent
allocation mask conflicts with its32-bit command encoding. Dormant mapping/cache
and export-core lock-ordering issues were also found. Revision is in progress;
the loaded original module is preserved, export stays disabled, and a successful
build/model test is not treated as a kernel or hardware correctness proof.

The importer candidate's local validation receipt is
`rknn_io/validation/fd_import_03/receipt.json`; its prepared manifest is
`40d16a705f4e60a17e3a2e0a454d88aca78d1701dcbcd0007a9251b19742ead9`.
The fixed runtime has the required exported importer/bind/sync symbols
(`rknn_import_symbols_readonly.json`), but ownership and NPU support await the
fresh target build/probe. New runs retain complete frozen source packages and
root-owned artifact manifests, require downloaded size/hash agreement for all
backends, and mark artifact-download failures as failed evidence. Archived
earlier runs retain their original supervisor behavior and receipts.

FD-import build `c0c79feaa9604c2ebc52f23a5209cba8` passed;26 artifacts were
downloaded with exact size/hash agreement. Experiment
`49b3adc489d74eb596fc8b393e3ec23b` declined before any candidate inference:
first output binding succeeded, all tensor attributes and descriptor ownership
fields stayed unchanged, but the runtime resolved phys_addr from
`ffffffffffffffff` to `ffa80000`. The strict setup metadata check rejected that
resolution. The unused ownership probe and allocated output both passed CPU
sync, import destruction, context destruction, FD/mapping retention and final
owned cleanup.42 artifacts were hash-verified; HDMI restored PID136782,
starttime24241761. No parity or performance is established. A revised gate
will permit only this initial unresolved-to-resolved device address assignment
while retaining strict post-binding metadata stability and every other field.

The revised DMA source passed independent follow-up review of the five prior
findings. Parent WSL execution initially rejected unused stub parameters under
-Werror; these were explicitly marked unused without changing the fail-closed
behavior.37 model tests and both executed C harnesses then passed, and fresh
kernel compilation is running. Neither review nor tests lift export/backend
gates or establish PCIe drain/RGA reuse correctness.

Repaired DMA target build `61732b056e0a4cc0af87a7d0378d4fbc` completed with
582 retained kernel dependency hashes and26 size/hash-verified artifacts.
Module SHA256 is
`3b60a6619bf036c83c86435867149a0ae8528bd45f178c484077d2c4d4eaa3dd`;
vermagic remains `6.1.99 SMP mod_unload aarch64`. The only retained build
warning is GCC12.2 versus kernel GCC10.3.1. Current frozen manifest is
`57b6cfc5331775bff7b010f26fccb68debab26b3a2b70c3f3a549402cfaec1e3`.
The module was not loaded; HDMI PID136782/starttime24241761 was preserved.

The imported-memory review found a P1 after failed rknn_run: bound imports
were destroyed while device execution remained uncertain. The first declined
hardware experiment attempted no candidate inference and did not exercise this
branch. Revision must keep bindings/context/external buffers and the runtime
loaded until process teardown, reject any certification of that retirement,
and never resume/fallback within that probe. Two misplaced supervisor tests
were restored to NativeProofTests; all23 supervisor/proof/coverage/artifact
tests now pass. Prior local lifecycle checks do not cover the corrected branch.

Automatic tool review rejected the PCIe completion simulation subtask before
execution for a possible cybersecurity risk. No simulation evidence exists.
Parent recomputation did verify the six recorded frozen PCIe source hashes and
recovery bit SHA256 `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`.
This is source/bit record binding, not a proof of the vendor-core final-payload
and MSI ordering or fresh verification of the physically loaded image.

The failed-run retirement fix passed local SDK/Qt compilation, ASan/UBSan
lifecycle checks and proof gates in `rknn_io/validation/fd_retirement_01`.
All nine recorded source hashes match the current files. Uncertain run or failed
context destruction retains the runtime and resources until process exit; JSON
uses null return codes for skipped calls and the runner halts without timing or
certification. Parent supervision now checks each candidate's retirement logs
before restoring HDMI: missing/incomplete/deferred/failed retirement holds both
restoration and the shared board lock. Normal retirement still restores HDMI.
All26 local supervisor/proof/stereo/artifact checks pass, including both prior
misplaced tests and three restoration-guard cases. Fresh prepared manifest is
`59c21cc8d2bbad6fe03b3f207e98a27f6a0b551e4c8aef59a6b142e15adf86bf`;
target rebuilding is in progress.

DMA design-note updates re-froze the offline handoff as
`32fd28aee9e67f20b87b349eebb0eafdda1418f9512d9cb9fd9abfd12309a612`
with28 hashes. This documentation-only refresh leaves the six kernel build
source inputs unchanged. The compiled `61732...` module still binds its earlier
freeze and complete archived source; no new kernel/runtime evidence is implied.

Frozen byte-level source inspection is retained in
`pcie_completion/SOURCE_TRACE.md`. Actual controller wiring uses
`~fpga_tx_done` from FIFO read-count completion (`ips2l_pcie_dma.v:337`),
rather than the packet generator's busy output. FIFO read-count completion and
the buffered PCIe output are distinct boundaries. This is a specific unresolved
completion contract, not a reproduced target failure or an executed simulation.
The two additional inspected FIFO/wrapper files matched their archived input
manifest hashes; no active/frozen RTL was changed.

Follow-up review found that the first restoration guard accepted a normal
ownership-probe retirement without requiring inference-session retirement if
the process was interrupted. The guard now requires a terminal JSON record and
retirement coverage for each started ownership domain, with duplicate/missing
coverage rejected. New source emits a session-start event before allocation;
memory-purpose events also identify domains in earlier retained logs. Both
probe-only interruption regressions pass, bringing parent checks to28. The
in-flight `596a...` benchmark remains frozen at its original bytes; its full
logs require the corrected coverage audit before further board work.

FD-import experiment `2807eda6137340f3b3d82d364747ea5a` completed using frozen
target build `596a40954b4947f2ac5191a63436ffae`, executable SHA256
`448963bc1699bb5322effdef58fdd6a2aa90575578910f2211831f6da64c3f80`.
`target_report_manifest_verified.json` matches the emitted artifact size/hash;
download and checking of all641 raw artifacts is still running. This report
records four legacy/candidate and four legacy/control certifications, exact
tuples/bitwise arrays and max_abs=0, then16 timing pairs with800 completions
per profile and zero failures. Mean single-copy/FD rates are29.790579 and
29.805678/s; median ratio1.000776, range0.955681..1.046933. No gain is established.
Mean input write1.246315->1.303381ms, input sync0.346004->0.103424ms,
output sync0.188423->0.706156ms, conversion3.769184->3.683120ms and NPU run
24.171816->23.944541ms. Different sync costs and timing variation largely offset.
The scope is NPU allocator and CPU memory/synchronization; FPGA and live-viewer
acceleration are not established by this isolated probe.

The current corrected guard was run read-only against all20 actual candidate
logs and passed (`current_retirement_guard_audit.json`). Each ownership and
inference session retired normally and each file ended with terminal evidence;
the partial-log review finding was not exercised in this run. Explicit session
start logging subsequently compiled locally and passed marker-aware runner
checks in `validation/fd_session_marker_01`. Fresh prepared manifest is
`ccf9bc0a15ae1cc606352e7e1fd0ffd01106aec0c1291dd4077abc024505f492`;
these later marker bytes are not covered by the earlier target build.

The `2807...` download subsequently completed: all641 artifacts matched size
and SHA256. `audit_fd_import_experiment.py` independently re-read400 unique
finite FP32 arrays and60,032,000 reported comparison values against each first
reference, with bitwise equality/max_abs=0 and exact detection tuples. It also
rechecked strict certificates,800 completions per path and all20 candidate
retirement logs. Evidence is `downloaded_array_audit.json`; report SHA256 is
`7e038ff9c8f37ee90b6f0437e50eb452265a9cfe0fb1442079b475f18ce16d64`.
The original HDMI was restored with PID139571/starttime24603902 and its pinned
executable hash. This establishes compatibility on these fixtures and this
runtime; the small variable timing difference does not establish allocator
acceleration, so FD import is not selected for viewer integration.
A subsequent privileged read-only inspection confirmed that restored PID and
starttime, original argv/executable hash, and the unchanged loaded driver Build
ID `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`
(`restored_identity_readonly.json`). The board lock was released by the normal
verified restoration flow; no module or FPGA switch occurred.

## RGA full-frame conversion and letterbox

Receipt: `runs/rga_experiment_b1040db3ebb545fd9274ab8eea40d6e8/receipt.json`.
Native evidence: `artifacts/results/fd.jsonl` and `receipt.json`.

The actual RGA format mapping matches the retained CPU pixels with
`RK_FORMAT_BGR_565`, followed by bit replication. `RK_FORMAT_RGB_565` swaps red
and blue. Without correction, BGR565 expansion differs by up to 7/3/7 in RGB;
using it directly changes model input. An exhaustive 65,536-color calibration
identified the correction, and corrected outputs match the independent oracle
byte-for-byte. Eighteen corrected six-fixture/path SHA checks passed; all 36
direct/corrected outputs and their exactness are retained in the board receipt.

500 timed frames, after30 warmups, ran for each fixture/backend/path. The table
is the arithmetic mean of recorded per-fixture means, in milliseconds. Costs
include source copy, dma-buf cache synchronization, synchronous RGA execution
and correction; all corrected timed frames were checked for exact output.

| Path | Wall ms | Thread CPU ms |
|---|---:|---:|
| CPU full RGB conversion | 0.544 | 0.542 |
| Corrected RGA full RGB conversion | 1.743 | 1.072 |
| CPU viewer conversion + letterbox | 0.870 | 0.868 |
| CPU fused conversion + letterbox | 0.545 | 0.544 |
| Corrected RGA direct letterbox | 1.780 | 1.106 |
| Corrected RGA conversion + ROI copy | 2.521 | 1.217 |

These synchronous RGA paths are slower and consume more thread CPU while
preserving exact input. They will not be integrated as an acceleration benefit.
The current viewer was restored successfully. RKNN detection parity was not
executed for RGA; exact full model-input bytes were verified instead.

## Stall diagnosis

The first paired diagnostic measured120.638 seconds, restored the HDMI viewer
and did not reproduce second-scale stalls. Fully contained windows recorded
96,509 completed ioctls, zero failures and maximum ioctl wall19.582ms.
Observer CPU54.446seconds makes this sample unsuitable as a throughput
acceptance baseline. The lighter observer retains boundary hashes and samples
full process identity plus executable inode metadata, with10-second global
owner/interference guards. Its21 local tests passed. Trace overruns in the first
run leave the scheduler cause unknown.

The second run `diagnostic_c75ef0dc93454eea8081b51727ec3b39` completed a precise
120.000245-second observation and verified restoration. Complete contained
windows recorded107,810 ioctls with zero application failures; no severe stall
was reproduced. Per-camera delivered rates over complete contained windows
were40.649/40.776/25.712/25.723/48.647/48.309fps. Coverage is110.1..115.1 seconds
per camera; these are delivered frames, not per-camera new paints or accepted
120-second target results. Mean successful copy cost remained6.369ms thread CPU,
8.870ms wall. Mean conversion CPU was2.217ms. The observer cost fell from54.446
to18.307 CPU seconds within the observation, still material for a throughput
baseline. Trace was disabled in the second run; scheduling attribution remains
unverified. Raw artifacts and bounded analysis are retained under `host_stall/runs`.

## Inference scheduling constraint

The retained calibration source reserves one pending inference in
`VisionPipeline::request`, then runs `stereoWork` synchronously in the same
worker. A completed inference stores/wakes a reply, but only the worker loop
consumes it and clears the reservation. Existing logs pair9completedfps with
42.97ms latest service time and nine stereo computations averaging276.83ms
over a five-second window; pending rejections were207 and interval rejections0.
These logs support stereo coupling but do not reconstruct an exact cycle time.

The retained source also queues request and completion callbacks through the
GUI. The optimized `swap/src` already uses direct thread-safe handoffs, while
stereo remains synchronous in the scheduler worker. Its valid motion minimum
interval can also limit requests when motion gating is enabled. Wakeable200ms
and20ms waits are idle timeouts, not evidence of forced polling delays. No
scheduler or stereo change is counted as a hardware acceleration benefit.
Any accepted candidate must keep the same motion/stereo policy and full-frame
input, and show a successful completion gain in matched120-second windows.
