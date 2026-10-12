Prepared locally for output_cache main.cpp `1ff7a8400a7a8dd48834ed56a740579ba93efce48a8b79687bf18085efbc71b9`
against the frozen baseline RKNN harness. No remote connection, build, inference,
or performance measurement was performed during preparation.

The candidate is a complete cache source copy with the exact frozen candidate
`--parity-selftest` branch inserted before camera/controller/window construction.
Model discovery and QApplication setup remain as in the frozen harness; the branch
selects exactly one detection model, before normal model rotation and GUI creation.
Removing that branch recovers every original cache source byte. The baseline is
copied byte for byte from `parity/baseline/src`, verified against its static manifest.
Reference files remain unchanged.

The manifest pins all original and harness source files, complete snapshot digests,
both existing 640x480 scene PNGs, and the known model:
`/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn`
SHA256 `21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`.
Screenshot crops retain labels/overlays. Both harnesses receive identical PNG bytes;
baseline uses its original 640x640 gray114 padding and candidate its raw RGB888 path.

Each scene runs in three fresh processes per harness. Each process loads the fixed
model and completes three ordered inferences on the same scene, exercising initial
load and cached descriptor reuse (nine completions per scene per harness). Starting
a fresh process reconstructs the context and its attributes. This covers fixed-model
reloads; it does not exercise switching among distinct models within one worker.
Cached worker semantics and RKNN native output formats are unchanged. Output remains
the existing `want_float=1` API conversion and decode path, not native tensor buffers.

The runner compares actual post-decode detection tuples with class/count equality,
score absolute tolerance 1e-6 and box tolerance 1e-4 model-input pixels. It requires
exact repeat stability within/across reloads and positive detections somewhere;
empty-only results are inconclusive. Load/inference failures, missing completions,
changed pins and timeouts fail with retained logs. Remote model/scene/binary pins
are checked before and after inference.

After **all cache target compiles, other parity builds/runs, and observations finish**,
the parent may run from the repository root:

```powershell
python project/performance_100h/cache_parity/run_later.py --after-observation --after-compiles --baseline-receipt project/performance_100h/parity/builds/619b6eb48a32ca26/receipt.json
```

The reuse receipt is read only when the parent runs this command. Preparation never
reads the other agent's build receipts, run output or progress. Baseline reuse requires
status built, the full identical source inventory, snapshot digest and a binary hash;
the remote binary must then match that hash. A mismatch fails rather than rebuilding.
If no completed baseline exists, omit `--baseline-receipt` only when no other owner
has claimed its shared content-addressed remote build directory. The underlying
builder refuses existing directories. The cache harness has its own source digest
and builds sequentially with make -j1; local receipts and run outputs live only in
`cache_parity`, and scene uploads use a unique remote `cache_parity_` directory.
The production cache binary from the parent build has no parity branch and cannot
substitute for this harness binary.

Local audit (no board imports or connection):

```powershell
python project/performance_100h/cache_parity/verify_local.py
```

`verification.json` records only source/scene SHA256 and Python syntax checks;
actual RKNN parity remains pending the deferred command.
