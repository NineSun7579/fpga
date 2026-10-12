# Per-camera host candidate

This isolated source tree is copied from `motion_display/host/src`. Its qmake target remains `detview`. No original source, RTL, driver, device mapping, or board process is changed by this host work.

## Capture configuration

Opt in to the requested camera limits at launch:

```sh
export DETVIEW_CAPTURE_FPS_BY_CAMERA=40,40,30,30,40,40
```

The six comma-separated decimal rates map to CAM1 through CAM6. Every rate must be finite and within 10..60 inclusive. Whitespace and fractional decimal rates are accepted. Missing/extra elements, trailing commas, junk, hexadecimal, NaN, infinity and out-of-range values reject the entire list. An invalid list logs a warning and all cameras retain the global `DETVIEW_CAPTURE_MAX_FPS` value. An absent list also retains the original global behavior (0/unlimited when unset, bounded at 120). There is no hidden 40/30 default.

Each camera retains its own deadline, set from that camera's actual frame DMA start. Duplicate tags, unstable frames, source generations, pause/reset behavior and independently owned RX slots remain intact. Caps limit attempted frame transfers; they cannot guarantee fresh delivered FPS when sensor cadence, DMA throughput, inference, or GUI work limits throughput.

## Conversion and ownership

The baseline already calls `copyCameraPixels` for a single DMA-to-owned-RGB565 copy and uses buffer swaps for display. Its AArch64 wide-load DMA helper is preserved. DMA ioctls are serialized; each camera owns a separate RX slot through its CPU copy. The GUI must never borrow the mapped RX pointer: later DMA can overwrite it. Published QByteArray snapshots and RGB888 QImages retain owned immutable storage; writable storage is replaced when display snapshots still share it.

The remaining RGB565-to-RGB888 manual loop serves selected inference and stereo cameras. The replacement converts eight pixels at once using AArch64 NEON and an interleaved `vst3_u8` store, with an exact portable tail/fallback. It deliberately retains `(r5<<3)|(r5>>2)`, `(g6<<2)|(g6>>4)`, `(b5<<3)|(b5>>2)`. QImage::convertToFormat was not substituted because its conversion implementation/version and pixel rounding would require independent parity and timing validation. Conversion runs only on owned RAM, never directly on DMA mappings. No reusable mutable QImage is handed to an asynchronous consumer.

`[capture] copy_ms` continues to measure DMA-to-owned-RGB565 copying only. New `[capture-rgb] owned_rgb888_ms` separately includes RGB888 allocation and conversion, excluding analytics submission and motion metadata. NEON cannot by itself explain or fix a high DMA copy_ms value. Existing camera_dma.h already optimizes that copy; its actual board performance and mapped-memory attributes need board measurements.

## GUI work and analytics

Camera display publication defaults to a 16 ms minimum interval, with the existing `DETVIEW_MIN_MS` override retained. A precise GUI timer consumes the latest pending camera snapshot every 16 ms. Notifications mark pending work; they do not immediately schedule another frame submission. The existing bounded mailbox accumulates changed camera bits and retains only the newest pixels. OpenGL presentation remains subject to the platform's swap/vsync behavior; QTimer is not a hardware-vsync callback. A busy GUI may display fewer frames. The initial 25 ms proposal was corrected because it provided no scheduling margin for fresh40fps.

Existing HUD revision/expiry caching and optional `DETVIEW_HUD_BATCH=1` upload batching are retained. This candidate does not change overlay contents or detection expiration rules. Analytics submission remains in the capture workers, independent of GUI consumption. Stereo stays at its existing default 200 ms cadence and motion polling at 100 ms. Tracking defaults and worker topology are unchanged.

## Validation

Standalone parity/parser/pacing tests require no Qt, RKNN or board access:

```sh
c++ -O3 -Wall -Wextra -std=c++17 host_optimization_selftest.cpp -o host_optimization_selftest
./host_optimization_selftest --benchmark
```

Local Windows MinGW execution passed 63 checks: exhaustive 65,536 colors, aligned and unaligned buffers, zero/odd lengths and SIMD boundary tails, destination guards, padded rows, decimal caps, malformed-list fallback and pacing/reset. Only the portable backend executed locally. The benchmark is a helper microbenchmark, not a delivered-FPS claim. Run the same test on AArch64 to exercise NEON before deployment, then compare per-camera delivered FPS, tag advance, copy_ms, owned_rgb888_ms, capture-to-upload latency, GUI delay, HUD rebuilds and paint timing with inference and both stereo pairs enabled. Full Linux Qt/RKNN application compilation and board throughput validation belong to the parent session; neither was performed here.
