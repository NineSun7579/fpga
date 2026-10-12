# Motion-aware full-frame inference scheduling

`host/src` is an isolated copy of `project/performance_100h/direct_ingress/src`.
The candidate target is `detview` in an isolated, hash-pinned build directory. This implementation changes
host scheduling only; it does not change RTL, bitstreams, running processes or
deployment. The parent session owns target build and board verification.

Enable explicitly with `--motion-gating` or `DETVIEW_MOTION_GATING=1`. Otherwise
there are no motion register accesses and the original scheduling applies.
`--motion-refresh-ms 100..500` defaults to 250 ms between total submissions.
Tracking caps this at 250 ms, retaining four-model round-robin refresh in about
one second when frames, controller and inference are available. This is a
scheduling interval, not a guarantee that slow inference completes on time.
The motion-enabled detection minimum must be 100..250 ms; motion and tracking
urgency never bypass it. Nontracking static scenes default to 250 ms total
submissions too. Existing controller reservation, per-frame duplicate gate,
decoder worker, model rotation, tracking age and bounded frame mailbox remain.

All six camera paths, video decoding and inference use complete RAW images.
No image DMA is skipped because of motion; there is no crop/ROI DMA or cropped
model input. CAM5/6, video, lane, unavailable metadata and invalid/stale records
retain the existing scheduling behavior (nontracking/lane are controller paced).

## ABI and acquisition

The reader follows `project/motion_100h/host/camview/motion_abi.h`,
`project/motion_100h/MOTION.md`, and
`project/DOC/FPGA_RK3568_传输协议_v1.md`. Opt-in first polls probe magic
`0x4d4f5431` and 640x480 geometry. Each record uses one capture selector write,
generation before/after, ten separate word selections/reads under the same
`PangoDev::dmaMutex_`. All transfers are 16 bytes, with the little-endian value
in bytes 0..3. The full selector TX packet is zeroed. Motion TX/RX scratch
`0x3fe000` is separate from camera tag scratch `0x3ff000` and six image slots.
No register burst is assumed.

Only the currently selected analytics camera among CAM1–4 polls, from its
capture worker, at most once per 100 ms from completion. The GUI does not poll.
Busy DMA causes an unavailable hint for that packet rather than waiting for a
lock. A 250 ms total budget covers the ABI probe and entire capture and is
checked before and after every ioctl. Each call arms the inherited SIGALRM
mechanism to the remaining time, split into timer seconds and microseconds.
This is a watchdog target, not a hard realtime or display latency limit: a
driver that does not return on the signal can exceed it. Probe read, capture,
validation, I/O and budget failures mark the hint failed, fall back to full-frame
scheduling, and retry from one second after completion with a fresh ABI probe.
Only a successfully read mismatched magic or geometry permanently disables
optional metadata for the process. Successful polls retain the 100 ms completion
gap. Metadata errors neither increment nor reset camera failure/restart
accounting. The watchdog remains process-wide, as in the baseline, with DMA
serialized by its mutex. No performance improvement or display bound is claimed.

## Conservative hints and missed events

`VisionFrame::motion` contains the frozen record, host observation time, host
time of the last observed source-sequence advance, source generation and the
observed-motion hold deadline. Neither timestamp is an FPGA exposure time.
The record is the latest source-frame hint: its sequence is **not** bound to
the DDR tag or the image carried by `VisionFrame`. Bitmap/bbox never select a
crop or claim exact association.

Static deferral requires reference valid, no error or reserved-bit violation,
both host ages <=300 ms, an observed advancing source sequence in the current
generation, zero bitmap/block count, and invalid bbox. All 192 bitmap bits are
validated against popcount and, for motion, the exact enclosing bbox. `samples`
counts **changed** points, not processed points: it must be <=19200, with at
least eight changed points per marked block. Zero-block samples=1 or 15 remain
valid static hints; samples=19200 is not a required condition.

Unsigned monotonic sequence wrap is accepted. Sequence gaps are counted and
do not disable gating: 100 ms polling naturally skips source frames. Backward
or half-range sequence jumps cause fallback until a later forward advance;
repeated frozen sequences cannot renew sequence freshness. Source generation
changes clear observation/hold state, and pipeline configuration changes clear
request/history state. Unsupported sources always fall back.

An initial valid positive record or a valid positive record with forward source
sequence advance holds the trigger for 500 ms. Duplicate positive snapshots
cannot renew or restart that deadline. The initial record still requires a
later observed sequence advance before it can authorize a fresh hint. Frozen
positive records fall back once sequence age exceeds 300 ms even if the original
hold deadline has not expired. The hold survives later static
records and mailbox replacement. This covers observed events, **not every
source event**: motion can occur and disappear between 100 ms polls. Bounded
periodic full-frame refresh is the deliberate mitigation for missed transient
motion and stationary objects. A stalled worker beyond the hold interval may
also lose the observed trigger; periodic refresh still applies. Motion cannot
override the detection minimum or an outstanding controller request.

## Counters and validation

`[motion-traffic]` logs cumulative polls, attempted I/O operations, completed
DMA bytes, errors, skipped source sequence numbers and sequence resets every
five seconds while selected-camera packets arrive. It also reports
`captureduration_last_us`, `captureduration_max_us` (probe plus capture, including
failed attempts), `max_ioctl_us` (including failed calls), `sequence_changed`
(successful captures whose sequence differs from the previous observation in
the same source generation), and `last_generation` (last successful FPGA capture
generation). Completed DMA bytes include successful ioctl returns even when the
elapsed budget subsequently rejects the record. A full capture is 23
transactions / 368 bytes; first capture adds two probe reads / 32 bytes.
`[motion-scheduling]` logs distinct static-deferred frame decisions and accepted
completed replies attributed to motion, fallback or periodic request reasons.
Failed/cancelled/expired requests are not completed counts. Static deferrals
are scheduling decisions and are not a claim of dropped display frames.
These counters describe reduced work; they do not imply higher inference FPS.

Standalone local policy tests use Qt Core/Gui and require no OpenCV, hardware,
RKNN, RGA or display server:

```sh
mkdir -p /tmp/motion-policy-build
cd /tmp/motion-policy-build
qmake /absolute/path/project/motion_scheduling/host/src/motion_policy_selftest.pro
make -j2
./motion_policy_selftest
```

The Qt test carries real `VisionFrame` identities through static/motion/stale
sequence scenarios, motion overwritten by static metadata, invalid flags and
all-word bbox/count validation, camera/video/lane fallback, generation and
sequence resets/wrap, minimum intervals, four-model periodic coverage and all
23 frozen-capture I/O failure points, torn generation and unsupported selectors.
`vision_pipeline_selftest.cpp` additionally exercises the actual Qt worker and
mailbox with static deferral, overwritten motion, full-frame requests and
source/camera/lane reconfiguration. The existing vision/decoder/tracker tests
remain, and `--vision-selftest` now includes the policy test. Run the policy test
alone in the full candidate with `--motion-policy-selftest`.

Local Windows validation uses Qt 6.11.1 and MinGW 13.1, release C++17 with
`-Wall -Wextra`, in `C:/tmp/motion-policy-build`. Full Linux/RKNN/RGA/OpenCV
candidate compilation and the actual-worker suite are deferred to the parent
session's target build; no target-build success is claimed here.

Verified result: `MOTION_POLICY_SELFTEST_PASS checks=84 failures=0`.
The release build produced no compiler warnings. Byte comparison to the copied
baseline found no missing files; existing changes are limited to `detview.pro`,
`main.cpp`, `vision_types.h`, `vision_pipeline.cpp` and
`vision_pipeline_selftest.cpp`. The tracker, decoder/inference preprocessing,
camera DMA helpers and stereo implementation are byte-identical to baseline.

The 250 ms watchdog/retry update in `PangoDev::motionHint` has received source
checks only. Its timer, ioctl durations and retry behavior require the parent's
target build and observation; the pure policy tests do not exercise that method.
No build or SSH was run for this update during the ongoing target observation.

Historical local SHA256 evidence (before the watchdog/retry update; the
`main.cpp` hash below does not identify the updated source):

| Artifact | SHA256 |
|---|---|
| `host/src/motion_policy.h` | `b82ae3b1ec4b5b95f376d77448e347eb1a6913b1229ccd04991c9aedefd8ac27` |
| `host/src/main.cpp` | `4d9516cfd78fe83ebc0d573f37749f0f74514b8fd8ba6bb62707a5946894d2fa` |
| `host/src/vision_pipeline.cpp` | `71fdc28e2449b2c6a399e30cfc1c9906820cbbb65a99f2feef2004a36444b99a` |
| `host/src/motion_policy_selftest.cpp` | `587e7031a3472dd30826730ea8b914eefdff121ae83b1195ff3e2f6921ed2b96` |
| `C:/tmp/motion-policy-build/release/motion_policy_selftest.exe` | `7c5547593f503b2115ac2d3f56ba23a244e455d8cae60833c78b5b9070bc15d3` |
