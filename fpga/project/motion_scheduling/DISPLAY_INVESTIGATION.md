The historical detview build053c691e05d07408 recorded paint_new_fps=30.00
in its short stats sample. Complete-window mean was26.21fps. The newer
motion-enabled buildde9f18c17a10da4c measured24.03fps in the recent120s pair.
These are different live scenes and cannot establish a code regression alone.

Stored display_regression_evidence.json compares retained raw log windows:

| Metric | Historical observation | Current motion-on observation |
|---|---:|---:|
| HUD rebuilds/s |3.869|8.198|
| HUD upload calls/s |61.906|229.374|
| HUD upload MB/s |8.187|18.153|
| Mean paint ms |11.379|18.169|

Both logs contain active C1/C2 and C5/C6 stereo computations. Hence the
earlier claim that stereo was absent from the faster version is unsupported.
Inference/detection content and preview updates affect the HUD workload.
Current CPU governor isondemand with measured1.8GHz and thermalzone068.125C;
historical clock/temperature evidence is unavailable for a matched comparison.

An isolated optional HUD upload batching candidate is being prepared; current
deployed source and executable remain pinned. A same-binary batch-off/on
experiment retains motion gating, model, sixvideo and stereo. It will measure
whether grouping small GPU uploads reduces paint cost without changing pixels.
30fps is a measurement target, not an accepted result until actually observed.

## Historical/current replay

Both pinned binaries were replayed for121s each with the same inherited
six-camera/stereo configuration, DET_BENCH=0, motion gating0 and HUD batching0.
historical_experiment_receipts.json and historical_experiment_comparison.json
retain evidence. Complete metric-window results:

| Metric | Historical053c691e05d07408 | Current4550d74c95942794 |
|---|---:|---:|
| Fresh composite FPS |24.2670|21.2788|
| Short stats peak FPS |28|25|
| Successful inference/s |14.3280|18.6909|
| Image DMA MB/s |100.7078|99.7810|

Both arms record zero camera read errors and zero inference failures.
This replay does not reproduce the old30fps short sample. It does show the
current binary performing about30.45% more successful inferences while fresh
display rate is12.31% lower in these sequential changing scenes. Higher
inference frequency is a plausible competing workload, not an isolated causal
proof. Metadata reads and HUD batching were disabled, so they cannot directly
account for this specific paired-arm difference.
Current optimized configuration has been restored successfully, PID61092,
with gating1, HUD batching1 and DET_BENCH1. Final pinned start receipt:
log/100h_motion/motion_viewer_experiment_switch_fc96ff489b244b3d8acd3ad5a1deb30e.json.
