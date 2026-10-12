# Current detview baseline

Fresh read-only collection lasted **320.902 seconds**, exceeding the requested 120 seconds. `runtime_120s.json` contains the exact newly appended segment, SHA-256, process checkpoints, source hashes, and toolchain discovery output. The filename denotes the minimum requested duration.

PID **42262**, starttime **11900709**, and executable SHA-256 `dbbe29cf09c2954df421f9d826f61040e8efaa22d35b2845b7a134038719eada` match the restore receipt at start, intermediate checkpoint, and end. The same process starttime and continuing metrics support continuity throughout collection. Checkpoints do not constitute continuous scheduling traces.

Source log: `/userdata/linaro/detview-calibration-session/detview.log.restore-e023736cc5604fa09c1a447335b9311e`. Collected byte range **[1826246, 2123794)**, 297548 bytes, same device/inode (45832/265060). Source CLOCK_MONOTONIC range **[120970.258047671, 121291.160038646]** seconds. Only bytes appended after the start offset are preserved. A single explicit wait was 20 seconds; other elapsed time was read-only discovery and analysis. No hardware changes, process switches, vendor launches, builds, or tests were performed.

## Display

Use 62 complete `[display-perf]` windows within the collection timestamps, covering **313.896 seconds**, monotonic milliseconds **[120974041, 121287937]**. Exclude the first boundary-straddling window. The summed exact `[display-events] new_paints` count is **7135**, yielding **22.73046 fresh paints/s**. Duration weighting the rounded logged `new_paint_fps` yields 22.73148, agreeing within rounding. These are fresh composite paints, not the sum of camera FPS.

| Upload accounting | Bytes/s | Decimal MB/s |
|---|---:|---:|
| `display-perf upload_bytes` (HUD only) | 8170289.17 | 8.170 |
| All six `display-upload` camera textures | 80301674.44 | 80.302 |
| Combined | 88471963.61 | 88.472 |

`main.cpp:1948` maps `upload_bytes` to `hudUploadBytes`; camera texture accounting is separate at line 1964. Treating the former as all texture traffic would substantially undercount.

## Capture

Each camera has 64 newly appended `[capture]` records. Values below are arithmetic means of the logged approximately five-second aggregate samples; logs do not expose their exact durations or underlying frame counts. The first sample can include work preceding the start offset. They are descriptive sampled means, not exact duration/frame-weighted interval measurements.

| Camera | Delivered FPS | Copy ms | Frame DMA ms |
|---|---:|---:|---:|
| 1 | 43.771 | 8.357 | 1.277 |
| 2 | 43.758 | 8.501 | 1.309 |
| 3 | 25.725 | 8.342 | 1.247 |
| 4 | 25.727 | 8.848 | 1.211 |
| 5 | 40.064 | 8.692 | 1.276 |
| 6 | 40.092 | 8.650 | 1.304 |

All sampled `unstable` counts are zero. Delivered FPS counts frames delivered by capture; tag advance rates are distinct and can be higher.

## Inference and bench evidence

63 `[stats]` records report mean sampled `npu_completed_fps` **14.444**, with sampled completed counts summing to **910** and sampled failed counts summing to **0**. `frame_metrics.h` implements a one-second sliding event count; `[stats]` samples it about every five seconds. **910 is not the total completions over the interval**, and multiplying it by five does not recover an exact total.

234 `[tdm]` records advance the cumulative completed counter from **28640 to 33300**, a **4660** completion delta between those logged checkpoints. Those checkpoints lie inside the segment and do not coincide with collection boundaries.

No `[tdm_bench]` or `[infer-split]` records occur despite ongoing successful inference. The matching source emits `tdm_bench` on each success and `infer-split` every ten successes when `DET_BENCH` is set. This supports **bench disabled** for the observed run. Display performance instrumentation is enabled, evidenced directly by its logs. No environment was dumped.

## Toolchain and source identity

Live executable: `/userdata/linaro/detview-todo-work/build/detview`. Every file in the local baseline `detview/src` snapshot matches its corresponding current board source SHA-256; both maps are recorded in the JSON. Matching source files alone do not prove that every linked object was built from those files.

Read-only discovery found `/usr/bin/qmake` (qmake 3.1, Qt **5.15.8**), `/usr/bin/g++` (Debian **12.2.0-14**), and OpenCV **4.6.0** through `pkg-config opencv4`. Qt mkspec is **linux-g++**, with libraries in `/usr/lib/aarch64-linux-gnu` and headers in `/usr/include/aarch64-linux-gnu/qt5`.

The existing build Makefile records this exact generation command, run from `/userdata/linaro/detview-todo-work/build`:

```sh
/usr/lib/qt5/bin/qmake -o Makefile ../src/detview.pro INCLUDEPATH+=../sdk
```

Its CXX flags are `-pipe -O2 -std=gnu++1z -Wall -Wextra -D_REENTRANT -fPIC`, with `QT_NO_DEBUG`, `QT_WIDGETS_LIB`, `QT_GUI_LIB`, and `QT_CORE_LIB`; linker flags are `-Wl,-O1`. `detview.pro` specifies C++17, Qt core/gui/widgets, OpenCV through pkg-config, and `-lrknnrt -lrga`. Includes add `../sdk` and `/usr/include/opencv4`.

RKNN header: `/userdata/linaro/detview-todo-work/sdk/rknn_api.h`; runtime: `/usr/lib/librknnrt.so`. RGA library: `/usr/lib/aarch64-linux-gnu/librga.so` (also `.so.2` and `.so.2.1.0`). Plain `ldconfig` was unavailable on the login PATH; direct read-only file discovery supplied these library paths. The JSON preserves the full observed Makefile flags and OpenCV link list. The existing Makefile establishes the recorded configuration; no build was executed to validate reproduction.
