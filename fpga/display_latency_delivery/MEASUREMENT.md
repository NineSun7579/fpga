# Display latency measurement contract

User objective: reduce live display latency without changing YOLO input pixels,
models or inference scheduling. C5/C6 acceptance requires continuous output;
color is outside the requested scope.

Use six live cameras and MVP_accuracy_round1 fullscreen for each arm. Keep FPGA
SRAM, driver, camera settings, display size, Qt update idle, HUD cadence and
snapshot publication cadence fixed. Do not take screenshots in timed intervals.
Compare the same instrumented binary with candidate behavior disabled/enabled,
in alternating order; record inference throughput and capture/DMA faults.

The existing rawCapturedMs is assigned just after the F2H ioctl completes,
before CPU copy. The existing capturedMs/lastCapturedMs is assigned after CPU
copy, before vision preparation and latest-frame publication. Neither timestamp
represents sensor exposure. CaptureToUpload uses the latter timestamp.

Software comparisons measure these timestamp-to-upload/render/submission ages.
Qt frameSwapped does not prove pixels appeared on the panel. Any hardware camera
to screen claim requires a synchronized optical test (for example a filmed LED
and its displayed image); no optical result should be inferred from software FPS.

Exclude first two complete five-second windows for startup, then use twelve
complete windows per arm. Summarize weighted means and histogram percentiles
where available. A maximum window P95 is explicitly not a pooled P95. Compare
fresh camera upload rates, not only swap FPS; stale repeated paints can otherwise
look like a display improvement.

Deployment at the installed path requires observed improvement, fault-free
continuous output, and unchanged model/input behavior. If a candidate regresses,
leave the working installed application in place and report actual measurements.
