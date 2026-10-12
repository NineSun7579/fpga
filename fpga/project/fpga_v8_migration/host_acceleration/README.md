# Isolated RK3568 raw DFL decoder experiment

This directory is a source candidate and benchmark only. It does not change the
viewer, production decoder, FPGA RTL, PDS project, or board runtime. The parent
session has measured the original canonical decoder on the board; the optional
production compatibility mode below awaits its board validation. No board access
was performed while implementing this update.

## Contract and API

`raw_dfl_native.h` requires exactly these packed outputs, identified by exact name
and output index, even when the attributes and buffers are independently permuted:

| Name | NCHW shape | Stride |
| --- | --- | --- |
| box_p3 | 1,64,80,80 | 8 |
| box_p4 | 1,64,40,40 | 16 |
| box_p5 | 1,64,20,20 | 32 |
| cls_p3 | 1,3,80,80 | 8 |
| cls_p4 | 1,3,40,40 | 16 |
| cls_p5 | 1,3,20,20 | 32 |

Use `RKNN_QUERY_OUTPUT_ATTR` and `rknn_outputs_get(want_float=0)`, not native
NC1HWC2 zero-copy attributes or device-strided buffers. The decoder checks names,
shapes, NCHW, S8/U8 affine quantization, in-range zero points, finite positive
scales, exact element/byte counts, unpadded width, and nonnull buffers. Device
`size_with_stride` is allocation metadata and does not replace the packed
`rknn_output.size` check. Malformed inputs throw `std::invalid_argument` before
reading tensor data. Negative/zero/nonfinite scales are rejected.

```cpp
#include "raw_dfl_native.h"
raw_dfl::NativeDecoder decoder; // one instance per thread; keep LUTs warm
raw_dfl::DecodeStats stats;
auto detections = decoder.decode(outputs, attributes, &stats);
// Also available: raw_dfl::decode(outputs, attributes, config, &stats).
```

With the default `Config::production_compatibility=false`, classification always
applies `sigmoid((q-zp)*scale)`, including logits in
`[0,1]`. It picks one best class per cell, breaking class ties by lowest class
index. Default confidence is 0.25 inclusive. Candidate ties use canonical
p3/p4/p5 row-major anchor order, independent of output permutation. Top 300
candidates are chosen before any DFL box work. Default class-agnostic NMS uses
strict IoU > 0.45 and the production `1e-6` denominator epsilon. Boxes remain in
the letterboxed 640x640 coordinate system, including negative/padded coordinates.
`Config` exposes confidence, IoU, topk, the opt-in production compatibility flag,
and the separate opt-in pinned runtime dequantization flag described below.

Set `config.production_compatibility = true` to mirror the frozen production
decoder's scoring and tie behavior:

- Iterate scales in box-head encounter order in the supplied attributes, with
  row-major cells and one best class per cell.
- Sample dequantized class 0 of the first scale for at most 2000 cells. Apply
  sigmoid only if max > 1.5 or min < -0.5; otherwise use raw dequantized scores.
- Fully `std::sort` **all** qualified candidates by descending score only, then
  resize to topk (300 by default). No canonical tiebreaker or partial sort.
- Decode DFL, then perform a **second** score-only `std::sort` on boxes before NMS.

This mode retains mandatory six-name/shape/buffer validation and cached integer
DFL. `DecodeStats::used_sigmoid` reports the decision. Default canonical behavior
remains unchanged. Full production parity assumes topk=300, IoU=0.45, and the same
standard library sort implementation as the frozen include. Compatibility ties
deliberately inherit that implementation's ordering and depend on attribute
encounter order; canonical ties remain deterministic across permutations.

Native decoding caches 256 sigmoid and raw dequantized values per unique
class-head type/zp/scale and
256 exp values per unique box-head scale. Each DFL side subtracts its actual
maximum integer code, so zero point cancels and LUT differences cover -255..0.
No full float head is allocated. Cache tables are reused across calls. Qualified
candidate selection, 4x16-bin DFL, and NMS all use float precision.

### Pinned RKNN 2.3.0 dequantization profile

`Config::pinned_rknn230_dequantization=false` preserves mathematical conversion
`float(q-zp)*scale` for all generic models. Set it to `true` only for the audited
wb_v8_w25_nop2c2f model/runtime combination. This flag is independent of
`production_compatibility`: it selects float conversion, while compatibility
selects the class heuristic and tie policy.

```cpp
raw_dfl::Config config;
config.production_compatibility = true; // optional: frozen production semantics
config.pinned_rknn230_dequantization = true;
raw_dfl::NativeDecoder native(config);
auto detections = native.decode(outputs, attributes);
auto floats = raw_dfl::full_dequantize(outputs, attributes, config);
auto scalar = raw_dfl::scalar_float_decode(floats, config);
// scalar_reference(outputs, attributes, config) also passes the profile through.
```

The same-completed-run probe at `../runtime_dequant_probe/pipeline_metadata.json`
and `pipeline_mapping.csv` contains 30 frames, 16,884,000 observations, and 1,214
unique head/code pairs. Acquisition was raw get/release, float get/release, then
raw get/release; raw bytes never changed and no code had ambiguous float bits.
Its authoritative `runtime_bits` show these model-specific conversion formulas:

- p3/p4 boxes and classes: `float(q-zp) * float16_RNE(scale)`, with the rounded
  half coefficient promoted back to binary32. The pinned half-coefficient bits
  are explicit constants; no rule is inferred for another model/runtime.
- p5 boxes and classes: `std::fma(float(q), scale, rounded_float(-float(zp)*scale))`.
  The offset product is explicitly rounded before FMA. In particular, box p5
  `q==zp==-35` produces bits `0x33980000`, not zero.

Native class tables use those runtime float values for both sigmoid and raw
scores. p3/p4 DFL retain the integer-difference exp table with the pinned half
coefficients; their dyadic differences are exact in binary32. For selected p5
cells, a cached 256-entry float-logit table supplies the actual rounded logits,
then the decoder computes `exp(logit-max_logit)` for each bin. There is no full
float-head allocation or 65,536-entry pair table. The scalar reference converts
all heads with the selected formula and annotates `FloatHeads` with the profile;
its DFL still uses scalar float subtraction and exp. Existing score <=1e-6 and
coordinate <=1e-3 pixel tolerances remain unchanged.

Enabling the profile checks the ordinary six-name/shape/packed-buffer contract
plus exact INT8 type, logical name-to-index binding, zero points, and binary32
scale bits:

| Head | Index | zp | Scale bits | Half coefficient bits (p3/p4 used) |
| --- | --- | --- | --- | --- |
| box_p3 | 0 | 0 | 0x3da0a0a1 | 0x3da0a000 |
| box_p4 | 1 | -2 | 0x3d9e27da | 0x3d9e2000 |
| box_p5 | 2 | -35 | 0x3d7c33af | not used |
| cls_p3 | 3 | 83 | 0x3d425e3c | 0x3d426000 |
| cls_p4 | 4 | 69 | 0x3d50337b | 0x3d504000 |
| cls_p5 | 5 | 71 | 0x3d4d63f2 | not used |

Vector encounter order may still be permuted; actual logical name/index bindings
must match the pin. The profile requires IEEE binary32, round-to-nearest FP mode,
and compilation without fast-math. Use `-fno-fast-math -ffp-contract=off` or MSVC
`/fp:precise`; p5 explicitly calls `std::fma`.

The decoder header makes no RKNN queries and cannot verify runtime/model
identity. Before selecting this profile, the caller must bind:

- Model SHA256: `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9`.
- Runtime API: `2.3.0 (c949ad889d@2024-11-07T11:35:33)`; audited driver `0.9.8`.
- Loaded runtime `/usr/lib/librknnrt.so` SHA256:
  `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`.

This is a profile for that pin, not a general claim about RKNN dequantization.
The parent session owns pipeline identity enforcement and board certification.
`bench.cpp` continues to use the mathematical default; its existing optional
argument selects production tie/heuristic compatibility only.

`raw_dfl_reference.h` materializes all 562,800 head elements (2,251,200 float
bytes). In default mode it applies scalar sigmoid/exp and canonical topk/NMS;
compatibility mode independently reads the recorded source attribute scale order,
applies the same float sample heuristic, and performs both score-only sorts.
`FloatHeads::scale_order` is populated by `full_dequantize`; manually constructed
float fixtures default to p3/p4/p5 order. Parity requires equal ordered
anchors/classes/counts, score
error <= 1e-6, and every coordinate error <= 1e-3 pixel. Raw code subtraction and
separately dequantized float subtraction can round differently; a near-threshold
NMS change is a parity failure, not silently accepted.

`legacy_production_adapter.h` imports the **unchanged**
`../board/board_production_decoder.inc`. Its heuristic samples class 0 of the
first paired scale in attribute order, for at most 2000 cells, and applies
sigmoid only if max > 1.5 or min < -0.5. It also uses score-only `std::sort`, so
quantized score ties can select different top-300/NMS survivors. Legacy
comparison matches boxes by class and coordinate tolerance without relying on
that sort order, and reports unmatched boxes and score discrepancies separately.

## CPU self-test

On Linux/board, point `SDK` to the directory containing `rknn_api.h`. No RKNN
runtime link or NPU access is needed for either self-test:

```sh
SDK=/path/to/sdk
g++ -std=c++17 -O3 -Wall -Wextra -Wpedantic -fno-fast-math -ffp-contract=off \
    -I"$SDK" selftest.cpp -o raw_dfl_selftest
./raw_dfl_selftest

g++ -std=c++17 -O3 -fPIC -fno-fast-math -ffp-contract=off \
    -DRAW_DFL_WITH_LEGACY -I"$SDK" selftest.cpp \
    $(pkg-config --cflags --libs Qt5Core) -o raw_dfl_selftest_legacy
./raw_dfl_selftest_legacy
```

The relative production include requires the existing sibling `board` directory
to remain present when compiling the legacy test or benchmark. Qt6Core also
works for a desktop check. Core-only testing needs just C++17 and the SDK header.
Locally, that header is at
`../../hardware_acceleration/rknn_io/prepared/sdk/rknn_api.h`.

Windows MSVC: run `build_local_selftest.cmd` in this directory. Its VS2022 path
is explicit; all outputs stay here. For the installed Windows MinGW/Qt6:

```powershell
& 'C:/Qt/Tools/mingw1310_64/bin/g++.exe' -std=c++17 -O3 -Wall -Wextra -Wpedantic `
  -fno-fast-math -ffp-contract=off -DRAW_DFL_WITH_LEGACY `
  -I../../hardware_acceleration/rknn_io/prepared/sdk `
  -IC:/Qt/6.11.1/mingw_64/include -IC:/Qt/6.11.1/mingw_64/include/QtCore `
  selftest.cpp -LC:/Qt/6.11.1/mingw_64/lib -lQt6Core -o selftest_legacy.exe
$env:PATH = 'C:/Qt/Tools/mingw1310_64/bin;C:/Qt/6.11.1/mingw_64/bin;' + $env:PATH
./selftest_legacy.exe
```

Fixtures cover all three scales/classes, S8/U8 and mixed types, independent
output/attribute permutations, table sharing/reuse, exact sigmoid on all `[0,1]`
logits, one-label behavior, confidence nextafter boundaries, top300 ordering,
class-agnostic NMS, negative/outside letterbox boxes, full code difference 255,
affine endpoint zero points, random/uniform/saturated distributions, and rejection
of wrong names/shapes/types/quantization/sizes/stride/scales/indices/null buffers.
With Qt, they exercise the real legacy decoder for both normal parity and the
`[0,1]` semantic discrepancy, plus 33 compatibility fixtures. Those compare
ordered counts/classes/scores/boxes directly against the real include, covering
8400 tied qualified cells, tiny and overlapping boxes, reordered aligned
box/class pairs, S8/U8, mixed affine heads, both score sorts, strict heuristic
boundaries, class0-only sampling, sample index 1999 versus 2000, and a changed
first scale. Invalid inputs are rejected in both modes.

Local validation passed using MSVC C++17 and GCC 13 C++17, plus the real
production include with Qt5Core (MSVC) and Qt6Core (GCC). All 33 compatibility
fixtures passed against the frozen include on both toolchains. Maximum
native/scalar and compatible-native/production coordinate error was
`0.0000610352` pixel. The default `[0,1]`
fixture produced 300 native detections versus one legacy detection, with the
matching box scored `0.731059` versus `1.0`. The local pinned RKNN file hash was
also checked against the pin below. Compatibility mode returns the same one
detection at score `1.0` as production for that fixture.

The pinned conversion update passed locally with GCC/Qt6 and MSVC/Qt5 against
the real frozen production include. Each checked all **1,214** authoritative
mapping entries bit-exactly (per-head counts 214,178,208,251,231,132), representing
all 16,884,000 probe observations. 995 entries differ from mathematical affine
conversion. Tests also construct complete float heads directly from those
observed bits and compare both decoder contracts independently, cover 24
synthetic endpoint expectations and both p5 FMA residuals, force selected p5 DFL,
and reject altered scale/type/zp/index pins. Total production-compatible fixtures
with the optional mapping test are 37; prior generic/default fixtures still pass.

To run the authoritative mapping checks after either self-test build:

```sh
./raw_dfl_selftest_legacy ../runtime_dequant_probe/pipeline_mapping.csv
```

On Windows, pass the same argument to `selftest_legacy.exe` or `selftest_qt5.exe`.
The CSV is read-only and optional; synthetic profile checks always run. Runtime
float decimal strings are never used as expected values, preserving near-zero
residual bits.

`bench.cpp` passed GCC/Qt6 and MSVC/Qt5 syntax checks against the actual SDK
header and the declaration-only OpenCV stand-in in `test_support`. This checks
C++ and RKNN/Qt API usage but does not validate the real OpenCV library link or
NPU behavior. **Never add `test_support` to the board compile include path.**
Those checks cover the compatibility update; its full board build and timings
remain pending. The parent reported the original canonical run
`native_board_benchmark_retry`: 30 frames x 100 iterations, scalar mean 3.357 ms,
native mean 0.272 ms, exact canonical parity PASS. Legacy had one unmatched box
on each of frames 4, 5, 9, 12, and 16; all used sigmoid and matched scores had
zero error. These parent-supplied results motivated the compatibility mode and
are not measurements of the new mode.

## Board benchmark (instructions only)

Requires RKNN runtime, Qt5Core, OpenCV core/imgproc/imgcodecs/videoio, and the SDK
header. This is a separate executable, not a production Model/viewer change:

```sh
SDK=/path/to/sdk
RKNN_LIB=/path/to/librknnrt/directory
g++ -std=c++17 -O3 -fPIC -Wall -Wextra -fno-fast-math -ffp-contract=off \
    -I"$SDK" bench.cpp -L"$RKNN_LIB" -Wl,-rpath,"$RKNN_LIB" -lrknnrt \
    $(pkg-config --cflags --libs Qt5Core opencv4) -o raw_dfl_bench

MODEL=/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn
MODEL_SHA=$(sha256sum "$MODEL" | cut -d' ' -f1)
./raw_dfl_bench "$MODEL" road_frames.txt result "$MODEL_SHA" 100 30 0.25 0.45
./raw_dfl_bench "$MODEL" road_frames.txt result_compat "$MODEL_SHA" 100 30 0.25 0.45 1
# ROAD_VIDEO may replace road_frames.txt; lists use one absolute path per line.
```

The benchmark requires the pinned filename and SHA256
`be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9`.
It accepts a caller-supplied hash and independently hashes the loaded bytes
before RKNN initialization. IoU stays at 0.45 for actual production comparison;
the native API itself supports other IoUs. Default iterations=100 and frames=30,
and at least 30 road images are mandatory.
The final optional argument is `production_compat=0|1` (default 0). Both native
and full-dequant scalar timings use the selected mode. In mode 1, scalar parity
means the float production-compatible contract, not always-sigmoid canonical
parity. Metadata, sample/summary/parity CSV, and stdout identify the mode;
parity CSV also records native and legacy sigmoid decisions.

All images are captured into memory first. Then each distinct captured frame
gets fresh preprocessing, inputs_set, one synchronous RKNN run, and one
outputs_get with want_float=0. The packed bytes are copied into immutable
snapshots and released before decoder measurement. Parity and CPU warmup occur
on every snapshot outside timing. Decoder timing loops repeat full-dequant+
scalar DFL+NMS and cached native DFL+NMS 100 times on the **same snapshot**, with
alternating first decoder. No RKNN calls occur in those loops. Allocation,
candidate selection, DFL, NMS, and output construction are included; consuming
the output checksum happens after timing. NPU acquisition times are separate
and include the first cold frame. Decoder speedup is not an end-to-end FPS claim.

Outputs:

- `_samples.csv`: paired decoder milliseconds for each frame/iteration, order,
  qualified count, DFL count, kept count, mode, and sigmoid decision; includes model SHA.
- `_summary.csv`: min/mean/p50/p95/max for both decoders and separate RKNN stages.
- `_acquisition.csv`: original input ID and fresh input/run/get/copy timings.
- `_parity.csv`: selected scalar contract pass/errors, contract label and mode,
  and real legacy heuristic/count/box/score discrepancies for every frame.
- `_detections.csv`: all native, selected scalar, and legacy boxes/scores/classes.
  Legacy has no anchor ID and uses -1 in that column.
- `_metadata.txt`: supplied and verified model SHA, settings, quantization attrs,
  table counts, aggregate parity/compatibility results, and decoder speedup.

Exit 0 always requires selected scalar contract parity. In mode 1 it additionally
requires zero legacy differences: equal counts, matching class/boxes within
1e-3 pixel, and scores within 1e-6. Mode 0 reports legacy discrepancies without
failing its explicit always-sigmoid canonical contract. Inspect the comparisons
before considering production integration.
