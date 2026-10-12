# Read-only thread scheduling capture, 2026-10-04 22:47:36–22:49:46 host time

Completed 131 samples over 129.977 seconds through one SSH session. Raw JSONL includes board epoch timestamps, uptime, monotonic timestamps, per-thread stat/schedstat/status/wchan, all-process stat, CPU/load/IRQ/VM/memory/frequency/thermal counters, and incremental existing viewer logs. No viewer, FPGA, environment, calibration, sysctl or device changes; no DMA reader, installation or profiling session.

## Identity boundary

Prior PID 95911 was no longer present. Initial exact-name discovery aborted safely; fresh discovery found PID 105250, starttime 20178496, executable `/userdata/detview-hdmifull/detview-hdmifull`, SHA256 `bbf5de26fb2b34d94fef83faa3ab79a4107af456b92aa0cd488d1f586423a3ae`. This differs from the preceding preserved viewer (`0d717a...`). Treat this as a separate current baseline, never as proof about PID 95911 or the earlier rollback.

PID/starttime/executable hash/argv/environment hash and DMA owners matched at both ends. Sole DMA owner was PID 105250 FD16 `/dev/pango_pci_driver`. Active log was `/userdata/50k_link_evidence/hdmifull_20261004_143609.log`. Argv: `--model wb_v4_combo --fullscreen --no-tracking --prefer-hdmifull auto`. No configuration file argument was present, so the argument-file configuration-hash map is empty; implicit configuration equality is NOT established. No new stereo log line appeared; stereo operation is NOT verified for this different baseline. All six cameras and inference were active.

## Observations

No severe slowdown reproduced. 129 panes observations: C1/C2/C3/C4/C5/C6 mean capture FPS 44.44/44.98/26.05/26.05/52.60/52.33; minima 40/43/26/25/46/47. Across 156 camera-window records, logged copy mean 8.853 ms (window means 7.979–10.030); DMA mean 1.270 ms (1.110–1.472); read mean 12.285 ms (10.657–16.082). These are window means, NOT individual-frame maxima. Paint window means 14.745–17.520 ms, camera upload 6.979–8.045 ms.

| TID/name | CPU % of one core | runtime delta s | runnable wait delta s | voluntary / involuntary switches |
|---|---:|---:|---:|---:|
| 105266 QThread | 41.31 | 53.701 | 22.468 | 27946 / 54800 |
| 105267 QThread | 33.74 | 43.853 | 23.079 | 31909 / 42287 |
| 105268 QThread | 20.19 | 26.233 | 19.178 | 38622 / 18846 |
| 105269 QThread | 19.37 | 25.176 | 19.235 | 39315 / 18107 |
| 105270 QThread | 36.55 | 47.508 | 24.182 | 30123 / 47153 |
| 105271 QThread | 36.84 | 47.888 | 24.288 | 29901 / 46853 |
| 105250 main/UI | 39.13 | 50.847 | 15.829 | 8480 / 83203 |
| 105263 InferenceThread | 11.76 | 15.289 | 2.844 | 16120 / 6905 |
| 105265 CameraThread | 4.21 | 5.473 | 12.637 | 105541 / 4270 |
| 105264 VisionPipeline | 1.61 | 2.086 | 2.092 | 13673 / 1026 |
| 105262 mali-cmar-backe | 9.04 | 11.758 | 8.486 | 79095 / 13240 |

The six consecutive QThreads are consistent with six capture workers (each sampled in `pango_cdev_ioctl`, nanosleep, runnable or futex states), but names alone cannot establish camera-to-TID mapping or distinguish conversion/copy suboperations. Each accumulated 148–187 ms of runnable wait per second on average, maximum one-second totals 212–242 ms. These totals comprise multiple waits and are NOT maximum contiguous stalls. Main/UI maximum one-second runnable-wait total was 182 ms. Inference sampled in `rknpu_submit_ioctl` 95/131 times; VisionPipeline sampled in futex wait 121/131. Sampling cannot resolve precise lock ownership or individual copy timing boundaries.

Linux documentation verifies `/proc/PID/schedstat` columns: CPU runtime ns, runqueue wait ns, timeslices (https://docs.kernel.org/scheduler/sched-stats.html). Kernel flag `/proc/sys/kernel/sched_schedstats` was `0`, yet recorded counters increased substantially and runtime agrees with stat CPU ticks. Report measured positive deltas; do not infer from the flag that counters were unavailable. Detailed scheduler statistics may still be gated. `perf` absent; PSI CPU/io/memory interfaces absent. No settings enabled.

Viewer CPU 253.98%, Xorg 37.52%, xfwm4 6.19%. Aggregate CPU idle 18.75%, iowait 0.0295%, softirq 0.1947%; context switches 11912.9/s. Runnable task snapshots mean 5.27, p95 9, maximum 15. No major faults; system pgfault +241. Available memory minimum 1217232 kB (~1.16 GiB), swap zero. CPU frequency predominantly 1992000 kHz, sampled minimum 1608000; GPU fixed 800 MHz, NPU 900 MHz, memory 1560 MHz. SoC 66.875–68.750 C, GPU 61.666–62.777 C. DMA IRQ 1055.57/s; GPU IRQ 586.66/s and 509.22/s. No sustained major-fault, memory shortage, IRQ-cost or frequency-collapse signature during this baseline. Earlier unseen stalls remain unconstrained.

Collector CPU 12.533 s over 130 s (~9.64% of one core; all-process stat estimate 9.09%). This is ~2.4% of four-core aggregate capacity and a measurable observer load; comparisons should acknowledge it. Single-session 1 Hz sampling avoided repeated SSH startup. Full logs and counters are retained for interval-specific analysis.

## Conclusion and focused next step

Current baseline establishes real runnable contention while logged copy means remain near 9 ms. It does NOT establish that scheduling caused the prior 327–871 ms copy labels. No synchronized severe event, no earlier PID identity, no individual copy CPU-clock measurement, and no stereo confirmation prevent that claim. Current C3/C4 ~26 FPS also does not satisfy the original all-six 40/30 objective.

Parent source analysis should map capture workers and the exact copy label scope, including RGB565 conversion, allocation and locks. A focused future diagnostic change would report per-copy wall time AND `CLOCK_THREAD_CPUTIME_ID`, worker TID, lock wait durations and frame sequence into existing logs. During recurrence, low thread CPU delta with large runqueue-wait delta identifies descheduling; low CPU with blocking evidence identifies synchronization; high CPU delta identifies active work. No such source/config change was applied here. Do not disable stereo or cameras to mask the issue.

Artifacts: `thread_stall_20261004_224736.jsonl`, `.summary.json`, `.viewer_logs.jsonl`, `.progress.log`, `.stderr.log`. Collector and analyzer: `project/per_camera_fps/host_stall/`.
