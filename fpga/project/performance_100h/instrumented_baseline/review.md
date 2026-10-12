# Instrumented original pipeline baseline

Source-only instrumentation of `../baseline/detview/src`, copied after verifying all 22 files against `../baseline/detview/source_sha256.json`. Only `src/main.cpp` differs: **52 added / 14 removed lines**, with LF line endings retained. All other 21 files, including `detview.pro`, all five selftest sources, and stereo sources, remain byte-identical. No SSH, build, deployment, or production mutation was performed. Runtime equivalence and the three-way performance comparison still require the parent's builds and measurements.

## Pins

The complete 22-file baseline pin set is the existing `../baseline/detview/source_sha256.json`; its SHA-256 is `44eb83c1b1678eede465aa28c9d5451bcdea54258cc99a00543c2ee35190bd52`. This binds every copied file, including files below `stereo_demo/`, rather than just main.cpp.

- Original main.cpp: `6477821f639f2f7f878b90d4e4782ff469833dce0a0de91a86deb8749e45d941`.
- Instrumented main.cpp: `8266300d23d3d1403a41958c62666e5cd828a5fb4eeabed0a78cc48e37a9fb28`.
- Every other source file retains its hash in that pinned manifest. No extra candidate headers or selftests were imported.

## Diff review

| Original main.cpp region | Instrumentation change |
| --- | --- |
| 365–380, `cameraRead` | Add a caller-owned `transferBytes` output initialized to zero. Split the two short-circuited tag reads into the same ordered operations; add 16 only after each successful tag read. Add `op.total_length` only after successful frame ioctl. |
| 523–534, capture audit setup | Add four integer counters and candidate's `reportCapture(bool force)` implementation. `maximum_fps` is literal zero, matching the original unpaced pipeline. |
| 534, capture loop | Check the five-second reporting window before polling; report even when reads return no new frame, unstable frame, or error. |
| 546–566, capture resume/read | Reset traffic counters on resume; collect bytes after each cameraRead, count polls, successful frame DMAs (results 1 and 2), and read errors. Original sleeps and branches remain. |
| 605–614, old capture log | Move the existing capture audit into the shared reporter, guarding per-frame averages when no frames were delivered. |
| 617, capture exit | Force a final partial report when measuring. Suspension also forces a partial report before disabling measurement. |
| 1187, inference setup | Initialize monotonic window start and successful/failed counters. |
| 1253–1263, inference execution | Keep the original runOnce arguments and processing; save its bool result and count success or failure. Non-null frames without a loaded model count as failed, matching candidate semantics. |
| 1264, inference report | Copy the current output_cache `[infer-perf]` reporting block exactly: elapsed milliseconds / 1000, completed / elapsed seconds, reset after each elapsed window of at least 5000 ms. |

Full unified diff can be reviewed locally with:

```text
git diff --no-index -- ../baseline/detview/src/main.cpp src/main.cpp
```

The return value of runOnce defines completed inference, including the original postprocessing/result publication path. There is no inference final-partial report, matching the current candidate counter. Idle inference windows are reported after the original 200 ms condition wait; long calls can extend windows beyond five seconds. Use the logged timestamps and actual seconds rather than assuming exactly five seconds per row.

## Capture metric semantics

The candidate's payload accounting, counter definitions, timestamped log format, five-second window test, suspension/resumption, and final-report behavior are retained. Pacing-related state, clock reads, environment parsing, and waits were excluded entirely.

`dma_bytes` counts only successful camera-path F2H ioctl payload lengths. A successful first tag followed by a failed second tag contributes 16 bytes; two successful tags followed by a failed frame contributes 32. No-new-frame polls contribute 32; successful frame DMA contributes another 614416 bytes (640 x 480 x 2 + 16), even if the post-read tag is unstable. Thus an ordinary successful capture contributes 614448 bytes. Failed ioctl requested lengths are excluded. These are payload bytes, not PCIe wire overhead, and exclude unrelated register, model, and stereo-demo reads. `polls` counts cameraRead calls, including failed calls; `frame_dmas` counts successful full-frame reads; `delivered_frames` counts stable delivered frames.

Stalls that return from ioctl still produce reports. A blocking ioctl can defer reporting until it returns, as in the candidate. The original six-failure hard `_exit(3)` recovery remains; that path can lose the current partial window. Ordinary worker stop and suspension flush partial windows. No background reporter or recovery changes were added.

## Instrumentation cost

Inference adds one initial monotonic clock read, one monotonic read per loop (including idle loops), one success/failure integer increment per attempted inference, and one stderr fprintf approximately every five seconds: 0.2 additional log lines/s.

Capture adds one monotonic read per active loop, up to three payload additions per read, a polls increment, a bytes accumulation, and conditional frame/error increments. Successful-loop reporting replaces the old post-delivery clock check with the loop-top check; no clock is added inside frame DMA timing. Each active camera emits one existing `[capture]` line and one new `[capture-traffic]` line per approximately five seconds. For N active cameras this adds N/5 traffic lines/s; with inference, six cameras add 1.4 lines/s, one camera adds 0.4 lines/s. Suspension/stop adds partial-window lines, and stalled cameras now emit the existing capture line as well. No pixel-sized allocation, copy, lock, ioctl, or deliberate delay is added by instrumentation.

Reporting and counters have nonzero CPU/stdio cost. The added frame-byte increment is included in the existing DMA timer, and counter updates are included in the existing read timer. Wall-clock overhead in microseconds or throughput impact has not been measured; it must be checked on the target with identical logging/configuration across the three sources.

## Static validation performed

- Verified every original file against the complete pinned manifest before copying; compared all copied file hashes afterward, finding only main.cpp changed.
- Verified the entire source from the original `bool runOnce(` through EOF is byte-identical. This covers inference pixel processing/postprocessing, display, UI request scheduling, and selftest entry paths.
- Verified the full CameraThread through inference setup region, RGB565 conversion helper, and original monotonicMs helper are byte-identical.
- Verified the ordered `msleep`, `usleep`, `sleep`, and `m_cond.wait` call expressions are identical across original and instrumented main.cpp.
- Verified the inference reporting block is byte-identical to current `output_cache/src/main.cpp`.
- Confirmed absence of `CapturePacing`, `InferencePreprocessor`, `frameStartedNs`, and `DETVIEW_CAPTURE_MAX_FPS` in the instrumented source.

**Shared time helper change: none.** The original CLOCK_MONOTONIC millisecond implementation remains verbatim. Its timestamps are equivalent to the candidate's nanoseconds-divided-by-one-million helper at millisecond resolution.

Builds, selftest execution, and exact baseline/candidate/output_cache runtime verification remain pending for the parent session; the static checks above do not establish measured performance.
