# Performance experiments

The authoritative host source is the downloaded running detview source,
baseline/detview/src. Older project/host/detview does not represent the current
board binary. Initial 25.285s of complete display windows show 22.858 fresh
paints/s and 80.75 MB/s camera texture payload; HUD payload is 8.20 MB/s.
Sampled one-second inference completion rates are 13–16/s, service 43–46ms.
These initial samples will be supplemented with a fresh bounded observation.

1. Move letterbox preprocessing into the inference worker; reuse its input
   allocation and initialize only padding. Compare input bytes and detections.
2. Avoid history grayscale work in no-tracking/lane modes after checking all
   history consumers. This reduces RK3568 memory work.
3. Compare texture ring 1/2/3 against baseline using fresh paint rates and
   camera-upload stage latency. Existing code supports this environment option.
4. Evaluate paced full-frame downloads at a measured display/inference demand.
   Current CAM1/2 download ~44fps and CAM5/6 ~40fps while display is ~23fps;
   transferring fewer superseded images could reduce FPGA DDR reads and host
   memory traffic. Keep all six cameras live and enough input cadence for
   completed inference throughput. Count actual full-frame DMA completions,
   bytes and sequence gaps, and compare active scenes as well as static scenes.

Every experiment must retain model/configuration and measure successful
inference completions, fresh displayed frames and frame-DMA bytes. Full-frame
download pacing must be explicitly reported, with latency and camera coverage.
Motion records currently lack DDR-frame association; safe use for transfer
selection needs freshness checks and bounded refresh rather than assuming a
zero bitmap means the currently published DDR frame is unchanged.

Candidate transfer counters record payload from successfully completed DMA
ioctls. Failed-operation partial transfers remain unknown. Camera writes and
host/GPU memory-controller traffic require separate accounting. A zero-error
reduction of frame read payload establishes reduced requested FPGA DDR reads;
it is not a measurement of total physical DDR bandwidth.
Inference windows count successful worker executions across their interval;
use stable model/source/generation observations for throughput comparison.
Configuration switches and stale-result rejection require separate reporting.

Target tests on build456e73cd: preprocessing parity, vision scheduler, DFL,
lane, camera DMA and frame metrics all passed. Review then corrected pacing
to use actual full-frame ioctl admission after mutex acquisition and budget
failed/unstable attempts; capture reports now flush without delivered frames
and before suspension/exit. A new isolated target build is running.

Build053c691e completed, executable 128d9fe60643c80f48cdf20b60dcdae29ba913a5b3e62ce26069ccae5b4281cd.
Original detview stopped successfully with receipt current_viewer_stop_de45893607c44602869690d96369e663.json.
Ring1/no-pacing candidate started receipt candidate_start_bd6b8c97912242459a5da34ef85f5315.json;
120s observation candidate_observe_002fc1bc4fbf4454b6792dc6e1e61159.json succeeds.
Recent complete windows show ~23–24 fresh paints/s and ~14–15 completed
inferences/s, no failures/unstable reads. This alone does not establish all
three goal improvements. Next experiment changes only texture ring 1 -> 3.

Completed pure audit: ring1 fresh23.531/s (+3.52% vs22.730), successful
inference14.105/s vs baseline checkpoint bounds14.522–14.846. Capture payload
129.735 MB/s vs baseline estimated134.755 MB/s; estimation limits retained.
Goal acceptance is not established. Stop sent WM_DELETE successfully but
the old proc reader raced process removal (ESRCH); read-only followup confirms
PID43991 gone. Candidate wrapper now treats disappearing proc files as exited
only after confirming /proc/PID absent, with existing safety tests passing.
Ring3/unrestricted candidate started: candidate_start_ad8b18415bc84242872ee796f92663b9.json.
Its 120s bounded observation is running.

Ring3 unrestricted completed23.127 fresh/s and14.374 successful inference/s.
Ring1/30fps completed26.209 fresh/s (+15.3%) and14.236 inference/s; successful
DMA payload101.514 MB/s vs baselineestimated134.755 MB/s (~24.7% reduction).
Allsixcamera overlap passes, but inference improvement remains unmet.
Nextcandidate changes only inference completion handoff: direct mutex-protected
VisionPipeline reply/failure delivery with GUI callbacks explicitly queued.
Queued request ingress and GUIgeneration/pausechecks remain intact. Isolation
build is running, and frozen original/candidate shared-image RKNN parity
harnesses are executing outside performance observation windows.

Direct-completion build689a1ad36932d0f5 succeeded, binary
ad68c7cbe589d14879ce918c2038d0aac4def57441c7acafd32d54faea783d33.
Target vision/camera-DMA/frame-metrics selftests pass. Viewer switch is pending;
next measured observation must begin only after parity build/RKNN jobs finish.
Follow-up read-only review identifies per-inference output attribute queries
and descriptor allocations; fixed-shape per-context caching is a possible next
single-variable change. Native output types require separate decoder work and
will not be enabled without output equivalence tests.

Direct-completion viewer launched successfully with receipt
candidate_start_6036539dc8b44f439ad3e063c11b4731.json, PID46840. State inspection
finds parity make-j1 plus an independent detview-calibration-work make-j2;
CPU contention lowers delivered/inference rates. No acceptance measurement
will include this build interval. An isolated output-cache candidate is being
prepared without remote compilation, preserving float outputs and decoders.

Output-cache build400bdadbec3e38df succeeded (binary
add0dce703ec468102965d9dcb47c70c09b81be6f24018492f8ae8a1166b7f5d),
vision/DFL/lane target tests pass. Direct-completion observation
candidate_observe_e251ddd137cc4db596862b77f2d19ddc fails immediately: target
viewer absent. Read-only inspection finds another session's calibration viewer
PID48187 using detview-calibration-work/build/detview with calibration-capture.
Candidate log shows graceful partial capture flush and device release before
the other viewer starts. Preserve this calibration owner while finishing
isolated artifacts; do not claim its FPS as candidate evidence.
User asked to continue; metrics-only original build now running. Cache parity
prepared with baseline source/binary reuse and full model/image pins.
