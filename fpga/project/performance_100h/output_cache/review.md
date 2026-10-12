Prepared source only. No SSH, build, executable test, or board action was performed.

Source identity and exact diff
------------------------------

Copied `candidate/detview/src` into this isolated `output_cache/src`. Candidate main and direct-completion build `builds/689a1ad36932d0f5/source/main.cpp` both hash to `6d4087177ad9ba98584fef3eb076bfee4d696aa6e62375e8658d33139d9bb91c`.

Result main SHA256: `1ff7a8400a7a8dd48834ed56a740579ba93efce48a8b79687bf18085efbc71b9`.

Only copied `main.cpp` changed: **45 added / 18 removed lines**, six unified-diff hunks. All 24 other copied files match the pinned candidate byte for byte. Added `src/output_cache_static_audit.py` solely for a repeatable source audit; it is not in `detview.pro`. Added this review. Candidate, baseline, parity, and build sources were not edited.

Exact hunk map (original -> isolated):

| Original lines | Isolated lines | Change |
| --- | --- | --- |
| 1214,6 | 1214,9 | Add per-context `attrs` and `outs` vectors to `CachedModel`. |
| 1273,12 | 1276,32 | Reject zero outputs; query/cache attributes after valid IO count; destroy/report/skip a context on any output-query failure; allocate/reset descriptors only for a fully queried model. |
| 1297,7 | 1320,8 | Pass selected model's attributes and descriptors to `runOnce`. |
| 1366,11 | 1390,21 | Add descriptor reset helper; accept const attributes / mutable descriptors by reference; document benchmark meaning. |
| 1418,22 | 1452,14 | Replace per-frame descriptor allocation with reset; clear on failed get; remove attribute allocation/queries and query timing lap. |
| 1442,6 | 1468,7 | Clear descriptors immediately after the original release call. |

Generate the complete exact diff from the workspace root while candidate remains pinned:

```powershell
@'
from pathlib import Path
import difflib
root = Path('project/performance_100h')
a = (root / 'candidate/detview/src/main.cpp').read_text(encoding='utf-8').splitlines(True)
b = (root / 'output_cache/src/main.cpp').read_text(encoding='utf-8').splitlines(True)
print(''.join(difflib.unified_diff(a, b, fromfile='candidate/main.cpp', tofile='output_cache/main.cpp')))
'@ | python -
```

Behavior and ownership
----------------------

Each successfully initialized worker context first validates one input and nonzero output count (lane models still require one output), then queries each output index once. Attribute query failures now emit `modelLoaded(path, false, "output attr INDEX query RET")`, destroy that new context, and skip insertion. Successful models keep attributes until model reload/shutdown. The source has no dynamic input-shape API calls; this optimization assumes the existing fixed-shape contexts.

The selected `CachedModel` supplies both vectors alongside its context/output count. Vectors are resized only at model load. Reload destroys all old cached contexts before clearing their vectors; thread exit destroys all remaining cached contexts. Execution is synchronous on the inference worker, with no outstanding output buffers during cache changes.

`resetOutputs` zeros every descriptor, then sets its index and `want_float=1`. It runs at load, immediately before every get, immediately after a failed get, and immediately after release. No output buffer pointer survives a completed or failed attempt. Input-set/run failures happen before get and leave the previously cleared descriptors intact. Successful execution still follows input-set -> run -> get -> decode -> release. Failed get still returns without release, preserving the original policy. Release return handling is unchanged. No decoder, lane-mask logic, input path, detection identity, thresholds, NMS, or native INT8 output handling changed. The existing experimental INT8 *input* option is byte-identical.

There are two output-attribute query sites in the application: the independent `probeLaneModel` context and worker model load. The lane probe is unchanged and still queries/releases its own temporary context; it is not an extra query of a cached worker context. There is one production get site and one release site, both in `runOnce`. The DFL/lane synthetic selftests do not exercise cache lifecycle.

DET_BENCH interpretation
------------------------

The `query` field remains in `[infer-split]` for parser compatibility and is zero because per-frame output queries are gone. No replacement lap, synthetic measurement, or subtraction was introduced. Cached-model query/allocation cost now happens during model load, outside per-frame `ms` and the split sum. A cold-start/load-time comparison must measure that cost separately; no speedup is claimed here.

Descriptor reset before get is included in `get`; clearing after release is included in `release`. `decode` measures actual decoding after the get lap, with no query lap. `[tdm_bench] ms` still measures input-set through release plus descriptor clearing. `preprocessing_ms` and completed-FPS definitions are unchanged; successful completions per wall-clock interval continue to reflect any startup stalls within the observed interval. Existing logs should be compared with this revised query meaning documented.

Local evidence
--------------

Ran:

```powershell
python project/performance_100h/output_cache/src/output_cache_static_audit.py
```

Result: PASS. The audit pins the original hash, compares every copied file, checks byte-equivalent input preparation and complete unchanged decoder/trailing regions, inventories every `runOnce` call and output API site, and checks context destruction/skip/reload/shutdown and all descriptor resets in the actual source. A byte search across all other copied C++/header files found no additional RKNN references. Build 689's main hash independently matches the pinned source.

This is static evidence, not compilation, execution, fault-injection coverage, allocator measurement, RKNN ownership verification, or detection parity. No host compiler or target build was invoked because the parent has concurrent compiles underway.

Risks and required target checks
--------------------------------

1. Confirm deployed SDK/toolchain compatibility by building this isolated source after concurrent compiles finish. The later build helper must hash/build this source rather than reuse a pre-cache candidate receipt. It may include the standalone Python audit in its source inventory; it is not compiled by qmake.
2. Confirm cached load-time attributes equal the attributes formerly queried after get for each actual detector and lane model, including dimension/layout metadata. Dynamic-shape model support would require explicit invalidation/requery and is outside this change.
3. Run actual RKNN image parity with this cache implementation: repeat frames within a context, alternate models with different output counts/layouts, reload the same/different selections, switch detector/lane mode, and compare full class/score/coordinate tuples and lane masks. Use nonempty scenes as well as empty ones. Check context reload does not reuse stale attributes or pointers.
4. On target, exercise failed output-attribute queries (first and later indices), IO-query/zero-count failures, failed input-set/run/get followed by retry, and reload/exit after failures. A real SDK call interceptor can record call counts/descriptor state and inject failures while delegating other calls to RKNN. Verify one query per output per accepted worker context, no per-frame query, failed context destroyed exactly once and never used, and zeroed/indexed/float-request descriptors on every get. Static checks here cannot establish those runtime facts.
5. The original failed-get policy assumes the RKNN runtime cleans up any partially acquired outputs on error; resetting application descriptors cannot free undocumented partial allocations. Likewise, ignored release failures remain an existing limitation. Validate deployed SDK ownership/error behavior; this patch intentionally preserves get/release call ordering and policy.
6. Run existing target `--dfl-selftest`, `--lane-selftest`, and `--vision-selftest`, then the actual repeated-frame/model-switch parity above. Existing synthetic decoder tests establish decoder behavior only. Compare `DET_BENCH` steady-state service time and completion rates under matched settings; retain cold-start load cost separately. No performance number is established locally.

Parity harness adaptation required
----------------------------------

The existing `parity/manifest.json`/README pin the earlier candidate build `053c691e05d07408…` / main `f3406080…`; results from that harness cannot validate this change. Do not reuse its prior candidate binary/receipt or treat its pending run as cache parity.

Parent should create a separate harness from this isolated source (or regenerate candidate harness after integrating this patch), applying only the existing early `--parity-selftest` branch. That branch submits through the worker, so the updated worker call already passes `item.attrs`/`item.outs`; the audit confirms this source has no other direct `runOnce` caller to adapt. Any new direct caller must initialize a context, validate IO, check each attribute query, allocate descriptors, and pass both vectors with lifetimes matching that context; it must not pass dummy attributes. Retain preprocessing appropriate to the chosen baseline, unchanged decoders, fixed assets and tuple tolerances. Re-pin complete original/harness inventories, source/model/image hashes, builder adaptations, and build receipts. Run at least three sequential real frames and add model-reload/multi-model/lane coverage. Empty-only agreement remains inconclusive. Existing parity files were left untouched.
