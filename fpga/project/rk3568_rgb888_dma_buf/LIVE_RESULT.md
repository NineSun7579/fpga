# Current live integration results

Original production runtime is restored and active, PID3972 at last verified
receipt deploy_1791596752376736300. SPI Flash unchanged. Work confined to ov56401.

## Correctness and memory

Scheme2 initially requested8MiB TX+8MiB RX, exceeding practical headroom in the
16MiB CMA pool. Original errno was not captured, so the precise initial failure
remains unproven. Minimizing register-write TX to4KiB and preserving8MiB RX
allowed live startup. At least25 Cam1 MVP640x480 same-frame pairs passed exact
921600 input bytes and all434700 native output bytes across6 tensors.

## Exploratory performance

| Metric | Original | Scheme2, global DMA exclusion |
|---|---:|---:|
| Process CPU,30-second sample, multi-core percent |211.81%|181.38%|
| Cam1 deliveredFPS |44.13|35.45|
| Cam2 deliveredFPS |44.50|27.79|
| Cam3 deliveredFPS |25.74|24.12|
| Cam4 deliveredFPS |25.75|24.11|
| Cam5 deliveredFPS |40.20|34.61|
| Cam6 deliveredFPS |40.25|34.75|
| RKNN completions/s |3.91|3.45|
| PaintFPS |31.55|37.13|

CPU samples have equal30s durations; FPS comes from trailing log aggregates
with different window lengths, not a controlled ABAB. CPU is14.37% lower while
capture and inference work also decrease, so no efficiency gain is established.
PaintFPS varies independently of capture; no optical latency measurement exists.
The last100 scheme2 leases average42.04ms. Blocking all DMA during synchronous
inference causes acquisition pauses. Current candidate fails capture
non-regression and is not accepted as the final runtime.

Separate concurrent candidates are being developed to preserve the input-slot
lease while allowing rigorously disjoint camera/scratch DMA. They require new
boundary/lifetime review, input/output parity and live before/after measurement.

Evidence: scheme2_performance_cpu.json, original_after_memory_fix_cpu.json,
corresponding runtime logs/summary.json and deployment parity_markers.log.

## Concurrent candidate trial

deploy_1791598646233805500 passed at least16 same-frame input/native pairs.
Verification-off PID9011 CPU182.14% over30.009s; trailing11 log windows:
capture39.67/9.40/25.53/25.55/38.66/38.72FPS, completion3.18/s, paint33.24FPS.
Cam2 regression remains severe although Cam3-6 approach baseline. This candidate
also fails acceptance. Original restoration started; scheduling/traffic cause
under investigation. Evidence concurrent_performance_* files. These are
exploratory sequential samples, not controlled equal-work performance gains.

## Fair scheduling and shortened hold

Fair scheduling restored Cam2 near44.59FPS; selectedCam1 remained34.76FPS,
completion3.29/s, CPU204.88%. Moving selected RAW copy after FPGA release then
passed >=91 live exact pairs. Its30.007s verification-off sample: CPU209.59%,
six delivered39.02/44.42/25.73/25.69/40.20/40.24FPS, completion3.17/s,
paint32.98FPS. This sample uses its own six aggregate windows. SelectedCam1
improved, but overall non-regression and efficiency requirements still fail.

Current original runtime restored with receiptdeploy_1791602150521334900,
PID17828; health confirms44.59/44.81/25.72/25.71/39.99/40.38FPS,4.00 RKNN
completions/s and zero errors. Phase telemetry and cadence investigation remain
in progress. Older activePID3972/9480/13717 descriptions above are historical.
