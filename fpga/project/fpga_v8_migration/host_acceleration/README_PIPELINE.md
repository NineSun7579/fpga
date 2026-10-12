# Paired completed-inference benchmark

`pipeline_bench.cpp` is a standalone C++17 executable. It uses the existing
`raw_dfl_native.h`, scalar reference, and frozen production decoder import without
changing the viewer, `bench.cpp`, shared headers, or board runtime. It measures
completed inference pipelines, including preprocessing, instead of repeating
decoders on stored head snapshots. No board connection, upload, or NPU execution
was performed during implementation.

## Build and run on RK3568 (parent schedules execution)

Use the actual SDK header, RKNN runtime, Qt5Core, and OpenCV. Keep the sibling
`../board/board_production_decoder.inc` include available. GCC 9+ is recommended
for C++17 filesystem support. **Never include `test_support` in a board build.**

```sh
SDK=/path/to/directory/containing/rknn_api.h
RKNN_LIB=/path/to/directory/containing/librknnrt.so
g++ -std=c++17 -O3 -fPIC -Wall -Wextra -Wpedantic \
    -fno-fast-math -ffp-contract=off -I"$SDK" pipeline_bench.cpp \
    -L"$RKNN_LIB" -Wl,-rpath,"$RKNN_LIB" -lrknnrt -ldl \
    $(pkg-config --cflags --libs Qt5Core opencv4) -o pipeline_bench

MODEL=/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn
MODEL_SHA=be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9
./pipeline_bench "$MODEL" road_frames.txt result_pipeline "$MODEL_SHA" 2 1
```

CLI: `pipeline_bench MODEL FRAME_LIST PREFIX MODEL_SHA [cycles=2] [productioncompat=1]`.
The final argument accepts exactly `0` or `1`. Default `1` sets
`Config.production_compatibility=true` for both the native decoder and scalar
reference: production's first-scale class-0 sigmoid heuristic, scale encounter
order, and both score-only sorts. Explicit `0` selects the canonical
always-sigmoid contract with deterministic anchor ties. The baseline always uses
the frozen production decoder, and both modes retain every strict semantic check.
The model
basename and caller hash must match the pin above; Qt `QCryptographicHash`
independently hashes the loaded model bytes before RKNN initialization. One
input and six logical heads are queried and validated in every fresh context.
Unsupported shapes, names, quantization, output sizes, or strides abort the run.

`FRAME_LIST` contains one stored road-image path per line. Blank lines and lines
starting with `#` are skipped. Relative paths resolve against the list's directory.
The first 30 images are loaded as original BGR images before timing; fewer than
30 is an error. Each completion freshly resizes the cached original with OpenCV
`INTER_LINEAR`, converts BGR to RGB, and centers it in a 640x640 image filled
with 114. Dimensions use `lround` and padding uses integer division, matching
the existing benchmark's `prepare` path. Input SHA256 values refer to these
prepared RGB bytes. Fixed settings are confidence 0.25, IoU 0.45, top 300,
class-agnostic NMS, and unclipped letterbox coordinates.

## Measurement and certification

A is the genuine baseline: preprocessing, `rknn_inputs_set`, blocking
`rknn_run`, `rknn_outputs_get(want_float=1)`, frozen `ProductionDecoder::decode`,
copying detection tuples into owned results, and `rknn_outputs_release`.
Runtime buffers must contain exactly `n_elems * sizeof(float)` bytes per head;
queried quantized attributes retain their original type/size and describe the
validated logical NCHW mapping used by production decoding.

B performs the same completed pipeline with `want_float=0` and
`NativeDecoder::decode`. The decoder is reused throughout each block, so its
lookup tables initialize during warmup. Both paths copy the same tuple fields
into owned vectors inside the measured window and retire every RKNN output
before proceeding. No raw or float head snapshots are copied in timed loops.

Before timed blocks, certification executes 30 fresh completions per profile
on corresponding prepared inputs. Native outputs are also fully dequantized
outside performance measurement and decoded with the scalar reference using
the same selected `Config` as native. Default certification therefore mirrors
the production heuristic and both score-only sorts; only `productioncompat=0`
uses an always-sigmoid scalar reference. The report separately compares native versus scalar, native
versus fresh runtime-float production results, scalar versus production,
production runtime floats versus production on native-dequantized floats, and
native versus the latter production result. Per-head float errors and the real
production sigmoid heuristic are recorded to distinguish runtime conversion
differences from production scoring/tie behavior.

Four paired rounds run in AB/BA/AB/BA order. Every profile block creates a fresh
context with flags 0, runs exactly 30 full warm completions, then times `30 *
cycles` fresh completions in the same frame sequence. Defaults give 60 timed
completions per block, eight blocks, 240 warm completions and 480 timed
completions overall, plus 60 certification completions. Context creation and
destruction are excluded. Each decoder and context belongs to its block.

Block FPS is completed count divided by `steady_clock` elapsed time from the
start of the first timed completion through the last owned result, output
release, and stored timing sample. The aggregate FPS uses summed block wall
time, and the speed ratio is native aggregate FPS / baseline aggregate FPS.
Per-completion stage statistics cover preprocessing, input submission, blocking
run, output acquisition/validation, decode plus owned copy, release, and total
completion. The total block window includes clock/sample bookkeeping and input
buffer destruction. File/console writes, hashing, parity matching, and sink
consumption occur outside that window; samples are allocated before it.

Linux `CLOCK_THREAD_CPUTIME_ID` captures calling-thread CPU time for every stage
and block. Runtime worker CPU and device work are outside this CPU measure.
Other platforms, or an unavailable clock, explicitly report `unavailable`, JSON
nulls, and empty CSV CPU fields. No wall-time substitute is presented as CPU time.

All timed native completions are matched to the corresponding fresh baseline
completion by round, cycle, and frame after both profile windows have ended.
Compatibility requires equal counts and unordered one-to-one matches with the
same class, every coordinate within 1e-3 pixel, and score within 1e-6. Maximum
bipartite matching handles ambiguous nearby boxes; nonfinite values fail.
Box-only matches expose score discrepancies separately. Certification applies
the same tolerances to the exact scalar comparison.

Exit 0 / `benchmark_status=PASS` requires selected-contract exact scalar certification and
production compatibility on every certification and timed comparison. Any
native/production difference produces `semantic_compatibility=FAIL` and exit 1,
even when native matches the scalar reference. Timings are still reported so
the faster explicitly different contract can be evaluated without claiming a
drop-in production replacement. Invalid argument count returns 2; other errors
return 1. A failed run must not be interpreted as a completed benchmark report.

The viewer is unchanged, and NPU exclusivity is not assumed. Concurrent users,
thermal state, scheduling, and frequency scaling may influence block results.
Reported completed-inference FPS is not viewer/display FPS.

## Report files

- `_source.json`: pinned model provenance, prepared input hashes/paths, settings,
  loaded runtime library path/hash when available on Linux, SDK API/driver and
  compile-library versions, queried attributes and actual output byte counts,
  nested certification comparisons, block stage statistics, paired ratios,
  completion totals, compatibility status, result sink, and the selected
  production compatibility flag and scoring/sorting/scalar contracts.
- `_block_samples.csv`: every timed completion's identifiers, detection count,
  and wall/calling-thread CPU milliseconds for all stages.
- `_block_summary.csv`: min/mean/p50/p95/max per block/stage, block elapsed time,
  actual completed FPS, and native lookup-table counts.
- `_detections.csv`: owned class/score/box tuples for certification profiles and
  every timed completion. Anchor is -1 because comparison uses the common
  production-compatible tuple rather than native-only anchor identity.
- `_parity.csv`: every certification comparison and timed paired comparison,
  counts, strict/box-only matches, unmatched tuples, score differences,
  nonfinite/invalid-class counts, and maximum matched coordinate/score errors.
- `_totals.csv`: summed timed/warm counts and wall/CPU time per profile, aggregate
  completed FPS, native/baseline FPS ratio, both pass/fail decisions, and appended
  `production_compatibility` and `exact_scalar_pass` columns.

Existing report filenames, profile names, and legacy fields remain available
for wrapper compatibility. Historical `exact_sigmoid_pass`,
`certification_exact_sigmoid`, and `exact_sigmoid_parity` names are protocol
aliases for the selected-contract exact scalar check; they do not imply an
always-sigmoid contract when production compatibility is enabled. Use the new
`exact_scalar_pass`, `certification_exact_scalar`, and `exact_scalar_parity`
fields with the recorded `scalar_contract`. Scalar detection rows are named
`production_compatibility_scalar` by default and `exact_sigmoid_scalar` with `0`.

Indices are zero-based. Certification rows use -1 for round/cycle/block fields.
Percentiles use nearest rank. CPU fields remain empty when unavailable. Parent
directories for `PREFIX` must already exist. Existing report paths are replaced.

## Local syntax validation

The installed Windows GCC/Qt6 and the actual SDK header can check this source
against the existing declaration-only OpenCV stand-in:

```powershell
& 'C:/Qt/Tools/mingw1310_64/bin/g++.exe' -std=c++17 -O3 -Wall -Wextra -Wpedantic `
    -fno-fast-math -ffp-contract=off -fsyntax-only `
    -I../../hardware_acceleration/rknn_io/prepared/sdk -Itest_support `
    -IC:/Qt/6.11.1/mingw_64/include -IC:/Qt/6.11.1/mingw_64/include/QtCore `
    pipeline_bench.cpp
```

This verifies source/API usage only. The stand-in has no implementations and
cannot link a real pipeline executable. Real OpenCV linking, Linux timing and
library lookup, RKNN behavior, and board performance require the scheduled real
board build/run.

Local validation passed GCC 13 C++17 syntax checking with the actual SDK header
and Qt6Core. A temporary fixture compiled the unchanged non-OpenCV logic with
mock RKNN functions and real Qt6Core: ambiguous unordered matching, all four
coordinate tolerances, score/class/count failures, NaN/infinity rejection,
owned tuple lifetime, float-output byte sizing, buffer poisoning/retirement,
validation-error cleanup, and no repeated release after a release error all
passed. It also verified the actual pinned model bytes using the source's Qt
hash path and confirmed exact-scalar parity versus a separately reported legacy
difference on mock zero-logit heads. That fixture neither links OpenCV nor uses
the RKNN runtime/NPU; it is not a board-performance result.

## Pinned runtime float conversion

The CLI now accepts an additional final `[runtimecompat=1]` flag, exactly `0|1`.
The default requires the measured RKNN API build
`2.3.0 (c949ad889d@2024-11-07T11:35:33)` and loaded library SHA256
`73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`.
The decoder also checks the six pinned head scales, zero points and types.
Other models/runtime builds must use the default mathematical decoder API or
an independently verified conversion profile.

The first board pipeline experiment used mathematical queried affine conversion
and failed strict production compatibility. The same-run probe in
`../runtime_dequant_probe/` reads raw outputs, releases them, reads runtime float
outputs, releases them and reads raw outputs again, without a second NPU run.
All 16,884,000 raw elements stayed unchanged, and each of 1,214 observed
head/code pairs mapped to a single runtime float value. The independent
`conversion_audit.json` matches the float bits with P3/P4 FP16-rounded scales
and P5 fused multiply-add using a float32-rounded zero-point offset. Unobserved
codes are explicitly recorded; this profile is specific to these artifacts.

The candidate uses these conversions in both class scoring and selected-cell
DFL. The scalar certification uses the same conversion profile. Coordinate and
score tolerances stay at 1e-3 pixel and 1e-6. Header/profile verification and a
new real-board pipeline run are required after the profile change.
