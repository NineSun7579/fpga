# Isolated scheme2 viewer candidate (not deployed)

**Review revision:** [README_REVIEW_FIXES.md](README_REVIEW_FIXES.md) is the current
ownership, admission and context contract. It supersedes the early-BEGIN and
lazy-context design described below. Read it before building/deployment review.

Source-only copy of `../baseline_1791563289001003700/viewer`, excluding generated
`moc_*` files and the old executable hash list. The snapshot and driver sources
were not edited. Target name is `detview_scheme2_candidate`.

`DETVIEW_FPGA_INFER_RGB=1` enables the candidate path. Unset, `0`, and every other
value keep the conventional viewer path and 4 MiB mappings. The enabled path
requires the independent candidate driver and the six-camera mode-0 image under
`../hardware_baseline`; it cannot run on the old 4 MiB allocator. No board calls,
FPGA programming, deployment, or hardware performance claims were made here.

## Acquisition and ownership

1. `VisionPipeline::request` first checks the original urgency, cadence, pending
   request, source and model conditions. When due, it arms acquisition for the
   selected camera/generation and next cached model height. It does not ask the
   FPGA to recreate an earlier analytics frame.
2. That camera's worker claims one published RAW bank with the delivery endpoint
   at `0x40020000`, mode 0, output bank 0. It checks epoch, source, sequence,
   camera, publication, destination and RAW commit tag against that lease.
   Writable physical camera-bank destinations are audited for overlap using the
   same checks as the validated baseline host.
3. RAW is copied from the held bank to the original owned camera image for
   display/tracking/stereo. RGB conversion is submitted on that same held bank,
   and completion plus identity is checked again. The converted DDR destination
   remains exclusively owned by this viewer's sole converter owner.
4. The FPGA camera hold is released and selectors restored **before** the final
   RGB F2H transfer. This avoids attempting register DMA while `PZ_BEGIN` blocks
   all driver DMA. No converter job can overwrite the destination in between:
   all submissions share the same transport mutex and single admission gate.
5. For height 480, F2H reads `destination + 153600`, length 921600, directly into
   RX offset `0x400000`. Height 640 reads the full 1228800 bytes there. Neither
   path binds a non-page-aligned RKNN offset. BEGIN reserves 1228800 bytes at
   `0x400000` in both cases. It follows the payload transfer immediately; later
   scratch/register transfers would replace the driver's ready publication.
6. The exact `VisionFrame` carries a shared input token with camera, source
   generation, tag, FPGA epoch and bank address. Analytics ingress pins an
   undispatched admitted frame against replacement by ordinary tracking frames.
   The token is carried through the inference queue without changing identity.
7. Each selected model imports the real exported RX DMA-BUF once with
   `rknn_create_mem_from_fd(context, fd, full_rx_base, input_bytes, 0x400000)`.
   It binds UINT8 NHWC, pass-through 0. The bound path performs no input CPU copy,
   signed-byte conversion, padding copy or `rknn_inputs_set`.
8. Successful synchronous run/output retirement precedes END. Cancelled frames
   that were never submitted can END safely. A failed bound operation or consumer
   stack unwind quarantines the process; it cannot falsely assert completion.
   Context imports retain backing ownership beyond queued token retirement, so
   camera-thread shutdown cannot close/unmap storage under a cached importer.

The original model bytes, input geometry checks, raw6/raw10/raw4 validation,
output attributes, decoders and canonical-coordinate restoration remain in use.
A coherent RKNN context is created lazily per model, using those same bytes and
attributes with `RKNN_FLAG_DISABLE_FLUSH_INPUT_MEM_CACHE`. The original context
is retained for conventional video/HDMI inference. This costs an additional
context for each model that uses the bound path; target memory use needs review.

CPU RGB565 expansion **remains** for tracking and stereo. This candidate only
removes CPU preparation on the bound RKNN input path. Display stays RGB565 and
video/HDMI retain their conventional inference path. The flag does not claim to
remove all camera conversion costs.

## Required driver peer contract

Preflight requests one 4 KiB TX page and 8 MiB RX (8 MiB + 4 KiB total). TX register writes use
host offset 0; the existing `0x3ff000` scratch is RX-only. On a MAP failure,
the viewer logs the ioctl command, selector, host offset, DDR address, requested
bytes, TID, return code, errno/text and alarm state, then flushes stderr. MAP
does not submit DMA. A successful idle UNMAP (selector 3) frees any earlier
allocation before closing the device and returning FATAL; the UI exits with
code 3. If UNMAP cannot confirm idle cleanup, ownership is preserved and the
process quarantines. DMA failures retain their existing quarantine behavior.
There is no CPU fallback. With only 16 MiB total CMA, additional GPU/NPU users
and fragmentation can still prevent an 8 MiB contiguous RX allocation; inspect
the logged errno and CMA evidence before changing allocator or DMA mask policy.

- Exclusive device owner and version-1 export/lease ABI from `scheme2_uapi.h`.
- Enabled TX allocation/mapping is 4 KiB; RX capacity is 8 MiB. Flag-off TX/RX remain 4 MiB. Existing RX mmap selector remains
  `0x100000`. Existing camera slots and scratch stay below `0x400000`.
- Export the actual coherent RX backing as a DMA-BUF. A copied/CPU-owned buffer
  is not an accepted substitute.
- Permit the fixed BEGIN extent `(offset=0x400000,length=1228800)` after a completed
  F2H at that offset of **either** 921600 or 1228800 bytes. Keep publication
  length exact; only the imported prefix is read for a rectangular context.
  The old driver's `ready_length == lease.length` check rejects the rectangular
  case with `ENODATA`; an allocator-size change alone is insufficient.
- Preserve exclusion of all DMA while the consumer token is active. Viewer
  submissions use the shared transport mutex and skip while the token is held.
- Preserve fault/quarantine semantics. Candidate DMA faults stop instead of
  invoking the baseline automatic driver-reopen recovery path.

`[scheme2] ... lease_hold_ms=...` measures global DMA exclusion from BEGIN to
END, including queue/context-init/run/decode time. Existing capture and NPU
metrics remain separate. This design can reduce camera throughput during NPU
ownership; it needs measurement, not an assumed speedup.

## Local validation

Run in WSL Ubuntu from this directory (writes only `local_build/`):

```sh
mkdir -p local_build
g++ -std=c++17 -Wall -Wextra -Werror -fPIC -pthread \
  scheme2_selftest.cpp camera_dma_selftest.cpp inference_geometry_selftest.cpp \
  mvp_decode_selftest.cpp $(pkg-config --cflags --libs Qt5Gui) \
  -o local_build/scheme2_selftest
local_build/scheme2_selftest
DETVIEW_FPGA_INFER_RGB=0 local_build/scheme2_selftest
DETVIEW_FPGA_INFER_RGB=1 EXPECT_SCHEME2_ON=1 local_build/scheme2_selftest
python3 local_protocol_check.py
g++ -std=c++17 -Wall -Wextra -Werror -fPIC -pthread -I. \
  $(pkg-config --cflags Qt5Core) local_build/protocol.cpp \
  $(pkg-config --libs Qt5Core) \
  -Wl,--wrap=open,--wrap=close,--wrap=mmap,--wrap=munmap,--wrap=ioctl,--wrap=raise \
  -o local_build/protocol_test
DETVIEW_FPGA_INFER_RGB=1 local_build/protocol_test
python3 local_syntax_check.py
g++ -std=c++17 -Wall -Wextra -fPIC -fsyntax-only -I. \
  $(pkg-config --cflags Qt5Widgets) local_build/main_classes.cpp
```

Passed locally: default-off flag behavior; concurrent single-slot admission;
queued/backing lifetime and exactly-once retirement; 480/640 crop byte layout;
baseline camera-copy, inference-geometry and MVP decoder selftests; actual
candidate `PangoDev` mode-0 acquisition against wrapped device syscalls for all
six cameras and both heights; and classes-only viewer syntax.

The extracted PangoDev syscall fixture also exercises TX/RX ENOMEM, interruption
after a successful MAP, confirmed UNMAP cleanup without any DMA/export, and
preserved ownership when cleanup returns EBUSY. It checks 4 KiB TX / 8 MiB RX
allocation, mmap and munmap lengths. This remains a local fixture, not a CMA or
hardware acceptance result.

The wrapped-syscall test is not hardware parity. The syntax check removes unused
OpenCV/RGA includes and excludes `main()`; it is not a linked viewer build.
Full `qmake ../detview.pro` failed locally with
`Project ERROR: opencv4 development package not found`. RGA development headers,
target RKNN runtime, ARM build/link, full `VisionPipeline` compilation/tests,
live input/native-output parity for the original model contexts, importer/cache
ownership validation and live performance measurement remain for parent review.

Original baseline `main.cpp` SHA256, verified unchanged after implementation:
`08b239abbc02a8f5da6526b9f27d04ce1d3ddf5974f339148850dc0dda5c5c95`.

## Opt-in live verification (requires a separate parent build)

Set both `DETVIEW_FPGA_INFER_RGB=1` and `DETVIEW_FPGA_INFER_VERIFY=1`, or use
`--fpga-infer-verify` with the RGB flag already enabled. Verification defaults
off. `DETVIEW_FPGA_INFER_VERIFY_COUNT=N` / `--fpga-infer-verify-count N` selects a
marker threshold from 1 through 10000 (default 12; invalid values use 12).
Verification without the RGB feature returns an error before starting workers.

Every acquisition compares **all** payload bytes against little-endian RGB565
RAW copied while the same FPGA bank was held. Golden RGB uses bit replication,
RGB channel order, 114 padding for square contexts, and the exact 480 crop.
Comparison runs under the sole producer mutex after completed F2H and before
BEGIN; it never CPU-reads a DMA-BUF while RKNN owns it. The owned CPU golden is
carried in that same input token. Input PASS logs camera, tag, epoch, height,
bytes and acquisition count. A mismatch logs the first byte and quarantines.

For each submitted frame, the existing conventional context receives CPU golden
UINT8 NHWC through `rknn_inputs_set` and runs once. All its outputs are obtained
with `want_float=0`, copied in full, and released. The bound context runs the
same model/frame and obtains native outputs the same way. Count, returned byte
sizes and every output byte must match exactly. Returned native size must equal
the original output attribute `size`; unsupported layouts fail closed and are
not counted as parity. There is no tolerance or decoded-box-only comparison.
Output PASS logs exact model path, camera, tag, frame id, height, output count,
total bytes and completion count. The bound context then runs once more on its
still-owned unchanged input and feeds the **unchanged** `want_float=1` decoder
path. These are three NPU runs per verified submission, intentionally avoiding
multiple output retrieval representations after a single run's release.

`INPUT_COUNT_REACHED` and `OUTPUT_COUNT_REACHED` are emitted once at the chosen
aggregate threshold. They are receipt markers, not an automatic deployment
gate or a claim that every model/camera was exercised. Every later acquired
frame continues verification. Parent should bound the hardware session and
check individual PASS logs for all intended model contexts/cameras, including
raw6/raw10/raw4. Cancelled acquisitions can make input count exceed output count.

Verification logs include `performance_sample=0`. It disables DET_BENCH,
capture/lease performance logs, periodic combined stats and RKNN event metrics;
reported inference service time is zero. Existing analytics/display diagnostic
logs can still occur and are **not** valid performance evidence in this mode.
Restart with verification unset for timing measurements; do not toggle it inside
a running process.

Additional local checks passed: all 65536 RGB565 values, every padding byte,
first/final-byte corruption detection, default-off/opt-in verification behavior;
actual acquisition code with verification enabled across all six cameras at
both heights (12 input receipts and threshold marker); actual native output
capture helper with raw4/raw6/raw10 fixture counts, complete byte copying,
last-byte corruption and rejection of unsupported returned sizes. These tests
wrap local API fixtures and do not claim RKNN hardware parity.

```sh
DETVIEW_FPGA_INFER_RGB=1 EXPECT_SCHEME2_ON=1 \
  DETVIEW_FPGA_INFER_VERIFY=1 EXPECT_VERIFY_ON=1 local_build/scheme2_selftest
DETVIEW_FPGA_INFER_RGB=1 DETVIEW_FPGA_INFER_VERIFY=1 local_build/protocol_test
python3 local_native_verify_check.py
g++ -std=c++17 -Wall -Wextra -Werror -pthread -I. \
  local_build/native_verify.cpp -o local_build/native_verify_test
local_build/native_verify_test
```
