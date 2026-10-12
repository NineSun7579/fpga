# Display latency candidate

Candidate source: `src/main.cpp` and the copied `src` tree. Production
`../detview_display_fix/src` is untouched. Only candidate `main.cpp` differs.
No FPGA/PDS, board, model, inference or detection changes were performed here.

## Controls and comparison

Build one binary and run the same workload with:

```sh
# A: original display behavior, with the new timing instrumentation
DETVIEW_LATE_LATCH=0 DETVIEW_PERF=1 DETVIEW_MIN_MS=24 ./detview <same arguments>
# B: late-latch display behavior, same instrumentation and publication cadence
DETVIEW_LATE_LATCH=1 DETVIEW_PERF=1 DETVIEW_MIN_MS=24 ./detview <same arguments>
```

Final installed candidate defaults to late latch (1) when `DETVIEW_LATE_LATCH`
is unset. `DETVIEW_LATE_LATCH=0` restores baseline behavior. Run A/B/B/A with identical
camera selection, model, screen, texture ring, HUD interval, duration and warmup.
Use existing inference/capture/FPS logs to check that improved frame age does
not cost throughput. Compare per-camera distributions, excluding startup and
mode transitions; combine `sum_ms` and `count` across windows for means. Do not
average window P95 values. Histogram quantiles have 0.5 ms upper-bound buckets.
Use `DETVIEW_LATENCY_TRACE=1` in both modes only if individual frame timestamps
are needed; tracing adds synchronous stderr overhead.

## Behavior

The publisher still samples every 24 ms by default. Immediately before painting
the candidate refreshes the accepted camera snapshot from the current owned
camera store. It replaces pixels, sequence, tag, generation and timestamps as
one transaction under the store mutex. It only accepts a strictly newer complete
frame from the same source generation and display configuration. The selected
pane, HDMI mode, pause state and shutdown state are checked under the config
mutex; only visible cameras are refreshed. Video playback uses its existing path.

The store is shared-owned and published/cleared under the config mutex. Qt
implicit sharing retains pixel lifetime; the existing worker allocates writable
storage when its recycled buffer is still shared. Locks are released before GL
uploads. The refresh does not consume or publish the display mailbox, notify the
GUI, submit analytics, change raw calibration snapshots, or add take/replacement
events. A publisher frame already uploaded through late latch is not uploaded
again in candidate mode. No additional polling or GUI scheduling was introduced.

## Timestamp scope

Both A and B attach a `CLOCK_MONOTONIC` nanosecond stamp immediately after a
successful frame DMA ioctl returns, before tag validation, CPU pixel copy and
the existing analytics submission. Frames rejected by tag validation are not
displayed or measured. The stamp travels with the owned pixels and metadata.

`[display-latency]` reports camera 1..6 separately:

- `dma_return_to_upload`: DMA return to the return of that camera's GL upload
  call, once per new visible frame identity.
- `dma_return_to_draw`: DMA return to the return of the first GL draw call using
  that uploaded camera frame, once per new identity.
- `refreshed`: snapshots replaced with a newer camera frame during painting.

`[display-latency-frame]` optionally includes generation, camera sequence, FPGA
tag, `dma_return_ns`, `upload_end_ns`, and `draw_end_ns`. Settings-only paints,
paused display, repeated frames and invisible HDMI tiles do not add latency
samples. The legacy aggregate `capture_to_upload` stage remains based on worker
completion milliseconds and is a different metric; use the new per-camera
stages for A/B comparison.

These endpoints measure host frame age to GL call return. They include CPU
copy/analytics work, publication/GUI wait and GL call time. They do not measure
sensor exposure, FPGA capture time, GPU completion, swap completion, scanout or
panel response. No `glFinish`, fences or rendering stalls were added. An actual
latency improvement is pending the parent session's board measurements.

## Build and verification

Build out of tree on the existing Linux/RK3568 toolchain:

```sh
mkdir -p build
cd build
qmake ../src/detview.pro
make -j2
QT_QPA_PLATFORM=offscreen ./detview --display-latency-selftest
QT_QPA_PLATFORM=offscreen ./detview --vision-selftest
```

The dependencies are unchanged: Qt Core/GUI/Widgets, OpenCV4, RKNN runtime and
RGA. Regenerate moc files with qmake/make; do not reuse an old main.moc.

Local verification completed:

- `python verify_preservation.py`: PASS. `preservation.json` contains SHA256
  evidence for every copied file and protected analytics region; all protected
  regions match byte-for-byte. `latency_candidate.patch` is the source diff.
- `python generate_latch_test.py`, followed by host MSVC compilation linked to
  actual Qt 5.15.2 Core/GUI: PASS (`DISPLAY_LATE_LATCH_SELFTEST_PASS`). The harness
  extracts the exact candidate refresh, config, mailbox and selftest methods;
  it exercises Qt ownership/detach, metadata correspondence, strictly newer
  sequences, pause, source-generation mismatch, pane switches, video rejection,
  HDMI visibility and store lifetime. It does not compile the full renderer.

The full RK3568 binary build and live performance/YOLO regression verification
belong to the parent session. No target build or measured reduction is claimed.
