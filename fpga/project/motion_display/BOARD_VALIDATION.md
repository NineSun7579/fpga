Build4550d74c95942794 binary
5cbd06e6e4c0a322314be2a5bd986b9bcf45ae0e4cb260ef7483082e04a18023
passed target motion policy84 checks, vision worker, DMA, frame metrics216
checks, DFL and lane tests. target_hud_selftest.log records byte-exact GPU
readback on Mali-G52 OpenGL ES3.2, with HUD_UPLOAD_SELFTEST_PASS.

The1731-rectangle synthetic fixture takes110.271ms for planning on the target,
despite reducing uploads to92. This is not evidence of display acceleration.
Actual complete-window same-binary batch-off/on120s measurements determine
acceptance; if display performance regresses, turn batching off on the same
binary. Keep motion gating, stereo pairs, fullframes, model and logging equal.

run_display_experiment.py retains start/observe receipts in
display_experiment_receipts.json; compare_experiment.py --switch hud validates
the paired measurements. Scene variation remains an experimental limitation.

## Completed board comparison

Both same-binary arms passed identity-pinned120s observations; motion gating,
sixcamera display, two stereo groups and DET_BENCH remain enabled in both.
experiment_comparison.json and paint_comparison.json retain exact rates and
display-stage averages. Off/on results:

| Metric | Off | On |
|---|---:|---:|
| Fresh composite FPS |24.9392|25.2186|
| Successful inference/s |8.3714|8.8448|
| Mean paint ms |16.3523|14.5944|
| HUD upload calls/s |208.8834|104.4764|
| Mean HUD upload stage ms |12.6250|9.1392|
| Image DMA MB/s |101.0594|100.6793|

All recorded complete windows report zero inference failures, unstable frames
and camera read errors. The measured1.12% fresh-display increase is small and
not isolated from live-scene variation; the larger reduction in upload calls
and stage cost supports retaining the opt-in batch path for this deployment.
The target of sustained30fps is NOT achieved by this experiment.
Final on-arm start receipt:
log/100h_motion/motion_viewer_experiment_switch_4f81379ff6e9474fa60f0abb0dcbd549.json.
Snapshot recovery retains original camview; batching can also be toggled off
with board_viewer experiment_switch while keeping the same binary and gating1.
Final screenshotlog/100h_motion/hud_batch_final.png shows sixpanes and detections;
its momentary21fps during moving objects demonstrates ongoing scene sensitivity.
No commits, pushes, FPGA or Flash changes were performed.
