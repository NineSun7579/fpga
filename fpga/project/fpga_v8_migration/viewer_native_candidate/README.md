# Native decoder candidate for the recovered HDMI viewer

This is a prepared, isolated source copy of the recovered actual HDMI viewer.
**It is not deployed, and the complete viewer has not been built or run here.**
Only files beneath `viewer_native_candidate/` were written. No SSH, PDS, board
operation or GUI execution was performed. The previously completed
`cooperative_host/` helper is unchanged.

The immutable recovered `inputs/` contains 61 files. Its `main.cpp` is
SHA256 `f91893ec34c014eb4f14a9631dc2ed4d2c248eb69a9e4411b307a05d3261516f`.
The recovered live binary identity is
`0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`.
`src/` copies the 26 original `.cpp`, `.h` and `.pro` compiler inputs, excluding
old objects, executables, Makefile, moc sources/predefines and other qmake output.
Every original copied input except `main.cpp` is byte-exact. The original
`detview.pro` and its compile/link settings are unchanged.

`patch.diff` shows the changes to `main.cpp`. `candidate_manifest.json` lists
every source byte count and SHA256 plus its frozen-base hash. The complete
11,102-byte production decoder from `board/board_production_decoder.inc` occurs
byte-for-byte in both frozen and prepared `main.cpp` (SHA256
`bf268b78139e0489fe00ed5b7f0ef5e6a59fbc49d02b8424a6e5d63369e19700`). The code
following that decoder, including display, motion and CLI parsing, is byte-exact
apart from the two native state declarations. Fullscreen and
`--prefer-hdmifull` handling are unchanged.

## Opt-in and exact supported profile

Native decoding requires **`DET_V8_NATIVE=1`**. Unset, `0`, `true`, whitespace,
and other values leave the existing float path selected. The opt-in does not
select a model or change the viewer's configured default. The latest pinned
**wb_v8_w25_nop2c2f** model must be supplied through the existing model selection;
the default **wb_v4_combo** remains on its existing float decoder even with the
opt-in enabled. A filename alone is never an identity check.

The load-time gate requires all of:

| Identity | Required value |
| --- | --- |
| Actual loaded model bytes SHA256 | `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9` |
| Canonical mapped RKNN library SHA256 | `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885` |
| Queried API string | `2.3.0 (c949ad889d@2024-11-07T11:35:33)` |
| Queried driver string | `0.9.8` |
| Model IO | One RGB640 input, six raw DFL heads, detection with 3 classes |

The Qt adapter reads `/proc/self/maps`, collects mappings named `librknnrt.so`
or versioned variants, resolves each through `QFileInfo::canonicalFilePath`,
requires exactly one canonical existing library, hashes that file through
`QFile`/`QCryptographicHash`, and rechecks mapping paths after hashing. Deleted,
escaped, inaccessible, absent or ambiguous mapped libraries disable native mode.
Environment-provided or compile-time library paths are not used as fingerprints.
This fingerprinting assumes the loaded file is not modified in place while the
process runs; it is not an attestation of every mapped executable byte.

The input attribute is pinned to `images`, index 0, `[1,640,640,3]` NHWC, INT8
affine, zp=-128, scale bits `0x3b808081`, 1,228,800 logical/allocation bytes and
w_stride=640. **The input API stays UINT8 NHWC with pass_through=0**, preserving
the original QImage/preprocessing feed. Existing `DET_INT8_IN` override selects
the original float path and produces a native-guard reason when opt-in is active.

All heads must be INT8 signed, affine, logical NCHW `[1,C,H,W]`, in this exact
queried index/name order. Logical byte/element counts, zero points, binary32 scale
bits, w_stride=0, and recorded allocation sizes are checked:

| Index/name | Shape C,H,W | zp | Scale bits | Packed bytes | Device allocation bytes |
| --- | --- | --- | --- | --- | --- |
| 0 `box_p3` | 64,80,80 | 0 | `3da0a0a1` | 409600 | 409600 |
| 1 `box_p4` | 64,40,40 | -2 | `3d9e27da` | 102400 | 102400 |
| 2 `box_p5` | 64,20,20 | -35 | `3d7c33af` | 25600 | 30720 |
| 3 `cls_p3` | 3,80,80 | 83 | `3d425e3c` | 19200 | 51200 |
| 4 `cls_p4` | 3,40,40 | 69 | `3d50337b` | 4800 | 12800 |
| 5 `cls_p5` | 3,20,20 | 71 | `3d4d63f2` | 1200 | 3840 |

Device allocation padding does not describe `outputs_get` layout. Every native
fetch must have `want_float=0`, no preallocation, a valid indexed buffer, and the
**exact packed logical byte count**. The decoder performs its own format, shape,
signedness, quantization, length and pinned-profile validation before data loads.

## Lifecycle and failures

Each cached model carries its native decision, attributes, decoder and context
serial. Native attributes and SDK versions are queried with checked return codes
on model load only. A load-time guard/query failure logs one reason for that
context and preserves successful model loading through the existing float path;
unrecognized models perform no additional RKNN attribute queries. Model reload
clears the active native pointer, closes previous contexts and destroys cached
decoders. Inference and cache updates remain in the existing inference thread.

The native decoder is configured from `m_conf.load()` (including 0.32), IOU=0.45,
topk=300, `production_compatibility=true` and
`pinned_rknn230_dequantization=true`. It preserves the production sigmoid
heuristic and **both score-only sorts**. Its tables are cached per context and
rebuilt only when confidence changes. No canonical tie-breaker replaces those
sorts. The copied native header is byte-exact with the passing benchmark version:
SHA256 `02e52a2c828229d65637e84dffed0b97e662cf2a6db07bbd328f108508c6e4e4`.
The recovered SDK header is byte-exact SHA256
`c48e11a6f41b451a5fd1e4ad774ea60252d3d94f78bee9b21ea3d21b21deba9a`.

Run-setting/config guards occur before fetching outputs and can use the original
float path with a reason logged once per context. After a successful native
`outputs_get`, `OutputLease` owns the release obligation. Native decode exceptions
and invalid buffers return false and release through RAII. There is no second
run or fallback inference after a failed native fetch/decode. Successful detections
are copied field-by-field from `std::vector<raw_dfl::Detection>` into the viewer's
`QVector<Detection>` before release. Native release errors also return false.
All native output release attempts precede completion increments, metrics and
signals; the existing caller records the failure and emits `inferenceFailed`.

## Review and local validation

```
python run_native_guard_tests.py
python audit_native_candidate.py
```

The test fixture is generated from the actual recorded native session in
`pipeline_board_runtime_compatible/pipeline_source.json`, and checked across its
native sessions. Tests compile the pure C++17 guard plus the copied decoder/SDK,
without Qt or RKNN calls. Coverage includes accepted recorded attributes,
mutations of model/runtime/API/driver/IO/classes and every head field, input
layout, exact truth parsing, mapped-path discovery, independent owned detections,
and release on validation exceptions or release failure. Results and compiler
commands/stdout/hashes are in `artifacts/results.json` and `artifacts/selftest.txt`.
This run passed **160 cases / 250 checks**, with 6 fake releases covering all 36
buffers. Compiler: MSVC x64 19.44.35222.0, C++17 `/O2 /fp:precise /W4 /WX`.

The existing passing 30-frame/240-timed-pair benchmark records bind the unchanged
native decoder to the byte-exact production decoder. They are prior isolated
pipeline evidence; this candidate has not executed those viewer frames. The new
test suite exercises integration guards and cleanup rather than duplicating the
entire established decoder regression.

## Build-only handoff

After the independent frozen baseline rebuild finishes, stage this directory
into a **new isolated directory** on the suitable Linux/RK3568 build host. The
parent session controls that staging/build. The provided helper only builds:

```
sh build_prepared_viewer.sh
```

It runs the unchanged `.pro` through qmake in `artifacts/viewer_build`, overrides
only the output target name to `detview-native-candidate`, builds with make, and
prints the resulting SHA256. It does not run the binary. `QMAKE`, `MAKE`,
`NATIVE_BUILD_JOBS` and a build path beneath the staged candidate directory may
be supplied explicitly. Include the **entire `src/` tree**, not recovered moc or
objects. Complete linking requires the actual compatible Qt/OpenCV/RGA/RKNN
toolchain; the local guard build is not a substitute for it.

Pending evidence: complete candidate viewer build/link, actual runtime/head
measurement in the candidate, semantic/failure validation, and any authorized
viewer measurement. **No candidate viewer FPS gain, deployed support, live parity
or FPGA handoff is claimed.** No GUI execution or deployment is authorized by
this prepared source handoff.
