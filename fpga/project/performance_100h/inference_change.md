# Isolated inference candidate implementation review

Scope: `candidate/detview/src` was first copied in full from `baseline/detview/src` with Python `shutil.copytree`. Baseline and production sources were not edited. Final SHA-256 verification matched all 22 entries in the captured baseline manifest. No SSH, hardware, vendor tools, or board performance measurements were used for this implementation.

## Preprocessing change

The actual baseline controller `inferenceRequested` handler allocated a 640x640 RGB888 image, filled every pixel with 114, then copied 480 rows at offset 80. It now submits the owned raw `VisionFrame.image`. The existing queued GUI connections, source-generation/pause checks, request-rate increment, pending mailbox, model rotation, and completion-rate accounting remain in place.

After dequeue, the inference worker validates and prepares input before `runOnce`. `InferencePreprocessor` owns one lazily allocated 640x640 RGB888 image, fills it once, and copies exactly 1920 bytes from each source scanline on each 640x480 request. No image copy is exposed to another thread, so mutable access does not detach the reusable buffer. Padding is never overwritten. Tight and strided 640x640 RGB888 submissions bypass the letterbox buffer; `runOnce` retains the packed copy fallback for strided model images and the separate experimental INT8 conversion buffer. That buffer is allocated only if needed. A square-to-camera transition therefore cannot leave stale square pixels in padding.

Null images, dimensions other than 640x480 or 640x640, non-RGB888 formats, and undersized row strides fail before row access. Every dequeued malformed request emits `inferenceFailed` with its original source generation and frame id, including null submissions that the baseline silently ignored. External QImage backing-memory lifetime/length remains the caller's normal QImage contract; the API cannot discover a falsely declared allocation length.

All `InferenceThread::submit` callers were inspected: the controller, and the initial/repeated submissions in `--rotate-selftest`. File-loaded rotation-test images now explicitly convert to RGB888, preserving ordinary file-format support under the worker's strict pixel contract. There are no other submit callers in the captured source tree.

RKNN input remains raw RGB channel order, NHWC UINT8 with pass-through left at its baseline zero value. `DET_INT8_IN` retains byte subtraction by 128 in separate packed storage, so it cannot mutate constant padding in the RGB image. Detector/lane decoding and output-attribute queries are unchanged. Per-model output-attribute caching is intentionally deferred; this candidate focuses on preprocessing rather than broadening model initialization/error behavior.

`DET_BENCH` adds `preprocessing_ms` to each successful `[tdm_bench]` record. It includes worker letterboxing/validation (and the initial allocation on the first raw request), plus existing input packing/INT8 preparation time. Existing `ms` still measures RKNN set/run/get/query/decode/release; completed FPS still counts successful completions per elapsed wall-clock time. Moving CPU work can affect measured throughput, but does not redefine the metric.

## Independent history change

`vision_pipeline.cpp` now computes history grayscale and deep tracker snapshots only for `options.tracking && !active.lane`. `DET_EAGER_HISTORY=1` restores the baseline eager grayscale/snapshot work independently of the inference change. Options are fixed at construction; lane/camera/model/generation reconfiguration advances the epoch and clears history/trackers in `reset`. Late replies are rejected by epoch, and `acceptReply` returns before grayscale/snapshot use when tracking is disabled or lane mode is active.

All history grayscale consumers are tracker update/correction/replay. Stereo still calls `gray(left)` and `gray(right)` independently inside `computeStereo`; its frame pairing, cadence, and ROI/depth rules are unchanged. Frame identity, timestamps, and bounded history are still retained in no-tracking/lane modes for reply matching. The captured initial board log includes stereo pair work and roughly 15 completed inferences/sec in its first stats window; this is context only, not a candidate performance claim. The parent's stated no-tracking mode motivates avoiding unnecessary history conversion.

## Verification evidence and limits

The standalone `inference_preprocess_selftest.pro` needs only Qt Core/Gui and C++17. It was built and executed on Windows using `C:/Qt/Tools/mingw1310_64/bin/g++.exe` (GCC 13.1.0) and `C:/Qt/6.11.1/mingw_64/bin/qmake.exe` (Qt 6.11.1), release flags `-O2 -Wall -Wextra`. Result:

```
PREPROCESS_SELFTEST_PASS: baseline bytes, reuse, padding, stride, square transitions, malformed inputs
```

The reference is the exact captured controller fill-and-row-copy algorithm. Tests compare all 1,228,800 output bytes across 12 different frames, alternate tight/padded source strides, check constant border rows and unchanged storage address, interleave tight/strided square inputs, and reject null, wrong sizes/formats, and short strides. This demonstrates host byte parity, not RKNN execution parity or a target application build. Qt 5.15.2 qmake was also found in Anaconda, but it requires MSVC; the executed test used the available matching MinGW/Qt 6 toolchain.

Existing vision self-tests cover no-tracking replies, stale generations, lane failures/unthrottled scheduling, tracking replay, and stereo. The lane/stereo case now also switches lane -> tracking -> lane and verifies correction with fresh tracking history. These application self-tests were **not executed locally**: neither the checked Anaconda nor Qt SDK include paths provides OpenCV C++ headers, and this Windows host is not the application's Linux/RKNN/RGA toolchain. No target build is claimed.

Local reproduction (from `candidate/detview/preprocess-test-build`, with Qt/MinGW bin directories on PATH):

```
qmake ../src/inference_preprocess_selftest.pro
mingw32-make -j2
release/inference_preprocess_selftest.exe
```

## Target validation requirements

Build the isolated candidate with the deployed RK3568 Linux Qt toolchain, C++17, Qt Core/Gui/Widgets, OpenCV 4 development files/pkg-config (`core`, `imgproc`, `calib3d`), matching `rknn_api.h`/`librknnrt`, and RGA headers (`rga/im2d.h`, `rga/rga.h`)/`librga`. The full application also includes Linux PCIe DMA/ioctl/mmap and monotonic-clock APIs. Use an out-of-source qmake build of `src/detview.pro`; no production overwrite is required.

Run the standalone preprocessing test under the deployed Qt version, then application `--vision-selftest`, `--dfl-selftest`, `--lane-selftest`, and the existing tracker self-test. Repeat `--vision-selftest` with `DET_EAGER_HISTORY=1`. Exercise `--rotate-selftest` with an ordinary 640x480 and a 640x640 file to confirm caller format normalization/model rotation. Check default UINT8 and optional `DET_INT8_IN` input parity on target, rapid pause/source/model/lane changes, and matching failure identities. With `DET_BENCH=1`, compare preprocessing/service time and existing request/started/completed/failed rates; compare history optimization separately with `DET_EAGER_HISTORY=1`. Parent agents own board baseline/performance and DDR evaluation.
