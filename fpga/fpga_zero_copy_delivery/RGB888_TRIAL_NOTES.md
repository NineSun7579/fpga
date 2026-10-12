# Inference RGB888 experiment

User authorized inference-only FPGA RGB888 comparison after restoration of the
original production display30 image/viewer. RGB565 display is retained.

Fresh original baseline: restore_display30_1791560767926101900, 95 seconds.
C1/C2/C3/C4/C5/C6 mean delivered capture FPS:
44.60/44.84/25.74/25.74/40.33/40.36. RKNN completion3.844/s.

## Standalone paired measurements

run_rgb888_trial.py uses validated batch image81eb0c05… and 10 warmups plus
240 alternating frozen-frame pairs per mode. Conventional input submission
isolates FPGA conversion with inputs_set on both sides; the shared mode also
binds DMA-BUF input. Every input byte and every native output byte must match.
Process CPU and wall-stage timing, frequency and thermal samples are recorded.
The pinned V8 square-input model differs from the live MVP480-high model;
standalone stage rates do not establish live MVP completion rates.

First attempt rgb888_trial_1791561504031982600 failed during compilation because
root filesystem /tmp had120KiB free. Viewer PID2688 remained sole owner and
no candidate programming occurred. Compiler TMPDIR is now placed within the
isolated /userdata trial directory, which has about12GiB free. Retry launched.

## Live viewer integration constraints

Original grid mode selects C1 for inference unless stereo selection overrides it.
Batch mode0 supports all six source cameras; default standalone test uses C5.
Original geometry must be preserved: RGB565 bit replication, RGB order,
square640 padding114 at y80; MVP480 models consume rows80..559.

Do not create a competing PcieSession device owner or reuse its2MiB RX offset:
that overlaps the original six camera slots. An isolated owned-buffer adapter
can use RX tail space0x38a000..0x3ff000 with aligned chunks under the existing
DMA mutex, retaining original model contexts and decoder.

Dispatch-time claim returns a current published frame, not a requested old tag.
Relabeling pixels with an earlier analytics frame identity is invalid. A
tag-checked CPU fallback is possible but may provide little FPGA coverage.
Useful deterministic integration should acquire RAW and RGB under one lease
when inference is due and carry that owned RGB feed with its analytics frame.
Freeze contention and exact all-camera pixel/native-output parity must be
measured. HDMI combined frames and video continue their established CPU route.

Production UI exit is requested through a PID/hash-verified X11 quit event;
device retirement is required before programming. The trial restores original
SRAM imagefcb2e44d… and viewer73613d52… and validates95seconds of health.
