# FPGA and RK3568 inference acceleration

Active objective: implement hardware acceleration across FPGA and RK3568 and
increase RK3568 completed inference FPS. Six complete video streams, full-frame
model inputs, correct detections, stereo and a restorable board configuration
remain required.

## Evidence before implementation

The frozen e896 host runs the pinned wb_v4_combo RKNN model, SHA256
`21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`.
Its full RGB565 camera input is 640x480. RGB888 inference input is 640x640,
with the complete image at y=80 and gray114 padding. No crop or model change
is implied by this goal. The deployed motion FPGA does not enable its older
YOLO NPU. Its motion metadata currently schedules RK3568 inference.

Historical e896 samples report NPU run 32.91 ms, input set 2.15 ms, float-output
retrieval 8.71 ms and decode 1.36 ms. These samples prioritize experiments;
they are not a current matched baseline or a measured acceleration benefit.

The stalled calibration executable and later HDMI viewer are different builds.
Successful-only frame DMA means omit 10-22 second alarm-failed attempts.
`per_camera_fps/host_stall/IOCTL_STALL_ANALYSIS.md` retains the raw evidence.
The private paired wall/CPU diagnostic has completed two recoverable observations.

## Current work

1. Retain immutable diagnostic build and passed on-board selftests; diagnose
   recurrent stalls with paired thread CPU/wall and all-attempt accounting when
   reproduced. Two observations did not reproduce severe stalls.
2. Probe persistent and native RKNN I/O with runtime-reported tensor layouts,
   allocation sizes, quantization and strides. Verify output/detection parity
   before integrating a supported path into the viewer.
3. Retain exhaustive RGA color and full-fixture correctness evidence. Measured
   exact RGA conversion plus letterboxing is slower than the CPU path, so this
   path is excluded from integration. Separately assess hardware copying from
   the existing FPGA DMA buffer to eliminate measured CPU uncached-memory cost.
4. Select the first supported accelerator with verified correctness and actual
   end-to-end gains. Retain FPGA raw acquisition/DMA and motion functionality;
   additional FPGA offload requires explicit format and frame identity evidence.
5. Compare successful inference completions in matching monotonic windows of
   at least 120 seconds, with the same model, scheduling, stereo and scene.
   Record fresh video rates per camera, failed attempts and DMA request bytes.

No speedup or completed objective is claimed at preparation time. Runtime
receipts must bind executable, source, model, input fixtures and dependencies.

## Executed evidence

- The paired diagnostic built as `0e25307aa770116c`, executable SHA256
  `946bcb0dc3b7740ad8bb4e7db2da510573f4d019de99ca264635625622a656ba`.
  Target vision, camera-DMA, DFL and standalone paired-clock selftests passed.
- Diagnostic run `2e4827f490df481989f912c82469e6fc` measured 120.638 seconds
  and restored the original HDMI viewer. Completed-only diagnostic windows
  strictly contained in the observation include 96,509 ioctls, zero application
  failures and a maximum ioctl wall time of 19.582 ms. Severe second-scale
  stalls were not reproduced. The full candidate log includes startup/shutdown
  and must not be presented as exactly the 120-second observation.
- Observer thread CPU increased by 54.446 seconds over this observation.
  Repeated full binary hashes and global proc scans make this an intrusive
   diagnostic sample, unsuitable as a throughput acceptance baseline. A lighter
   sampler with full boundary checks and explicit guard cadence has completed
   a second observation; measured observer CPU was still18.307seconds.
- RKNN probe target build `9006950aff2846a8a3d606117bf82375` succeeded without
  changing the viewer. Complete source, SDK, compiler dependencies, object,
  runtime and executable bindings are recorded under `runs/`.
  Current runtime library SHA256:
  `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`.
- Native tensor adapter arithmetic and unsupported-layout/buffer-bound checks
  passed using WSL g++17. These do not establish hardware compatibility.
- Isolated persistent-FP32 comparison passed output/detection parity but showed
  no demonstrated gain (paired FPS median ratio1.00044). Exact corrected RGA
  letterboxing likewise passed byte checks but took1.780ms vs CPU0.870ms.
  Detailed receipts and limitations are indexed in `RESULTS.md`.
- Revised native adapter supports runtime-reported channel padding and passed
  local bounds/sanitizer checks. Initial NC1HWC2 hardware parity failed: the
  retained bright fixture had2 detections with baseline and0 with native.
  Performance runs stopped immediately, and viewer restoration was verified.
  That output-only path is excluded. Full native I/O correctness subsequently
   passed as described below; an isolated viewer integration still defaults to
   legacy. Its exact helper has now passed the hardware check described below.

- Full native I/O with explicit FP16-rounded scales subsequently passed the
  four-fixture hardware gates in experiment `f39aaaf111014a1fb8ac5e6542fe8e21`.
  Sixteen pairs completed800 real inferences per profile with zero failures,
  but scalar conversion yielded median FPS ratio0.968684. This version is
  correct on those fixtures and does not establish acceleration. A guarded
   AArch64 SIMD conversion subsequently passed guarded scalar-reference checks,
   actual four-fixture bitwise parity and an independent median ratio1.021677.
    Subsequent six-camera observations are recorded below.
- The isolated viewer recipe adds opt-in cumulative acceptance snapshots with
  bounded atomic-read endpoints. It counts six-camera fresh swaps/deliveries,
  successful/failed model runs, and all-attempt full-frame/tag DMA requests.
  The same frozen executable will run legacy/native modes with original stereo
  assets; actual helper parity, immutable build receipts and120-second bounded
   endpoints are required before evaluating live gain.
- Viewer `ed49b9ed1ff2ee19...` compiled with three passed target selftests.
  Exact frozen helper comparison checked6,432,000 floats bitwise over four
  fixtures and12 completions. First legacy acceptance measured12.129937
  successful inferences/s over131.245524seconds with all six streams/stereo.
  Two opposite-order pairs now report native12.578333/12.673818 versus
  legacy12.129937/12.042275 per second: median ratio1.044705. All four windows
  exceed120seconds with continuous stereo successes. This is observed live
  native-NPU I/O plus NEON gain, with natural scene variation remaining.
  Per-camera fresh swaps remain below40/30; DMA request reduction is unproven.
- The isolated single-copy experiment changes only the redundant probe input write:
  one exact1,228,800-byte copy per frame instead of a whole-buffer gray fill
  followed by copying all640 complete rows. Original native I/O remains the
  timing reference; float arrays and exact tuples still certify against legacy.
  The live `HardwareInference::writeInput` already uses one full memcpy each
  frame; its gray fill occurs only at setup. This candidate aligns the probe
  with that viewer behavior and attributes the probe's redundant write cost.
  It does not provide an additional viewer optimization or additive gain.
  Actual experiment `0a2ca7a3216b431e8aa8b216d98461c9` passed four-fixture input,
  bitwise output and exact tuple checks; each profile completed800 inferences
  without failures. Input writes averaged1.74106 versus1.22738ms, but average
  throughput was29.72390 versus29.75654/s and paired ratios varied0.95674..1.04039.
  This is software-copy attribution, separately from unchanged FPGA/NPU execution.
- DMA exporter candidate `pango_dma_candidate` privately compiled against the
  actual generated6.1.99 headers and582 compiler-bound dependencies in build
  `3ffc96a5052c414ba81224a97f6159cd`.29 lifecycle model cases and executed C
  policies passed. Export stays disabled: PCIe drain, safe slot reuse and RGA
  completion remain unproved. The loaded driver and HDMI process were preserved.
- Next allocator candidate keeps all native bindings and one complete copy per
  frame, replacing only five persistent tensor allocations with dedicated
  `/dev/dma_heap/system` FD imports. Compare it to `native_io_single_copy`;
  certify against legacy and verify separate DMA-BUF and RKNN cache-sync calls.
  Import support, ownership and speed remain hardware questions.
  Candidate local SDK/Qt compilation, sanitizer lifecycle tests and proof-gate
  checks passed. New prepared manifest is
  `40d16a705f4e60a17e3a2e0a454d88aca78d1701dcbcd0007a9251b19742ead9`;
  target build `c0c79feaa9604c2ebc52f23a5209cba8` succeeded. Experiment
  `49b3adc489d74eb596fc8b393e3ec23b` declined before candidate inference when
  the runtime resolved an initially unknown device address during binding.
  The setup policy now allows only that initial resolution; subsequent fields
  remain fixed. A review also found unsafe import retirement after failed run;
  that path is being revised to retain bindings/context/FDs/maps until process
  teardown. The corrected local SDK build, sanitizer/lifecycle and proof-gate
  checks passed (`validation/fd_retirement_01`). New prepared manifest
  `59c21cc8d2bbad6fe03b3f207e98a27f6a0b551e4c8aef59a6b142e15adf86bf`
  is now in fresh target build. Supervisor restoration requires normal retirement
  evidence from every candidate run; unresolved/missing evidence holds the
  shared board lock.26 local supervisor/proof/coverage/artifact checks pass.
  Target build `596a40954b4947f2ac5191a63436ffae` subsequently succeeded.
  Hardware experiment `2807eda6137340f3b3d82d364747ea5a` completed and restored
  HDMI. Its manifest-verified target report has eight baseline certifications
  and16 bitwise timing pairs,800 completions per timing profile and zero failures.
  Mean29.79058 versus29.80568/s and median ratio1.000776 do not establish gain;
  all641 raw artifacts have now passed downloaded size/hash checks. Independent
  audit rechecked400 unique finite arrays,60,032,000 compared output values,
  exact tuples and all20 retirement logs. No allocator gain is established;
  FD import is not selected for live integration.
  Follow-up guard fixes require terminal records and retirement coverage for
  every ownership domain. A read-only audit of all20 actual candidate logs using
  the corrected guard passed.28 parent regression checks now pass. New explicit
  session-start logging compiled locally; prepared manifest
  `ccf9bc0a15ae1cc606352e7e1fd0ffd01106aec0c1291dd4077abc024505f492`
  differs from the hardware-tested manifest only as recorded in the new freeze;
  future deployment requires a fresh build for those source bytes.
- Same-format RGA heap calibration `dd71e4cc135c4be7a62a1d198bbd3e8a` passed
  12 complete changing-frame byte comparisons and100 paired copies. Full
  RGA-to-CPU-owned snapshot cost1.253847ms versus0.317750ms cached CPU copy.
  This demonstrates target heap-import/copy correctness; no PCIe buffer was
  imported and no live-viewer change was made. Export lifecycle is still required.
- The DMA prototype's reviewed locking/address/mapping issues have been revised
  behind the unchanged export gate.37 model cases and both local C harnesses
  passed after a parent -Werror stub-parameter fix. Current freeze manifest is
  `57b6cfc5331775bff7b010f26fccb68debab26b3a2b70c3f3a549402cfaec1e3`.
  Fresh target build `61732b056e0a4cc0af87a7d0378d4fbc` succeeded; all26 retained
  artifacts were size/hash checked and HDMI identity remained unchanged. The
  prior five findings were resolved in follow-up source review. Export and
  importer-backend gates remain closed; runtime/drain proof is outstanding.
  Updating the bound design notes produced documentation-only freeze
  `32fd28aee9e67f20b87b349eebb0eafdda1418f9512d9cb9fd9abfd12309a612`;
  kernel build inputs remain unchanged and the original build receipt is retained.
- The local PCIe completion simulation subtask was rejected by automatic tool
  review before execution. It produced no test evidence. Six frozen source
  hashes and the recovery bit hash were independently recomputed, which binds
  source records but does not establish final-payload/MSI ordering.

## Stereo scheduling candidate

The accepted frozen viewer calls stereoWork synchronously in the scheduler.
Inference completion wakes that thread but leaves the single reservation until
its next iteration; a230-240ms stereo call can delay the next NPU request. The
existing stereo interval is250ms after computation completes, so start spacing
is approximately480-490ms. This cadence must remain unchanged.

Prepare a distinct opt-in candidate in `viewer/stereo_async_candidate` with one
dedicated stereo worker, owned paired frames and bounded job/result storage.
Keep engine/calibration ownership in that worker, carry epoch/generation/pair/
capture identities, reject stale associations and join safely on shutdown.
Preserve pair selection/fairness, depth/freshness checks and stereo parameters.
The same new executable must support synchronous/asynchronous stereo for paired
tests; full inference helper/inputs and six video paths remain unchanged. This
is a scheduling improvement, separately attributed from NPU allocator and
FPGA/RGA gains. Actual build/review/parity and120-second six-camera windows are
required before use. Local initiative capture failed because memory is offline.
