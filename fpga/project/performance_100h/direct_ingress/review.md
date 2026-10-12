Prepared source only. No SSH, build, executable C++ test, parity run, or board action was performed. Concurrent parent cache builds were left untouched.

Source identity and diff
------------------------

Copied all 27 files from `output_cache/src` into this new isolated `direct_ingress/src` after verifying pinned main SHA256 `1ff7a8400a7a8dd48834ed56a740579ba93efce48a8b79687bf18085efbc71b9`.

Result main SHA256: `fb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04`.

Only `src/main.cpp` changed: **61 added / 7 removed lines, 11 unified-diff hunks**. All 26 other source files match `output_cache/src` byte for byte. The inherited `output_cache_static_audit.py` remains unchanged and is not a direct-ingress validation script; its prior main-source expectations do not establish correctness of this new variant. No files outside this owned directory were edited.

Generate the exact diff from the workspace root:

```powershell
@'
from pathlib import Path
import difflib
r = Path('project/performance_100h')
a = (r / 'output_cache/src/main.cpp').read_bytes().decode('utf-8').splitlines(True)
b = (r / 'direct_ingress/src/main.cpp').read_bytes().decode('utf-8').splitlines(True)
print(''.join(difflib.unified_diff(a, b, fromfile='output_cache/main.cpp', tofile='direct_ingress/main.cpp')))
'@ | python -
```

Ingress and configuration audit
-------------------------------

`VisionPipeline::inferenceRequested` now uses an explicit direct connection. Its worker-side callback reads only dedicated mutex-protected ingress enabled/generation fields, and submits the same owned RAW `frame.image` plus generation/frame identity while holding that mutex. It does not read controller pause, source generation, model selection, or GL state on the worker. The gate starts disabled, so startup frames cannot submit before the first committed configuration; an empty model list leaves it disabled.

A rejection calls `VisionPipeline::inferenceFailed` after releasing the ingress mutex. A success queues only an integer generation and monotonic request timestamp via `QMetaObject::invokeMethod(this, lambda, Qt::QueuedConnection)`. The context binds delivery to controller lifetime. The queued GUI callback checks the committed source generation and shutdown state before updating `m_requestRate`; obsolete notifications cannot repopulate a reset rate window. Qt's functor overload requires Qt 5.10 or newer; deployed SDK compatibility remains a required target check.

`closeIngress` is idempotent and supports repeated/nested closure. Closure and submission serialize on the same dedicated mutex. On an enabled-to-disabled transition it clears the inference pending image/flag under the inference mutex before any configuration setter runs. Only `resetVision` calls `openIngress`, as its last operation. Reset asserts the gate is closed, increments source generation once, resets rates/results, configures vision, updates capture generation, and clears all existing overlays. Opening performs a final pending clear under the same lock order, publishes the committed generation, and enables only when neither paused nor shutting down.

The full production setter/configure/reset inventory was searched across copied C++/headers and checked against the actual diff:

| Path | Closure before mutation | Commit |
| --- | --- | --- |
| `handleKey` C | After rejecting rotation mode, before format toggle and `setFormat` | `resetVision` |
| `handleKey` P/Space | Before pause toggle, GL pause setter and capture `setPaused` | `resetVision`; remains closed while paused |
| `onCamChanged` | After index validation, before camera state/GL updates and `setMode` | `resetVision` |
| `onModelChanged` | After index validation, before model state/GL updates and `setModel`/`setFormat` | `resetVision` |
| `startRotation` | After 2–4 model validation, before rotation state/GL updates and `setModels` | `resetVision` |
| `onConfChanged` | Before confidence state and `setConf` | `resetVision` |

There are exactly six production reset call sites and one production `m_vision->configure` site, inside reset. Constructor selection, numeric keys, settings actions, R/V/G keys and public camera/model/rotation entry points route through the audited handlers. Constructor capture sink/video setup occurs before workers start and while the gate is disabled. Standalone vision selftest `configure` calls own independent pipelines and do not use this controller gate. The separate inference selftest worker setup is unchanged.

Lock order is ingress -> inference; the inference worker releases its pending mutex before reload, RKNN work or result emission. Vision request emission occurs after releasing its own mutex, and the rejection path takes the vision mutex only after releasing ingress. No gate lock is held during thread waits or configuration calls into vision. An already dequeued request is not cancelled and may finish under old identity; existing generation/frame checks discard obsolete results. The pending clear prevents an old queued image from being dequeued together with a newly selected model. It does not promise cancellation or immutable per-request confidence/format for work already in flight.

Shutdown and preserved behavior
-------------------------------

Destructor permanently closes ingress, then stops/waits capture, stops/waits vision, and stops/waits inference before deleting any of their objects. Capture's sink remains alive through capture join, controller gate state through vision join, and the stopped vision object's reply methods through inference join. Pending context-bound GUI notifications are removed on QObject destruction. Permanent shutdown prevents reopening.

Inference `stop` now sets `m_stop` and wakes its condition while holding `m_mutex`, then releases that mutex before waiting. This serializes stop with the worker's predicate/wait transition and prevents a lost stop wakeup. `clearPending` touches only the pending image/flag under that same mutex; it does not destroy contexts or cancel active work.

The complete inference run loop and remaining inference-class/decoder region are byte-identical to the pinned cache source, as are capture/DMA pixel conversion and `main` entry/selftest handling. Round-robin context selection, cached output attributes/descriptors, preprocessing, confidence/format semantics, RKNN call ordering, and detector/lane decoders remain intact. Every mode still submits the original RAW RGB image; display/stereo/tracker images are not substituted.

Local evidence and limits
-------------------------

Ran a local Python byte audit against the actual prepared files: PASS. It verified the pinned input hash, equal 27-file inventories, exactly one changed file, all 26 other files byte-identical, complete unchanged worker-run/decoder region, unchanged capture/pixel-conversion prefix and main-entry suffix, and exact diff counts/hash. Read the complete unified diff, inventory of all configuration/setter/gate sites, vision request emission and reply/stop implementations, and inference dequeue/unlock flow. No implementation-mirroring tests were added or run.

This is source evidence only. Compilation, thread scheduling, SDK compatibility, hardware inference parity and performance remain unverified. Existing cache review/runtime requirements still apply to the inherited output-cache implementation.

Required target verification
----------------------------

1. After concurrent builds finish, hash and build this exact isolated source with the deployed Qt/RKNN toolchain. Confirm Qt supports the context-bound functor `invokeMethod` overload (Qt >= 5.10); retain complete source inventory/build receipt and do not reuse a cache-only binary receipt.
2. Run existing DFL, lane, vision, preprocessing and camera selftests using the built variant. Synthetic vision tests do not instantiate this controller, so they cannot establish direct-ingress/configuration/shutdown safety.
3. Exercise camera and video RAW ingress, detector and lane modes, tracking on/off, stereo on/off, and 2–4 model rotation. Compare repeated nonempty/empty RAW frames with the pinned output-cache variant using full detection tuples and lane masks; verify original context order, per-model format and confidence behavior. Any parity harness must be regenerated and repinned for this source.
4. Stress C, P/Space, camera/model changes, confidence changes, and rotation entry/exit while the vision worker emits requests and inference is busy. Deliberately delay GUI event processing to show inference submission continues independently; verify obsolete request-rate notifications and completions do not populate the new generation. Check paused ingress stays disabled, resume advances generation, invalid selections leave a working gate unchanged, and each committed configuration increments generation exactly once.
5. With target tracing or an actual-call interceptor, hold inference before dequeue, change models, and verify the old pending slot is cleared before new-model dequeue. Also hold a request already dequeued across reconfiguration and verify its old identity is rejected on completion. Exercise rejection/failure races to establish that vision pending requests are released without deadlocks. Do not interpret pending clearing as in-flight cancellation.
6. Repeatedly exit during capture, vision request emission, model load, inference completion and condition waiting. Verify capture -> vision -> inference joins complete, no worker uses deleted controller/vision state, and stop wakeup cannot be lost. Capture/driver operations that are already blocked retain their existing stop behavior.
7. Under matched input/model/settings, compare service time, successful completion rates, GUI responsiveness and `npu_request_fps`. Request-rate timestamps now originate at direct acceptance but are still delivered on the GUI thread, so a GUI backlog can temporarily delay its displayed rate. No speedup is claimed from local source inspection.

Local executable validation appendix (2026-10-04)
-------------------------------------------------

This appendix supersedes the earlier **no local executable C++ test** statement for the extracted gate/mailbox seams only. Production `src/main.cpp` was not edited and remains SHA-256 `fb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04`. All work was local; no SSH, remote build, board operation or calibration change occurred.

`local_validation/extract.py` reads production bytes and emits the complete direct inference-request connection, gate open/close methods, inference submit/clear/stop methods, dequeue block and wait/stop predicate. Those exact slices are compiled by `gate_test.cpp`; fake inference/vision objects provide fields, synchronization and observations, without copying the gate algorithm into a behavioral reference. `production_manifest.json` pins source and extracted bytes. The harness was compiled and executed successfully using Qt 6.11.1 / GCC 13.1.0, `-O2 -Wall -Wextra`, with no compiler diagnostics. `local_validation/README.md` details scope and reproduction.

Real threads demonstrated GUI-independent submission and queued rate delivery; 100 forced submit-versus-close races with inference mutex held; close/open pending-clear ordering, stale request rejection and stale rate discard; pause/reset/resume and permanent closure; preserved identity of already-dequeued work; rejection releasing ingress before blocking on a vision reply mutex; four concurrent producers across 200 configuration commits and shutdown; and 200 condition-wait-versus-stop joins. The final run emitted 811 requests in the concurrent-producer case. Result: `LOCAL_GATE_SELFTEST_PASS`, exit 0.

Complete build/test/tool logs and their hashes are in `local_validation/receipt.json`. Final test log SHA-256: `e05eb32241bc0d7bd94ad25a4f2c48ef55eeee8616b973c225fe8b3812a1b349`; compiler/link log: `a801f475a587d21bed75c13ce04323a78a47c5ffd14169c5966f853f6592fb8a`; executable: `61cf4ef8ef3b3b35976ebd1fda49fc72aa42ebd8ee1fb22c07c9e214bcf9ba20`.

Limits remain explicit: the full controller, production reset/configuration handlers/destructor, capture, VisionPipeline pending/history/completion logic, OpenCV/RKNN/RGA SDK and deployed Qt 5 application were **not compiled or executed**. Stale request/rate discard was exercised, but stale inference-completion discard and actual vision pending-map clearing were not. The fake configuration seam advances generation/pause fields; the fake reply records failure identities. Old in-flight identity survives the actual dequeue block, but this is not an end-to-end result rejection or device shutdown test. Qt 6 validates local API compilation/execution only; Qt >= 5.10 target functor compatibility still needs the deployed headers. No main-source refactor is required by the failures observed in these local checks; these checks found none. Required target verification above remains outstanding.
