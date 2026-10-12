# Isolated viewer native RKNN I/O candidate

This directory owns the local integration recipe and helper only. It does not
edit `per_camera_fps/swap/src`, the shared `rknn_io` implementation, FPGA RTL,
the board configuration, or the running viewer. No source bundle is frozen
automatically. The parent invokes preparation after its source/adapter edits.

Native I/O is experimental and exact hardware parity is unverified. The parent
reports that run `4ad952c78e814a14b87784e51ec250de` returned all-zero bound
outputs with legacy `rknn_inputs_set`, while the full `native_io` diagnostic on
the same binary returned two detections close to baseline. The measured runtime
requires both bound input and bound outputs. Output-only activation is disabled.
The parent must confirm current shared-adapter/raw-output and exact decoder
parity on the same NPU fixtures before enabling full native viewer I/O.

The helper explicitly selects `NativePlan::DequantScale::Fp16` once at setup
for the pinned model, and declines other SDK API/driver versions than `2.3.0` /
`0.9.8`. The shared adapter rounds the scale to binary16 once and builds its
byte lookup table; the dequantized product remains binary32. The parent's
`rknn_io/validation/scale_policy_validation.json` records exact reconstruction
of 536000 archived float values and two decoder tuples on one fixture. That is
archived arithmetic evidence; the new four-fixture hardware test remains the
parent's responsibility. No certification environment variable is added.

`DETVIEW_RKNN_IO` selects:

| Value | Input | Output |
|---|---|---|
| unset / `legacy` | Existing `rknn_inputs_set` | Existing float outputs/get/release |
| `native` | Persistent UINT8 NHWC input, explicit device sync | Persistent native buffers, sync, logical FP32 conversion |

`native_output` is an unsupported request and falls back to legacy with reason
`native_output_only_not_certified_target_runtime`. It creates no candidate
context, native allocation, binding or sync. The helper also rejects a direct
output-only request before setup, preserving the legacy context.

Any unknown value falls back to legacy. Native requests also fall back for
unknown model bytes, lane models, class counts other than three, the existing
`DET_INT8_IN` input experiment, unsupported tensor metadata, unavailable SDK
symbols, or failed allocation/binding/setup sync. The model gate checks SHA256
`21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`
and all four queried raw-DFL logical outputs (two scales). Multi-model rotation
still visits every selected model; only this eligible model can use native I/O.

The helper queries native output attributes using retained SDK command 9. The
shared `NativePlan` controls padded channel capacity, strides, bounds, types,
deblocking and dequantization. It is copied at preparation time, not pinned to
an intermediate version. Optional memory APIs are resolved from the same
runtime library as the linked `rknn_init`. `rknn_create_mem2` requests cacheable
memory when available; otherwise the helper uses `rknn_create_mem` with explicit
sync. Missing required native capabilities leave legacy usable.

Setup creates a separate RKNN context from the same resident model bytes and
validates every output before binding both input and outputs. Failure destroys its buffers before its
context, leaving the original legacy context untouched. Successful setup swaps
contexts and retires the original once. A failed native frame is counted as a
failure, retires the native context, and recreates/validates legacy for subsequent
frames. No failed frame is rerun or counted as a successful completion.

The input remains the complete CPU letterbox: RGB888 640x480 at y=80, gray114
padding to 640x640. The driver binding uses `type=UINT8`, `fmt=NHWC`,
`pass_through=0`, `h_stride=640`, 1228800 bytes; it never subtracts 128. Native outputs expose
persistent `rknn_output` FP32 descriptors to the byte-identical decoder, and
never call `rknn_outputs_release`. Existing stage statistics use their current
double wall times; `set` includes native input copy/sync and `get` includes
native output sync/conversion. Setup costs remain outside per-frame timings.

Each model load emits `[rknn-io]` with the requested/actual mode, model hash,
reason, `status=experimental` when enabled and `hardware_parity=unverified`.
It does not claim successful inference or detection correctness from setup.

Optional matched-run acceptance instrumentation:

Set `DETVIEW_ACCEPTANCE=1` on both profiles. It emits one `[acceptance]` JSON
snapshot at startup and at most once per five seconds, independent of
`DETVIEW_PERF`. All counts are cumulative within the PID/monotonic-start epoch;
existing five-second diagnostic counters and their resets remain separate.
Decimal strings preserve exact 64-bit counters/timestamps in JSON.

| Field | Counted event |
|---|---|
| `completed` / `failed` | The model's `runOnce` result, immediately before native fallback; no-model pending attempts count as failed |
| `delivered[6]` | Complete stable camera pixels committed to the capture mailbox |
| `per_camera_paints[6]` | That camera's new allocated texture was drawn, then Qt emitted `frameSwapped` |
| `paint_new_frames` | Swap callbacks containing at least one newly painted camera frame |
| `dma_frame_requests[6]` | Every full-frame DMA attempt, before ioctl, including failed/unstable attempts |
| `dma_request_bytes[6]` | Requested full-frame bytes including the 16-byte trailing tag; 614416 per attempt |
| `dma_payload_request_bytes[6]` | Pixel payload requested; 614400 per full-frame attempt |
| `dma_tag_request_bytes[6]` | Separate ping/pong tag-read requests, including failures; excludes motion/control traffic |

Capture supplies a per-camera cumulative delivery ID paired with the pixels
under its existing mutex. Each texture slot receives that ID only on upload.
The draw stages its actual uploaded ID; a swap counts it once. Repeated HUD,
exposure, settings, old-texture and duplicate swap callbacks do not add fresh
camera paints. Unseen deliveries/texture uploads do not count as paints. IDs
remain unique over source/model changes. Qt's swap callback measures GPU
submission after `swapBuffers` returns; it does not verify HDMI scanout or GL
execution correctness, and performs no added flush/finish/readback.

The snapshot brackets independent atomic counter reads with `sample_begin_ns`
and `sample_end_ns`. Its counts are exact at those reads, with the explicitly
recorded sampling span; it does not claim an instantaneous cross-thread cut.
Take two endpoints from the same epoch after warmup with
`last.sample_begin_ns - first.sample_end_ns >= 120000000000`. Subtract their
cumulative totals, including all six camera arrays. No alignment with separate
capture/inference/display five-second windows is needed.

For optional file access, set `DETVIEW_ACCEPTANCE_DIR` to a fresh absolute
private directory whose parent already exists. This also enables snapshots.
The viewer creates it mode 0700, or accepts an existing owned non-symlink 0700
directory, then atomically replaces one 0600 `snapshot.json` file every five
seconds. It never handles trigger files or signals. The bounded raw log remains
the record of all snapshots; a bad/unwritable directory falls back to log only.

The local summary utility enforces endpoint bounds and a single counter epoch:

```powershell
python project/hardware_acceleration/viewer/acceptance_summary.py candidate.log --first 3 --last 28
```

It reports exact cumulative deltas, duration/rate bounds and per-camera fresh
paint/delivery rates. The parent selects equivalent stable scene/configuration
intervals and supplies binary/model/runtime receipts. Run long enough to retain
two post-warmup snapshots separated by at least 120 seconds after sampling
uncertainty, rather than assuming a 120-second process lifetime gives that span.

Local audit without freezing source:

```powershell
python project/hardware_acceleration/viewer/prepare.py --audit-only
```

Local compiled mock checks and actual patched-worker Qt syntax check:

```powershell
wsl --exec python3 /mnt/c/Users/NineSun/Desktop/ov56401/project/hardware_acceleration/viewer/local_tests/run.py
```

These checks cover output-only rejection with continued legacy operation, the
target runtime/FP16 policy gate,
context/buffer destruction order, partial setup rollback, missing native symbols,
optional allocator fallback, persistent descriptors, unchanged input bytes and
sync failure handling, repeated/settings/old paint identity handling, concurrent
acceptance counters and private atomic files. They do not execute an NPU or
duplicate the shared adapter's layout selftests. The full viewer still needs
the parent's RK3568 build with the existing Qt/OpenCV/RGA/runtime dependencies.

After the parent's edits are complete, freeze the complete source tree:

```powershell
python project/hardware_acceleration/viewer/prepare.py --source project/per_camera_fps/swap/src
python project/hardware_acceleration/viewer/prepare.py --verify project/hardware_acceleration/viewer/prepared/<bundle-id>
```

The returned bundle contains complete `frozen/src` and `candidate/src` trees,
retained SDK copies, `main.patch`, `audit.json`, and a manifest binding all
source bytes. Inverting the explicitly allowed native/acceptance patches must
reproduce the entire original `main.cpp`. Acceptance patches only add counters,
paired delivery IDs and bounded reporting at their event sites. Decoder and
input-preparation slice hashes are checked; all other original source files,
including RGB565 conversion, motion policy/ABI and stereo files, are identical.
The `.pro` changes only append helper headers, SDK include paths and `-ldl`.
No existing bundle is overwritten; preparation rejects concurrent source edits.

For the parent to build later, create a `build` directory inside the transferred
bundle, run the following from that directory on the target, and record the
binary, model and runtime/dependency receipts:

```sh
qmake ../candidate/src/detview.pro
make -j2
```

The same candidate executable defaults to legacy and accepts full `native`
as an explicit experimental mode. The parent controls deployment, restoration, identical viewer
configuration and at least 120-second matching completed-inference windows
with all six video streams, stereo and FPGA motion metadata. No hardware test,
deployment, throughput increase or parity certification is claimed here.
