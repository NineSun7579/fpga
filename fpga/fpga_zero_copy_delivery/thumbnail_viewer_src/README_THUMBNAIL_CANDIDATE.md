# Isolated full viewer thumbnail candidate

Copied from installed `display_latency_delivery/src`. The production viewer,
RTL, driver and PDS project are untouched by this subtask. The qmake target is
`detview_thumbnail_candidate`; use a fresh build directory and regenerate moc.
RK3568 YOLO remains enabled. Retirement of the old FPGA NPU belongs to the
integrated RTL candidate, not this application.

## Build and switches

Use the parent's normal RK3568 Qt/OpenCV/RKNN/RGA build environment:

```sh
mkdir thumbnail-build && cd thumbnail-build
qmake ../thumbnail_viewer_src/detview.pro
make -j4
QT_QPA_PLATFORM=offscreen ./detview_thumbnail_candidate --thumbnail-selftest
QT_QPA_PLATFORM=offscreen ./detview_thumbnail_candidate --display-latency-selftest
QT_QPA_PLATFORM=offscreen ./detview_thumbnail_candidate --vision-selftest
```

Existing selftest flags remain available. The thumbnail test is also included in
`--vision-selftest`. Hardware-free standalone transaction tests can be built with:

```sh
c++ -std=c++17 -Wall -Wextra -Werror -DTHUMBNAIL_STANDALONE_SELFTEST \
    thumbnail_delivery_selftest.cpp -o thumbnail_delivery_selftest
./thumbnail_delivery_selftest
```

`DETVIEW_FPGA_THUMBNAIL=1` opts in; every other value leaves RAW display enabled.
Only C5 can use the endpoint. C5 automatically uses full 640x480 RAW if selected
for vision, included in stereo, or HDMI is active. All six workers continue
capturing in both grid and single-camera/HDMI views; explicit pause still pauses.
There is no second device open, subprocess or independent DMA provider.

When a selection or generation changes during a thumbnail transaction, that
transaction completes safely and the frame is discarded. The next read uses
the current configuration, with RAW forced for consumers that require it. A
thumbnail never enters `VisionFrame`, stereo, HDMI analytics or calibration.

## Hardware contract and ownership

All configurable hardware constants live in `thumbnail_delivery.h`. They match
the integrated agent's `README_DISPLAY_INTEGRATION.md`: DLV2 at `0x40020000`,
capability bits 0/1 at `+0xa0`, mode at `+0xb0`, RGB default destination
`0x0a000000`, thumbnail destination `0x0a200000`, 153600-byte RGB565 output.
Adapt this header if the integrated contract changes before board compilation.

Each thumbnail frame validates signature/caps/default mode/idle/geometry, selects
mode 1 only while unheld and idle, acquires C5's hold, waits for frozen, records
epoch/source/tag, submits, and waits for completed with busy clear and the jobs
counter advanced. It checks error/config/quarantine status throughout. Output
size and ownership are validated before DMA/copy and revalidated afterwards.
Only a validated complete read releases the hold; acknowledged release precedes
mode 0 restoration and readback. Repeated source tags are not published as fresh.

The existing PangoDev fd, mmap RX/TX and DMA mutex cover the **entire** lease,
MMIO, metadata, pixel DMA and owned-buffer copy. RAW pixel copies also remain
inside that mutex. Pixel reads use the deployed PCIe reader's existing logical
payload gather over native DDR burst slots, exactly as RAW `cameraRead` does.
The endpoint's physical half-slot gaps must not be copied into the texture.
Parent validation must confirm this gather on the actual driver/bitstream pair.

Any candidate DMA error/timeout, invalid contract, changed lease or uncertain
completion stops the process with SIGSTOP, retaining fd/mappings and any lease.
It does not release, restore mode or exit into the old supervisor restart path.
SIGCONT re-stops. Recovery requires the parent/operator to quiesce/reset the
connected fabric and DMA before terminating/restarting the owner. Do not use
an automatic kill/restart policy for this candidate after quarantine.

## Display and measurements

Owned latest/display/late-latch buffers include per-camera dimensions. Each
texture-ring slot tracks its own allocation width and height. Transitions
between 640x480 and 320x240 call `glTexImage2D`; subsequent uploads use matching
`glTexSubImage2D` dimensions. The existing camera shader uses normalized 0..1
texture coordinates, so the GPU scales the thumbnail to the same 4:3 tile.
There is no CPU upsample. A C5 thumbnail upload counts exactly 153600 bytes;
RAW remains 614400 bytes. The optional diagnostic composite PNG omits thumbnail
tiles rather than expanding them on CPU.

`DETVIEW_PERF=1` enables existing performance counters (also enabled by default);
`DETVIEW_LATENCY_TRACE=1` adds frame identity, width/height/bytes and timestamps.
`[capture-format]` also records the actual last captured format every audit period.
Both paths start DMA-to-upload/draw metrics at **host pixel DMA return**, before
copy/analytics. The old `capture_to_upload` aggregate is corrected to use this
same start and is labeled `host_dma_return_to_upload`. These metrics exclude
FPGA processing/wait time, exposure, GPU completion, scanout and panel response.
Use capture read_ms and end-to-end measurements alongside them. No CPU or
latency improvement is claimed for this first integration test.

## Evidence and remaining checks

Local Windows tests passed: standalone transport/geometry fault tests (66 cases)
and a Qt6 host test extracted from the candidate's actual mailbox/late-latch
methods (RAW/thumbnail/RAW ownership, sizes, generations and malformed buffers).
`generate_host_latch_test.py` regenerates that host test. `local_test_results.txt`
records commands/results. `verify_source_preservation.py` emits a unified source
diff and SHA256 manifest: only `main.cpp` and `detview.pro` differ among the 39
copied baseline files; 37 are byte-identical. The complete InferenceThread, RAW
RGB conversion and vision packet conversion remain byte-identical.

The full RK3568 viewer has not been compiled or run by this subagent. The parent
owns that build, normal selftests, actual driver/native-layout validation,
switching/HDMI/stereo checks and live six-camera measurements. No board or PDS
operations were performed here.
