# Cooperative path measurement constraints

These are constraints for a board experiment, not a measured FPGA speedup.

The promoted isolated AXI bridge handles one full 640x480 RGB565 frame with
38,400 single-beat reads and 76,800 single-beat writes. Its behavioral-memory
regression takes 950,492 active cycles with the recorded backpressure/final-B
schedule. At an assumed 150 MHz that schedule would take 6.337 ms; PDS component
synthesis does not establish that frequency or the real DDR response schedule.
The standalone letterbox/packer takes 409,602 cycles with continuous ready,
or 2.731 ms at the same assumed frequency. These numbers cannot be substituted
for a full-board end-to-end measurement.

The first isolated paired RK3568 experiment caches the same 30 original road
images before timing. Its candidate profile averages 3.760 ms for CPU bilinear
letterbox/color preparation. The experiment excludes PCIe acquisition, FPGA
preprocessing, live-camera freshness and display. Its strict compatibility
failed until the pinned runtime-conversion profile is independently validated,
so the recorded FPS is diagnostic.

The corrected `pipeline_board_runtime_compatible/` experiment subsequently
passes all strict comparisons and improves completed inference from 14.5684
to 16.0670 FPS. Its camera/PCIe/FPGA exclusions still apply.

Retained PNG images are not established original RGB565 payloads. For example,
packing `frame_01.png`, `frame_07.png` and `frame_30.png` by dropping low channel
bits and expanding them again changes 812,034 / 805,605 / 804,985 channel bytes,
with maximum change seven. Reconstructed RGB565 is a new development input;
it cannot stand in for an original byte-identical camera frame. A cooperative
comparison must retain the actual completed 614,400 RAW bytes and derive both
software and FPGA model inputs from that same leased payload.
The checked board manifests now confirm the images were decoded from one MP4;
the migration's calibration and evaluation samples come from the same clip.
See `../evaluation_frames/PROVENANCE.md` for exact overlap limits.

Replacing one 614,400-byte raw transfer with a 1,228,800-byte model input doubles
the inference payload. Historical 125.99 MB/s DMA including user copy suggests
about 4.877 ms additional transfer cost per replacement; 510.03 MB/s without
copy suggests about 1.205 ms. Those capacity measurements do not describe
simultaneous six-camera operation. Retaining a separate raw display transfer
adds the entire model-input payload rather than just the difference.

For serial acquisition/preprocessing/inference, the measured preprocessing
saving must exceed additional DMA and FPGA work. If producer and consumer
overlap, benchmark sustained completed jobs and latency with real queue/bank
ownership; timing a prepared input alone cannot establish the improvement.
Single-beat bridge transactions also add arbitration cost on top of the pixel
pipeline. Burst staging, direct receive storage or pipeline overlap are
possible optimizations and require their own correctness/board evidence.

Before any cooperative speedup is accepted, verify all of:

- Same pinned RKNN model and byte-identical prepared RGB input for both paths.
- Certified unfiltered RAW source and capture lease that prevents overwrite.
- DDR and host receive allocations proven exclusive at runtime.
- Controller/core reset and owner retirement matching the installed DDR glue.
- Whole-design resources/timing, byte correctness and FPGA operation on board.
- Completed inference count over the same timed workload, latency/CPU use,
  live raw-display freshness and contention recorded for both profiles.

Evidence: `../cooperative_axi/REPORT.md`,
`../raw_preprocess/RESULTS.md`, `cooperative_integration.md`,
`../pipeline_board_benchmark/pipeline_source.json`. The first pipeline benchmark
and the historical DMA capacity records remain unchanged.
