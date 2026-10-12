# Local stall diagnostic candidate

This directory is the subagent's entire write scope. Nothing here opens a board
connection or a device, starts a viewer, deploys a program, or changes FPGA state.
The parent session owns all board sampling and any future build/deployment work.

`prepare_diagnostic.py` reconstructs retained text as UTF-8 bytes, preserving the
main file's BOM, and checks **size and SHA256 before writing any source copy**.
It requires the calibration main baseline
`d3a38d77338168b6d95a8731efe99e7b443f08b0dee7bcc831d33bc544a0fd23`
and the retained original executable hash
`0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153`.
It refuses non-unique byte anchors or differing existing output bytes.

`prepared/frozen/` contains all 26 supplied calibration C++/header texts at their
verified hashes, including SDK and retained generated build headers/C++.
`prepared/candidate/` copies supplied `src/` and `sdk/` inputs and applies the
diagnostic change. Retained old moc output remains evidence in `frozen/build/`;
it is not substituted for newly generated output. `prepared/diagnostic.patch`
changes exactly **src/main.cpp and new src/stall_timing.h**.

The retained receipt has a SHA/size for `src/detview.pro`, but no text. No project
file or complete original build manifest is invented. `prepared/manifest.json`
is explicitly **prepared_not_built**, with a pending full compiler-input manifest.
Matching runtime source/binary snapshots and verified disassembly of critical
scopes do not establish a full source-to-original-executable compile binding.

## Preparing and checking

From the workspace root on Windows:

```powershell
python project/per_camera_fps/host_stall/diagnostic/prepare_diagnostic.py
wsl -d Ubuntu-24.04 -- python3 /mnt/c/Users/NineSun/Desktop/ov56401/project/per_camera_fps/host_stall/diagnostic/validate_local.py
```

If changing instrumentation, use a fresh output directory inside `diagnostic/`
with `--output`, and pass that directory to validation via `--prepared`. Existing
prepared source snapshots are protected against silently overwriting changed bytes.
The parent can separately retain the actual `.pro` bytes read-only and pass them
as `--project-file PATH` into a fresh preparation. The script verifies the exact
recorded hash `785fdbf9098de32a5102ca042992f3d43d03d98ef339cd5f3bb73f7a0c5b497f`
and size 606 before using them. This still does not claim a completed build.

`validation/validation.json` retains actual GCC/Qt versions, commands, return
codes, stdout/stderr, native selftest binary hash, and exact extracted scope
hashes. The selftest runs real Linux clocks and real threads; synthetic failure
records test accounting, not a reproduced hardware stall. The validator compiles
both baseline and candidate capture scopes with real Qt headers, without mocks,
and replays the two-file patch into a clean local copy, checking exact bytes.
This is capture-scope syntax validation, not a full target viewer build.
`function_scopes` in the prepared manifest lists both baseline and candidate line
numbers. The added real mutex-wait test also verifies that ioctl records stay
deferred until the attempt finishes, and that a synthetic sleep in the copy
phase remains low-thread-CPU wall time; it does not execute a hardware DMA copy.

## Measurements and accounting

`StallTiming` has no Qt dependency. It uses `CLOCK_MONOTONIC`,
`CLOCK_THREAD_CPUTIME_ID`, and cached Linux `gettid`. Thread-local ioctl counters
separate the six workers and the dispatcher's calls to their shared device.
Full retained source contains one `PangoDev` instance, owned by CameraThread;
one CameraWorker per camera shares its DMA mutex. The six disjoint RX slots and
the separate metadata scratch offset are preserved.

Every completed ioctl, including MAP/H2F and both metadata reads, enters
success/failure count/sum/max windows. Each slow record carries PID/TID, device,
thread ioctl sequence, camera-attempt sequence, address-derived camera/role,
command, requested DDR address/RX offset/bytes captured before the syscall, raw
rc, valid errno flag, raw errno, alarm state and the actual wrapper result.
Negative wrapper result includes the unchanged alarm-forced failure when raw
`rc=0`. Raw errno on a successful syscall is retained but marked invalid.

The syscall has one paired wall/CPU measurement, excluding alarm setup/cancel
and legacy logging. Its endpoints include a small clock-reading/errno-snapshot
cost, measured by the native microbenchmark. Existing wrapper monotonic bounds
include watchdog setup/cancel and the added syscall clock reads. The difference
is wrapper overhead, not pure watchdog CPU. Existing 30-ms fprintf/fflush and
recovery behavior are kept; their logging cost is measured only when invoked.

Each camera attempt measures:

- `read`: writable-buffer preparation through cameraRead's return;
- `dma_wait`: wait to acquire the shared DMA mutex;
- `dma_hold`: acquired mutex through its release, including tags and frame DMA;
- `copy`: exactly the existing pixel-copy call, after releasing the DMA mutex;
- `alloc`: buffer preparation/check/detach, actual QImage creation, and any resize;
- `convert`: the existing RGB565-to-RGB888 loop;
- `sink`: the existing synchronous visionSink publication call;
- `publish_wait` and `publish_hold`: LatestFrames mutex acquisition and update,
  including the error-counter publication on failed attempts.

All outcomes enter camera windows: delivered success, error, no-new-tag, unstable.
They are recorded before the existing 6/25/6/1-ms retry sleep respectively.
Idle/pause loops poll diagnostic windows without sending DMA. The old `[capture]`
success-only output is preserved. New counters repair its failure censoring.
`alloc_n` counts measured scopes; a no-allocation buffer check still counts once.
Startup's initial one-time buffer allocation is outside attempt measurement.

New slow records have a **20-ms** threshold. Windows emit after **at least 5 s**,
on completed attempts/idle polls, and on graceful worker completion. A stalled
call may extend the actual interval far beyond 5 s: use the explicit monotonic
window/attempt bounds, not an assumed five-second denominator. Entire completed
attempts are assigned to their completion window; sums are not clipped occupied
time. Attempt counts and first/last sequence numbers are explicit. Phase scopes
are nested; do not add `read`, `dma_hold`, ioctl and `copy` as exclusive stages.

Tag advances enter the new sum only on successful delivery and only where the
existing worker permits a comparison. No-new/error/unstable samples contribute
no tag advance. `tag_comparisons` is separate from delivered count. Unsigned
32-bit subtraction matches the existing estimator; regressions are counted
separately because wrap/reset cannot be resolved from these counters alone.

New output is deferred until DMA and LatestFrames locks have been released.
There is no new fflush. Stderr lines use its stdio lock so worker records cannot
interleave. Logger wall/CPU cost includes stdio-lock waiting; `logger_previous`
is reported on the next window, excluding the current record to avoid recursive
self-measurement. Ioctl logger cost is shared per thread and repeated alongside
its camera/role buckets; do not add those repeated logger totals. Slow-record
storage is fixed, with capacity for the largest retained ddrRead's 1024 chunks;
an explicit overflow counter prevents silently claiming complete slow detail.

`off_cpu_ns = max(wall - thread_cpu, 0)` and `low_thread_cpu=1` (slow wall and
CPU under 20% of wall) distinguish elapsed time from accounted thread execution.
They do not establish runnable starvation, a kernel wait, MMIO/GPU/FPGA causality,
or IRQ behavior. Clock errors are counted explicitly rather than as zero samples.

## Parent follow-up and limits

No schedstat/proc read is added to the timed paths. The log says
`sched_wait_ns=unmeasured`. The parent can optionally sample the same pinned
PID/starttime and each logged TID's `/proc/PID/task/TID/schedstat`: its first two
fields are scheduled runtime and runnable runqueue wait in nanoseconds, its
third field is a scheduling count. Retain monotonic bounds around those reads
and correlate increments with the exact ioctl/copy interval; do not attribute
another process's historical logs or a missing/dead TID to this source.

The original sixth-consecutive-failure `_exit(3)` remains immediate and can occur
while the DMA mutex is held. That terminal attempt is counted in memory before
the exit, but deferred records/partial windows can be lost; signal/process death
and calls still in flight likewise leave an open tail. A `[recover]` exit is an
explicit censored tail, not proof of zero further failures. Flushing new records
inside the lock or changing recovery ordering would violate this patch's scope.

Before a full candidate build, the parent still needs the actual frozen `.pro`,
toolchain/options/dependency identities, newly generated moc/build inputs,
object hashes and linked diagnostic output hash. Existing binary/module hashes
are evidence, not a new compiler receipt. No target binary has been built or
deployed by this subagent; runtime capture/render/stereo behavior is untested.
