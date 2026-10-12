Same-binary sequential off/on experiment requested by the user.

Both arms run buildde9f18c17a10da4c binary
610b0cd15ec346b57b314458e4e11a9384bb3bbb783f743af630f0965914ce3c,
wb_v4_combo, sixvideo, texture ring1,30fps cap, no tracking and identical
stereo configuration. DET_BENCH=1 in both arms. The sole changed environment
setting is DETVIEW_MOTION_GATING=0 or1. Normal close, saved settings and
identity-pinned observations are retained by board_viewer.py.

Each arm observes at least120seconds, excludes builds and extra inference,
and keeps exact log boundaries. Complete metric windows must be used;
submit_fps and repeated paints must never be counted as new frame display.
Actual successful completed inference counters must be used. Static-frame
deferrals do not count as throughput improvements. DMA metrics cover
successful requested payload, not physical DDR-controller bandwidth.

This is a sequential live scene comparison, without reproducible camera input.
It can report measured off/on behavior but cannot establish isolated causal
performance gains independently of scene variation or thermal state.
After both arms, the same candidate remains with motion gating enabled.
run_experiment.py retains progress and both source receipt identities;
the final experiment_receipts.json is written only after both observations pass.

## Measured result

Both observations completed successfully; full results and receipt/source
hashes are retained in experiment_comparison.json. Exact complete-window rates:

| Metric | Motion off | Motion on | Change |
|---|---:|---:|---:|
| New display frames/s |19.8428|24.0273|+21.09%|
| Successful completed inference/s |18.6152|9.5914|-48.48%|
| Image DMA requested payload MB/s |99.4371|100.4463|+1.01%|
| Median model service ms |44.8725|45.2320|+0.80%|

Per-camera fresh upload rates improve from18.50–18.98fps to20.93–21.97fps;
camera delivery continues at25.69–28.05fps. Complete recorded windows have
zero inference failures, zero unstable reads and zero camera read errors.
The measurements show better display responsiveness while inference frequency
is reduced by motion scheduling. Model service speed remains approximately
unchanged, and full-image DMA payload does not decrease. This one sequential
live-scene pair is descriptive; scene/thermal differences limit causal claims.
The final successful on-arm start receipt is
log/100h_motion/motion_viewer_experiment_switch_deebbba7732944ecaccdab15f564c407.json;
the on-arm observation is
log/100h_motion/motion_viewer_observe_e695e36920264dd78acd0c8827eb2bf7.json.
Motion gating remains enabled, with the original camview recovery snapshot retained.
