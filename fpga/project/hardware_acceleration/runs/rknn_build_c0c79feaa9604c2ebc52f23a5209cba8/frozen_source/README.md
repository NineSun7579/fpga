# Private RKNN I/O benchmark

Local WSL compilation and arithmetic/evidence tests have passed. The parent has
executed hardware experiments; the results and limitations below refer to its
downloaded artifacts. This subagent has performed no SSH, board inference,
viewer/DMA/RGA operation, FPGA build or flash. The parent owns board scheduling
and the active acceleration goal. Every source refresh requires a new build;
earlier parent binaries, receipts and artifact directories remain immutable.

All changes and generated artifacts belong to this directory. `prepare.py`
copies the retained SDK, full original `main.cpp`, and `vision_types.h`, then
extracts the actual `InferenceThread` decoder, constants, and RGB565 converter
verbatim. Source slices and complete files are hashed in `prepared/manifest.json`.
RKNN function pointers use `decltype` of the SDK declarations; there is no
handwritten RKNN ABI, substituted decoder, mock NPU or inferred tensor count.

## Prepare locally

```powershell
& C:/Users/NineSun/anaconda3/python.exe project/hardware_acceleration/rknn_io/prepare.py
```

Ship this directory intact to a new private target directory after the parent
releases competing board work. The scripts do not contain SSH credentials or
start remote sessions. Use the actual target library path, resolved by the
parent, for `--lib`; it is hashed before compilation and at runtime.

## Parent commands after board ownership is released

From the copied target directory (example `/userdata/linaro/rknn-io-private`):

```sh
python3 run_target.py inspect --lib /usr/lib/librknnrt.so --out receipts/inspect_01
python3 run_target.py build --board-exclusive --lib /usr/lib/librknnrt.so --out receipts/build_01
python3 run_target.py probe --board-exclusive --lib /usr/lib/librknnrt.so --binary "$PWD/receipts/build_01/rknn_io_bench" --out receipts/probe_01
```

`inspect` prints target/compiler/tool/library/model identities before compilation.
`build` runs qmake and g++ in a fresh directory and records commands, object,
Makefile, compiler header dependencies, linked dependencies and executable hashes.
It uses C++17, matching the retained viewer and its complete `vision_types.h`.
`probe` initializes the pinned model but does not run inference. Read its JSON
stdout for actual API/driver versions and input/output counts, dimensions, data
types, quantization, width/height strides and byte sizes. Both native command 9
(NC1HWC2) and command 11 (NHWC) are queried. The filename's `dfl6` is never used
to assume how many outputs exist. Probe plan eligibility is not certification.

First paired profile:

```sh
python3 run_target.py experiment --board-exclusive --lib /usr/lib/librknnrt.so --binary "$PWD/receipts/build_01/rknn_io_bench" --candidates prealloc --out receipts/prealloc_01
```

After reading the probe and preallocation report, run genuine native NPU memory:

```sh
python3 run_target.py experiment --board-exclusive --lib /usr/lib/librknnrt.so --binary "$PWD/receipts/build_01/rknn_io_bench" --candidates native_io --native-query 9 --dequant-scale fp16 --out receipts/native_io_scale16_01
```

If command 9 layouts are unsupported and command 11 reports a supported layout,
use a new output directory and `--native-query 11`. No silent format fallback is
performed. Native symbol, binding, query and allocation failures are reported
with exact reasons. Unsupported profiles are declined; errors after successful
setup or incorrect outputs fail the experiment. Nothing modifies the viewer.

The opt-in `--dequant-scale fp16` rounds only the queried affine scale to IEEE
binary16, nearest ties to even, then multiplies `(q-zp)` in binary32. The result
is never rounded to binary16. The default remains `fp32`. Each native plan caches
all 256 stored-byte conversions, including INT8 signedness. Identity, plan and
experiment report record the policy; all array and exact tuple gates still apply.
No compiler fast-math dependency is introduced.
Helper API: `NativePlan::make(logical, native, NativePlan::DequantScale::Fp16)`;
omitting the third argument selects `NativePlan::DequantScale::Fp32`.
`convert(buffer, availableBytes, destination)` retains its original signature.

On AArch64 with NEON, `convert()` selects a bounds-validated affine INT8/UINT8
NC1HWC2 path only for batch1 and C2=8. It loads two four-pixel groups with
`vld4_u8`, unzips them into eight pixels per channel, widens/subtracts the zero
point, multiplies by the selected scale in FP32, and stores contiguous logical
channel rows. It computes/stores only active channels in partial blocks such
as the three-channel classifiers. Extra native blocks are skipped; padding
loaded as part of a complete eight-channel pixel never contributes to output.
Logical row width controls every vector load; tails of up to seven pixels use
the scalar LUT. Other layouts and architectures keep the scalar conversion.
`convertScalar(buffer, availableBytes, destination)` is an explicit checked
reference with the same scale policy; `usesNeon()`/`conversionKernel()` report
selection. Benchmark native-plan events record the kernel. No allocator, input,
decoder, certification tolerance or synchronization behavior changes.

## Narrow software input-copy control (parent hardware tested)

`native_io_single_copy` retains the query9 FP16-scale native output path, memory
allocator, context flags0, UINT8 NHWC input with `pass_through=0`, explicit input
and output sync, genuine blocking run, and frozen decoder. Its sole per-frame
data-path change is one `memcpy` of all1228800 preprocessed RGB input bytes,
including gray114 padding, instead of clearing the entire input allocation and
then copying640 rows. Every warmup and measured inference refills its input.
`native_io` retains the original memset-plus-row-copy path as the control.

The pure helper `single_copy_input.h` rejects any input except exact NHWC
1x640x640x3 UINT8, `pass_through=0`, row1920, width/height strides640, exact
1228800-byte queried binding sizes and actual source/allocation sizes, and
nonoverlapping pointer ranges. Unexpected strides, allocation rounding or
dimensions such as641 explicitly decline the candidate before any inference.
The post-`set_io_mem` attributes and actual returned memory size are checked;
there is no inferred layout or use of extra allocation padding.

Each run emits `native_input_copy` with the policy, sizes, binding and source/
destination SHA256 after a setup preflight copy, before warmups or timing. The
runner checks these against the fixture input hash. Certification also hashes
every complete input immediately after its copy and before sync/run, emitting
`native_input_copy_verification` for each of the three completions. Those checks
are retained with the policy event in each report certification entry. Checks
occur only in `--snapshot-all` certification; certification FPS is unused.
Paired timing performs no per-frame input hashing and retains its first/last
output snapshot policy. `--diagnose-native` explicitly declines the new profile.

`--timing-reference baseline|native_io|native_io_single_copy` defaults to `baseline`. Candidate
certification always compares against logical `baseline`; a selected `native_io`
timing control is also certified against that baseline for every fixture. Timed
pairs use the selected reference in the existing AB/BA order and completed-FPS
window. Reports record `timing_reference`, each pair's `reference_profile`, and
the actual profile order. For compatibility, `baseline` and `baseline_stages`
inside a timed comparison hold the selected reference summary/stages; baseline
certification labels keep their original meaning. Native-control certificates
are stored separately in `timing_reference_certifications`. Single-copy/native
timed comparisons additionally require bitwise equality of every retained
first/last FP32 array; exact tuples and logical certification epsilon stay as
before. Selecting the same profile as reference and candidate is rejected.

After the parent's local source freeze and fresh private target build:

```sh
python3 run_target.py build --board-exclusive --lib /usr/lib/librknnrt.so --out receipts/build_single_copy_01
python3 run_target.py experiment --board-exclusive --lib /usr/lib/librknnrt.so --binary receipts/build_single_copy_01/rknn_io_bench --candidates native_io_single_copy --timing-reference native_io --native-query 9 --dequant-scale fp16 --out receipts/single_copy_01
```

Defaults retain all four fixtures, four alternating pairs per fixture, fifty
timed completions per process and five warmups:16 pairs,800 timed completions
per profile. Existing candidate/default scale choices are unchanged; the new
profile requires explicit selection with query9 and `--dequant-scale fp16`.

The parent owns freeze/board scheduling and `prepare.py`. This implementation
does not modify that script, `native_adapter.h` or the current `prepared/` tree.
Before shipment the parent must refresh the manifest for changed benchmark/
runner/README sources and include the two new files `single_copy_input.h` and
`single_copy_selftest.cpp`, alongside previously added test sources. The parent's
current preparation code automatically pins local .h/.cpp/.pro files. Until the
parent runs its freeze, source verification intentionally rejects the old
manifest. The helper is included by the benchmark and compiler dependencies.

Focused local checks live in `validation/single_copy_01/`: optimized and
ASan/UBSan copy tests cover seven complete changing frames, gray114 padding,
source immutability, canaries, and rejection with no memory writes for invalid
sizes/pointers/overlap/layout/strides. The full WSL benchmark and archived
exact-decoder checks are compiled locally, without loading an RKNN runtime.
The runner's local orchestration/evidence checks do not execute inference.
No adapter or large NEON test rerun is required for this software-copy change.

Parent experiment `0a2ca7a3216b431e8aa8b216d98461c9` completed four single-copy
and four native-control baseline certificates with finite, bitwise-equal arrays
and exact tuples, followed by16 alternating pairs and800 measured completions
per profile with zero failures. Mean completed FPS was29.7239 (`native_io`) versus
29.7565 (`native_io_single_copy`); median pair ratio1.01386196 varied from0.956737
to1.040392. This does not establish an additional live-viewer gain: the current
viewer already writes its input with a single memcpy. The older doubled-write
probe supplied the isolated benchmark's original copy control.

## Isolated DMA-heap FD import candidate (local implementation only)

`native_io_fd_import` replaces only the five persistent native RKNN allocations
(one input, four outputs) with dedicated `/dev/dma_heap/system` DMA-BUF FDs,
`mmap(MAP_SHARED)`, and optional `rknn_create_mem_from_fd`. The function pointer
is `decltype` of the exact retained SDK declaration: `(ctx, int32_t fd, void *virt,
uint32_t size, int32_t offset)`, with offset0. `dlsym` is optional for legacy modes;
the candidate requires it and records its address, `dladdr` provider path and
SHA256, which must match the pinned runtime. Context flags stay0; there is no
MEM_ALLOC_OUTSIDE flag, cache-disable flag, tensor flags override or priv_data
mutation. Query9, FP16 scale and the existing AArch64 NEON plans are mandatory.
`native_adapter.h` and `single_copy_input.h` are unchanged.

Every allocation rounds its actual native byte requirement to the queried
`sysconf(_SC_PAGESIZE)`, with overflow and uint32 SDK-size guards. For4K pages,
the25600-byte classifier needs28672 mapped bytes. This changes allocation size,
not native tensor layout: conversion still checks the unchanged plan's byte
requirement and ignores extra allocation padding. Input remains exact1228800
bytes, UINT8 NHWC 1x640x640x3, pass_through0, width/height stride640; the existing
single-copy helper validates the actual imported memory and binding.

Input performs DMA-BUF START_WRITE, one full memcpy, END_WRITE, then the original
RKNN TO_DEVICE sync. The genuine blocking NPU run follows. Each output performs
START_READ, RKNN FROM_DEVICE sync, the existing NEON conversion and END_READ.
CPU access sessions never span a run. Input-copy timing includes write-session
ioctls; output-sync timing includes read-session ioctls and RKNN sync, while
conversion is timed separately. Input preflight and all certification input
hash reads have separate READ sessions. Measured frames add no input hashes.
Diagnostics explicitly decline this profile; no raw diagnostic access bypasses
CPU session brackets. Ioctl EINTR retries and paired END cleanup are bounded.

The SDK documents external allocation but leaves FD/mapping ownership after
`destroy_mem` unspecified. Before candidate setup, a fresh context imports an
unused page, clears it inside a WRITE session, destroys the import, then retires
that context. `fcntl(F_GETFD)` plus `fstat` device/inode identity and whole-map
`mincore` inspect ownership before/after both teardown stages without dereferencing
retired memory. No application FD creation or buffer reuse occurs during this
inspection interval. Unexpected FD closure, replacement or unmapping declines
the profile. Teardown never closes a descriptor whose original identity changed.

`MemorySessionOwnedRAII` owns every FD/mapping and import, including partial
allocations. CPU sessions end before teardown; imports are destroyed only with a
live context, then `rknn_destroy` retires the context, then owned mappings and FDs
are released. A failed run prohibits output access or further execution and
retires the context before freeing buffers. If context destruction fails, owned
resources remain until process exit because completion cannot be proved. There
is no fallback certificate. Import/binding metadata before and after setup/run,
allocation `st_dev`/`st_ino`, four CPU sync attempt/success/failure/EINTR counters
per buffer, all teardown return codes, and ownership snapshots are retained.

The parent must refresh `prepared/manifest.json` and make a fresh private build;
this subagent never edits `prepare.py`, `prepared/`, viewer sources or the parent
`run_rknn.py`. Freeze must include `dma_heap_import.h`,
`dma_heap_import_selftest.cpp`, and `local_tests/fd_import_checks.py`.

```sh
python3 run_target.py build --board-exclusive --lib /usr/lib/librknnrt.so --out receipts/build_fd_import_01
python3 run_target.py experiment --board-exclusive --lib /usr/lib/librknnrt.so --binary receipts/build_fd_import_01/rknn_io_bench --candidates native_io_fd_import --timing-reference native_io_single_copy --native-query 9 --dequant-scale fp16 --out receipts/fd_import_01
```

The runner enforces this single candidate/control, all four pinned fixtures,
four AB/BA rounds per fixture,50 measured iterations and five warmups:16 pairs,
800 measured completions per profile. Both profiles always certify against
legacy `baseline` on all fixtures with input hashes, finite bitwise-equal FP32
arrays, and exact decoder tuples. Timed comparisons also require bitwise equality
of all retained first/last arrays and exact tuples on every completion. Existing
profiles keep their gates. The FD experiment has a1600-second overall deadline
in addition to the existing per-process timeout; the parent also owns its outer
hardware timeout and scheduling.

Local lifecycle tests substitute allocator/import/sync/teardown syscalls and
cover success, partial allocation/mapping/import/bind failure, bounded EINTR,
paired CPU END on copy/sync/conversion errors, failed run retirement, unexpected
FD close/reuse or unmap, and failed context destruction. They establish only
software lifecycle behavior. Full SDK/Qt benchmark compilation and runner gate
tests run locally in WSL. The completed receipt is
`validation/fd_import_03/receipt.json`; earlier directories retain initial checks.
Reproduce in a new directory with
`python3 local_tests/fd_import_checks.py --out validation/fd_import_04`.
This implementation makes no hardware compatibility, certification or speedup
claim. Its measured scope is native NPU allocation plus software CPU sync/copy;
it supplies no FPGA accelerator or RGA path.

## Parent hardware findings and byte diagnostics

Parent runs `892e53bcaad44f23bcb0c617dd6c77dd` (query9) and
`71d108400c43406381ff66fb55cf1490` (query11), under
`project/hardware_acceleration/runs/rknn_experiment_<id>/artifacts/results/`,
failed certification: zero native detections versus two baseline detections.
All four native arrays are constant across all three saved completions. Box
arrays are zero; class arrays are exactly `(-83)*scale` and `(-72)*scale`.
This implies zero in all logical byte positions sampled by the adapter, but
does not prove every padding byte was zero. Queried logical/native quantization
matches. Retained SDK sync directions are TO_DEVICE=1 and FROM_DEVICE=2;
function pointers use their exact declarations, including uint64 create_mem2
size/flags. `mem.flags=1` marks internally allocated memory; it is not independent
proof of cacheability. Output-only `native` timing is explicitly declined for
this pinned model/runtime SHA; diagnostic runs can still investigate it.

Parent direct `native_io` run `4ad952c78e814a14b87784e51ec250de`, in
`project/hardware_acceleration/runs/rknn_diagnose_<id>/artifacts/`, used the same
old binary and produced nonconstant outputs and two close, unequal detections.
Both input and output binding therefore worked in that observed run. Its
`independent_half_scale_check.json` found zero differences across all 536000
logical elements when only the scale was rounded to binary16. Rounding the
result instead failed. This single fixture observation motivates the opt-in
scale policy; new hardware certification across all four fixtures remains required.
These observations do not establish the internal mechanism selecting RKNN I/O
paths or a performance improvement.

Later parent experiment `f39aaaf111014a1fb8ac5e6542fe8e21` certified the scalar
`native_io` FP16-scale implementation on all four fixtures, including all float
and exact tuple gates. Its 16 paired rounds had median FPS ratio
0.9686840585002597, so that implementation did not improve throughput. Native
deblocking/dequantization remained costly (about7–8ms thread CPU). The new NEON
implementation has local ISA parity evidence below and requires a fresh target
build followed by the same four-fixture certification and paired experiment;
the scalar certificate cannot certify a changed executable or imply NEON FPS.

`--diagnose-native` is a separate, untimed, opt-in binary mode. It saves a fresh
unbound baseline's runtime FP32 and `want_float=0` logical quantized bytes, then
poisons output allocations, syncs TO_DEVICE, and performs genuine bound runs.
For the first/last native runs it saves all raw native allocation bytes as `.u8`
**before** `outputs_get`, the adapter `.f32`, optional runtime `want_float=1`
`.bound_get.f32` from that same bound context, and raw bytes after retrieval but
before release. Each blob has a JSON sidecar with SHA256; raw native sidecars
include full queried/binding attributes and their compact-JSON SHA256 values.
Binding events include attribute and pointer/fd/size metadata before and after
`set_io_mem`. API return codes, byte-zero/poison counts, numerical comparisons,
and decoder tuples are emitted even when the normal certification would stop.
Failure of bound `outputs_get` is recorded as unsupported for that retrieval;
diagnostic completion is never a certificate or FPS measurement.

Use the freshly rebuilt executable directly. Example after exclusive board
ownership, from the copied package:

```sh
mkdir receipts/diagnose_fullio_scale16_01
receipts/build_01/rknn_io_bench --mode native_io --diagnose-native --native-allocator cacheable2 --native-query 9 --dequant-scale fp16 --lib /usr/lib/librknnrt.so --model /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn --manifest prepared/manifest.json --fixture prepared/fixtures/bright_baseline_cam1.png --kind png --iterations 3 --prefix receipts/diagnose_fullio_scale16_01/native > receipts/diagnose_fullio_scale16_01/stdout.jsonl 2> receipts/diagnose_fullio_scale16_01/stderr
```

The native diagnostic accepts `--native-allocator create` (`rknn_create_mem`),
`default2` (`rknn_create_mem2` flags0), `cacheable2` (flags1), or `noncacheable2`
(flags2). Use a fresh directory and change one variable per process: allocator,
native query9/11, or mode `native`/`native_io`. Output `pass_through` stays at its
queried value: the retained SDK documents this field for input conversion, so
no unsupported output override is added. All timing profiles retain their
original allocator; allocator overrides require diagnostics. Normal `native_io`
timing still uses no `outputs_get` and requires existing certification gates.

## Compared paths and acceptance

* `baseline`: full UINT8 NHWC RGB888 via `rknn_inputs_set`, genuine blocking
  `rknn_run`, runtime-allocated `want_float=1` outputs, frozen decoder and release.
* `prealloc`: identical input/run/decoder with persistent FP32 output vectors,
  exactly `n_elems * sizeof(float)`, `is_prealloc=1` on every retrieval/release.
  Every descriptor is reset to its user buffer after release.
* `native`: same input submission, genuine run into persistent native output
  memory, explicit FROM_DEVICE cache synchronization, deblocking/dequantization
  into logical FP32 arrays, and the unchanged decoder. No `outputs_get` call.
* `native_io`: native output path plus persistent input memory, UINT8 NHWC and
  `pass_through=0`. The driver must accept model input conversion. Every frame
  copies all 640x640 RGB bytes with the queried width stride and performs
  TO_DEVICE synchronization. Pixels are never changed to INT8 by subtracting128.

The native adapter handles explicit NCHW/NHWC rank4 and NC1HWC2 rank5 metadata,
including channel and reported width padding. Logical rank4 must be NCHW to
match the actual frozen decoder. Rank3 is accepted only with identical explicit
formats/dimensions and contiguous documented storage. It accepts affine INT8 or
UINT8 and unquantized FP32/FP16. Unknown layouts, unsupported ranks, DFP/INT4,
unexpected height stride, element mismatches or unexplained allocation padding
are declined. Hardware parity remains mandatory even for eligible metadata.

Each fixture/profile first completes five warmups and three certification
inferences in freshly loaded processes. Every certification float array is
saved and compared to the baseline first completion; every tuple is compared
exactly (class, score, box, count and order). Defaults are absolute1e-6 plus
relative1e-6 for arrays, and exact equality for detection tuples. If conversion
does not reproduce runtime float outputs and detections, timing is not accepted.

Certified paths then run four paired rounds in AB/BA/AB/BA order, with fresh
process/model reloads, five warmups and fifty timed completions per process.
All detection tuples must remain identical. First and last timed float arrays
are compared quantitatively; the report states this limited array coverage.
The two PNG fixtures also require exact FP32 tuples from their retained,
previously executed target baseline logs (bright fixture: two detections;
candidate fixture: zero). The historical logs and pinned request are frozen in
the package. A changed target result fails with its raw log retained.
It reports actual completed/window FPS, wall and thread CPU milliseconds for
input, input sync, NPU run, float retrieval, output sync, native conversion,
decode, release and retained snapshot copying. Snapshot copying is included in
the completion window; file writes, output hashing, JSON printing and comparison occur
after the window. Logical output attributes are cached in every profile, so
query caching is not credited to preallocation/native memory. Runtime default
cache synchronization remains enabled, and explicit synchronization is timed.
Per-process receipts also retain CPU/NPU frequencies, governors, thermal readings
and host load before/after execution; unavailable sysfs values remain explicit.

Fixtures are retained full640x480 little-endian camera RGB565 captures plus the
previously tested bright baseline and candidate PNG camera crops. PNG fixtures
retain screenshot overlays as recorded in their provenance. Conversion uses the
frozen bit-replication RGB565 code. Every input preserves the full image at y80
with gray114 padding to640x640; source and prepared input hashes are printed.
The model SHA256 is enforced:
`21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`.

Reports are isolated fixture experiments; preprocessing, live DMA scheduling,
video, stereo and viewer work are outside their timing scope. Actual live
completed inference FPS still requires the parent's matched viewer experiment.
There is no speedup claim in this prepared package.

## Local arithmetic and evidence checks

The parent released local WSL builds/tests. These checks do not load RKNN:

```sh
g++ -std=c++11 -Wall -Wextra -pedantic -Iprepared adapter_selftest.cpp -o receipts/adapter_selftest
receipts/adapter_selftest
g++ -std=c++17 -O2 -Wall -Wextra -pedantic -Iprepared scale_selftest.cpp -o receipts/scale_selftest
receipts/scale_selftest
```

This exercises signed/unsigned affine conversion, NC1HWC2 channel/width padding,
NHWC stride, FP16 values and short/unknown-layout rejection. It does not mock
RKNN or certify hardware results. `scale_selftest.cpp` checks binary16 rounding
against the compiler's independent `_Float16` oracle, all finite half values,
all midpoint ties and neighbors, random binary32 values, and every stored byte
for signed/unsigned affine LUTs and representative/extreme scales. Host build
and test logs are retained under `validation/`. `diagnostic_selftest.cpp` tests
comparison, NaN/size handling, immutable raw blobs/attribute hashes, and the
downloaded failure evidence; it includes benchmark code without invoking its
main or constructing the runtime API.
The latest scale checks passed 453953 oracle cases and 22528 LUT cases, both
optimized and with address/undefined-behavior sanitizers. Adapter padding/bounds
checks also passed both builds. The archive test recovers exact integer samples
from the old `native_io` FP32 snapshots, applies the new policy, and reproduces
all 536000 baseline floats and both exact decoder tuples for that one fixture.
It does not certify native memory mapping or replace hardware runs of the new
binary. New host test source hashes are included in the current manifest; the
parent's current preparation script automatically pins local .h/.cpp/.pro files.

`neon_selftest.cpp` compares actual AArch64 NEON execution against the scalar
reference and independently constructed expected logical values. Local QEMU
passed 10245 cases (10244 NEON dispatches) and 22709393 logical elements. Coverage
includes every byte value, signed/unsigned zero-point extremes, FP32/FP16 scale
policies, queried 64/3-channel shapes, extra classifier blocks, partial channels,
widths1/7/8/9/15/16/40/79/80/256, width padding, destination guards, protected input
allocation boundaries, short-buffer rejection, and changed padding sentinels.
All 536000 archived integer samples reconstructed into NC1HWC2 memory also
matched scalar and baseline floats bitwise. Actual native raw memory mapping is
not certified by this reconstruction. The independent scale oracle and existing
adapter arithmetic/rejection tests passed on AArch64 under QEMU as well.

```sh
# From local WSL only; reuse the existing private cross-tools read-only.
python3 verify_neon.py --out validation/neon_03
```

The completed receipt and command/output hashes are in
`validation/neon_02/receipt.json`. No packages were installed or downloaded;
compiler/QEMU binaries in the sibling RGA directory were read-only inputs and
all outputs stayed here. This is CPU instruction emulation, not board/NPU or
performance evidence. Full benchmark compilation and archived exact-decoder
checks also passed on the local x86 WSL host after the NEON change.
