# Host stall code analysis — 2026-10-04

Local-only analysis. No SSH, device access, process control, implementation edits,
or tests. Read workspace/project AGENTS and OpenCode codex-mode SKILL.md plus
its tuning reference. Hindsight was unavailable (connection refused).

## Identity and source binding

The earlier rollback receipts bind calibration-work binary
`b728e1d8f8d041ed4f8eed429edd09aa9f7ee22cd5891f372a262cadc73c70ae`
to a contemporaneous main.cpp hash
`0bdbbd3295e978d4b18a569579b569eb921c84d7112854d06211695344362122`.
See `log/100h_motion/rollback_current_3fb258dc1b1a492a97df74118ca68ff6/capture.json:14`.

The later recovery process is **PID 95911, starttime 20049099**, executable
`/userdata/linaro/detview-calibration-work/build/detview`, SHA256
`0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153`.
Its contemporaneous source hash is
`d3a38d77338168b6d95a8731efe99e7b443f08b0dee7bcc831d33bc544a0fd23`.
Evidence: `log/100h_motion/pll56_optimized_1182d414dcc7436f841bb2170ae93960/capture.json:14`
and `log/100h_motion/readonly_diagnosis_20261004.json`, viewers[95911].
Its exact argv includes `--model wb_v4_combo --fullscreen --no-tracking`
and `--stereo-config /userdata/linaro/detview-calibration-session/trial-meters/stereo_pairs_trial.json`
`--stereo-trial-meters --stereo-scale 0.5 --stereo-interval-ms 250`.
The stereo config SHA is
`7215b0b9085e04ed097539f251a9221fbdde09681e8ca210117a4fb21d864988`.

No main.cpp under local project/ or log/ matches either calibration SHA.
`project/per_camera_fps/swap/src/main.cpp` hashes to
`356a783cccb758a4442ed0eb94df5f6646d0445c802d049bd9fa6da07de6b3b3`.
There is no demonstrated frozen source/build receipt for the calibration binary
in the inspected local evidence. A source hash captured beside an executable
does not itself prove that executable was compiled from that source. Accordingly,
local swap line references below are comparison evidence, not actual-binary attribution.

The newer parent-owned sample
`log/100h_motion/thread_stall_20261004_224736.jsonl:1` identifies **a different
viewer**, PID 105250/starttime 20178496,
`/userdata/detview-hdmifull/detview-hdmifull`, SHA
`bbf5de26fb2b34d94fef83faa3ab79a4107af456b92aa0cd488d1f586423a3ae`,
with `--prefer-hdmifull auto` and no stereo-config argument. Do not use its
thread samples as evidence of PID 95911's earlier stalls. The 224556 sample
starts with an error and no viewer candidates.

## Raw logs change the interpretation

The small frame_dma_ms averages do **not** establish that all DMA attempts were
fast. Raw recovery observation contains long successful-return ioctls with
`alarm=1`, including a metadata read:

| Recovery log line | Completion monotonic seconds | ioctl elapsed ms | Other measured delay |
| --- | ---: | ---: | --- |
| 5 | 200516.818 | 9532.960 | camera 5 copy mean 307.481 ms, line 4 |
| 55 | 200529.180 | 11243.738 | GUI-delay max 11247 ms, line 47 |
| 66 | 200551.561 | 21357.365 | GUI-delay max 21359 ms, line 79 |
| 105 | 200563.821 | 11327.211 | long interval persists after rollback |
| 165 | 200588.302 | 12067.740 | C3 copy mean 424.606 ms, C2 327.735 ms, lines 167–168 |
| 199 | 200610.791 | 21460.594 | C4 copy mean 870.662 ms, line 200 |

All references in this table are to
`log/100h_motion/pll56_deploy_a1b1cf04843840d7b699d2ba769443cc/recovery_observation.log`.
The 21.357-second ioctl at line 66 reads only 16 bytes, so frame payload size
alone cannot explain the gap. GUI and ioctl durations differ by only 1.635 ms
for this interval, and by 3.262 ms for the preceding 11.244-second interval.
This is evidence of concurrent delays in independent execution paths, not proof
of one mutex, CPU contention, a process stop, or an FPGA failure.

Candidate logs also contain stereo compute wall-time outliers: line 95 reports
mean 10954.99 ms/max 21671.27 ms; line 162 reports mean 11024.60 ms/max
21755.11 ms. Ordinary 200–300 ms stereo means in later samples therefore do
not represent every slow-window computation. Empty fixed stereo windows can
be emitted after a long gap; log adjacency alone does not establish concurrent
computation or exact start times.

Display windows run 10.435, 12.315 and 22.386 seconds (recovery lines 13, 36,
68), while paint maxima in those windows are 70.766, 77.907 and 76.387 ms.
The multi-second GUI delays occur outside the measured paint work in the
11.247/21.359-second examples. HUD/paint costs explain baseline display load
but do not by themselves explain these gaps.

## Timing and locks — local comparison only

| Metric / operation | Local swap source scope | Included and excluded |
| --- | --- | --- |
| read_ms | main.cpp:696 timer start through :722 accumulation | Includes writable-buffer preparation, DMA mutex wait, two tag DMAs, full DMA, tag validation, pixel copy. Excludes later RGB conversion, vision ingress, LatestFrames publication and sleep. Successful deliveries only. |
| frame_dma_ms | main.cpp:395–399 | Wall time around full-frame ioctlTmo; excludes initial mutex acquisition and tag reads. Includes watchdog setup/cancel and possible diagnostic logging inside ioctlTmo. |
| copy_ms | main.cpp:405–408 | DMA mutex released first; restart timer, copyCameraPixels, elapsed read. No allocation, RGB conversion, QImage operations or frame-publication lock inside this scope. |
| pixel loop | camera_dma.h:30 | 614400 bytes; AArch64 64-byte ldp/stp loop from mapped RX into already-writable QByteArray. No user-space mutex or allocator in loop. |
| writable-buffer allocation | main.cpp:700 | Shared recycled QByteArray gets fresh uninitialized allocation before frame.data(); inside read_ms, outside copy_ms. |
| RGB conversion | main.cpp:728–744 | QImage allocation and RGB565→RGB888 scanline conversion occur after read_ms/copy_ms accounting and before vision submission. |
| LatestFrames publication | main.cpp:746–758 | Shared frame mutex, QByteArray swap, possible resize, counters. Outside read_ms/copy_ms. |
| display snapshot | main.cpp:919–936 | LatestFrames mutex protects shallow QByteArray snapshots and metadata; no stereo compute or GPU upload here. |
| vision ingress | vision_pipeline.cpp:608–623 | Separate mutex; QImage is shallow-shared into a bounded two-frame mailbox. |
| stereo compute | vision_pipeline.cpp:654–670, :520–522 | Ingress lock scope ends at :659, before stereoWork and DepthEngine::compute. No LatestFrames mutex acquisition here. |

Important censoring detail: local ioctlTmo logs a long ioctl at main.cpp:527
before testing timeoutHit_ at :534. `rc=0 alarm=1` then becomes an error return.
CameraWorker skips timing accumulation for failed reads at :712–716; only :722–723
add successful read/DMA/copy samples. Thus a long timed-out DMA can vanish from
frame_dma_ms while delaying other readers and reducing delivered_fps. Confirm
the same control flow against the matching calibration source before treating
this exact mechanism as established for PID 95911. Its raw alarm/error records
already show why successful-frame averages cannot exclude long DMA attempts.

Local motion metadata, when enabled, has additional fprintf calls under the DMA
mutex (main.cpp:417–434, :475, :492). Local ioctl diagnostic fprintf/fflush also
runs while DMA callers own that mutex (:528–532). A blocked logger could
propagate DMA-lock waits, but cannot directly enter the local unlocked pixel-copy
scope. No evidence establishes logger blocking as the cause.

The actual board-source excerpts retained in readonly_diagnosis confirm the
capture fprintf at remote main.cpp:640, cv::setNumThreads(2) at :3577, stereo
interval parsing at :3717, and a per-camera texture-ring upload path at :2248.
They do not retain cameraRead, the worker timing body, or calibration HUD uploader
implementation. Remote :640 differs from local swap :642 and the reporter body
differs; do not transfer local line numbers to the running calibration source.

## Scheduling and logging evidence

PID 95911 has 20 threads and CPUs_allowed_list 0–3. Main-thread sched shows
policy 0/prio 120; retained per-thread stat records show nice 0 except
InferenceThread nice -19. This asymmetry is real, but its origin and causal
effect during the earlier slow intervals are not established. The local swap
workers use start() without an explicit priority (main.cpp:877); do not infer
the calibration binary's priority policy from it. No per-thread affinity mask
was captured for 95911, so process-level eligibility is not proof that every
thread is pinned identically.

The later 30-second sample reports viewer CPU 264.68%, Xorg 33.47%, aggregate
idle approximately 11.86%, current CPU 1992 MHz, no swap and zero major-fault
delta. It establishes substantial later workload, not CPU/frequency/IRQ state
during the earlier 10–22-second gaps. OpenCV source limit is two, and captured
environment includes no OPENCV_/OMP_/OPENBLAS_ override. Thread count includes
Qt, Mali and NPU support threads, not 20 simultaneous OpenCV compute workers.
Target capture budgets 40/40/30/30/40/40 are requirements; the captured 95911
environment does not contain DETVIEW_CAPTURE_FPS_BY_CAMERA or CAPTURE_MAX_FPS.
Do not claim those caps were active for this calibration run.

Actual /proc/95911/fd/1 and fd/2 both resolve to the recovery .log regular file,
not a pipe. A reader needing to drain a stdout pipe is excluded for this process.
Regular-file writeback/stdio-lock delays remain unmeasured. Reading a file does
not itself imply an exclusive file lock preventing its writer.

## Smallest next diagnostic and fix gate

No implementation fix is justified by the available evidence. Parent owns board
sampling; this analysis performs none. First retain the matching full source,
included headers and build manifest for the selected PID/executable hash, keeping
105250 and 95911 observations separate.

If read-only per-thread CPU/runqueue/wait sampling cannot resolve a recurrent
stall, minimally instrument the matching capture implementation with paired
CLOCK_MONOTONIC and CLOCK_THREAD_CPUTIME_ID deltas around **only** the pixel copy,
plus separate DMA-mutex wait and locked-section wall durations. Count and time
all attempts, including timeout/unstable/no-new-tag outcomes, not only deliveries.
Store count/sum/max in thread-local counters and emit after releasing locks;
report monotonic window bounds and capture-thread TID. Large copy wall with
small thread CPU distinguishes time off CPU from execution, but not the reason
for that absence; correlate it with parent-owned per-thread scheduler sampling.
High copy CPU calls for mapped-memory/frequency profiling instead. Keep RGB,
allocation, publication wait and logger time as separate scopes if read_ms still
has an unexplained residual. std::chrono/QElapsedTimer elapsed-read overhead
alone does not explain hundreds of milliseconds or matching 10–22-second gaps.

Do not change priorities, CPU affinity, OpenCV pools, rendering, capture budgets
or FPGA state merely because the later process is busy. The confirmed finding is
intermittent multi-path wall-time delay with misleading successful-frame averages;
the precise root cause remains unproven.
