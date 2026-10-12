# Local production-byte gate validation

Run from the workspace root:

```powershell
python project/performance_100h/direct_ingress/local_validation/run.py
```

Only Windows-local processes are invoked. Tool paths are pinned to Qt 6.11.1 and MinGW GCC 13.1.0. `run.py` extracts source bytes, records tool versions, runs qmake/make and executes the harness with a 45-second process timeout. Complete combined stdout/stderr is retained per step, with exit codes and SHA-256 values in `receipt.json`. `production_manifest.json` records the main-source hash and each original method/block's line, byte length and hash. Generated `.inc` files consist of the exact source slice plus one trailing newline. No production source is edited.

The compiled production pieces are the entire inference-request connection including its direct callback and queued rate functor; `closeIngress`, `openIngress`, `submit`, `clearPending`, `stop`; the pending dequeue block; and the condition-wait/stop predicate. The scaffold supplies their original field names/types with Qt objects and a fake inference worker. Assertions observe mailbox state and request identities after real synchronized thread interleavings. They do not compare source strings or duplicate the gate algorithm.

Observed checks:

- Worker submission completes while the GUI processes no events; only the integer/timestamp rate notification waits for GUI delivery.
- 100 iterations deliberately hold the inference mutex. The request acquires ingress and blocks in production submit. A competing close cannot complete until the held submit is released; afterwards its pending slot is empty. Repeated close, reopen, both pending clears, fresh acceptance, stale request rejection and stale queued rate discard are checked.
- Actual dequeue bytes preserve an old request's generation/id across pause/reset. Pause rejects fresh requests, resume accepts them, and permanent close prevents reopening and stale GUI rate updates.
- A rejected request blocks on the fake vision reply mutex. Ingress remains available during that wait, and rejection forwards the original identity.
- Four concurrent producers overlap 200 GUI-thread configuration commits (including pause/resume), then keep emitting across permanent close. Paused slots remain empty, any dequeued slot belongs to the current committed generation, shutdown prevents refill, and queued rates are discarded.
- 200 real QThread instances race production stop against the extracted predicate/wait seam; all join. The fake run loop intentionally isolates the wait path and performs no device inference.

`commit` is a controlled test seam: it closes, advances the source generation and pause/rate fields on the GUI thread, and opens. It does **not** compile or execute production `resetVision`, configuration handlers, controller destructor, GL operations, capture, model setters, RKNN/RGA/OpenCV SDK code, or VisionPipeline history/reply logic. Generation rejection of requests and GUI rate notifications is executed; stale inference-completion rejection is **not** executed. The old dequeued identity check establishes the prerequisite for that later production check, not completion correctness. The fake vision reply records failure identity under a mutex; it does not establish the real vision pending-map clearing behavior.

Qt's real typed `connect(..., Qt::DirectConnection)` and context-bound functor `invokeMethod(..., Qt::QueuedConnection)` compile and execute here under Qt 6.11.1. This is not a Qt 5 target build or a complete application build. The production functor overload requires Qt >= 5.10; deployed Qt 5 headers, ABI and SDK integration remain unverified. No board action, calibration change, performance comparison, sanitizer run, hardware parity or end-to-end shutdown claim is made.
