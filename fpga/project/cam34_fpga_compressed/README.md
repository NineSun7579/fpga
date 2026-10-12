# C3/C4 FPGA-side 320x240 transfer

The user requires direct FPGA compressed transfer and 200% display in a persistent six-camera grid. This independent delivery owns FPGA RTL, PDS build, RK3568 viewer and board evidence. Main installed viewer and SPI Flash are preserved.

`source/ov5640/cam34_downsample_2x2.v` emits one RGB565 pixel per 2x2 accepted source block. `source/top.v` sets CAM_DATA_LEN=9600 only for C3/C4. `source/ov5640/ov5640_top.v` inserts reduction before existing DDR packing. `ov5640_reg.v` exposes readonly wire geometry in C3/C4 pages. No full-size C3/C4 pixels are read by the new host; there is no fallback to the software compressor.

`viewer/main.cpp` uses 153600-byte image quotas for zero-based DMA slots 2/3, corresponding compressed tag addresses and 153616-byte frame DMA requests. C1/C2/C5/C6 keep 614400-byte image quotas. `viewer/hdmi_view.h` accepts only two 320x240 RGB565 buffers, joins without resizing, fills 120 padding rows each side and preserves 640x480 model input. GPU draws the actual 320x240 textures in the existing logical 640x480 tiles.

The software-only CPU downsample delivery is a previous implementation and is not the final acceptance target. Its earlier screenshots/FPS cannot prove reduced PCIe transfer. Fresh board artifacts belong under board_evidence.

Commands: Python sim/run_frames.py; Python sim/run_ddr_commit.py; register test sim/tb_cam34_geometry.sv; Python build_viewer.py. PDS image is generated only after both post-route and detailed timing closure. `program_candidate.py` is an explicitly executed SRAM-only rollout, `--rollback` uses the preserved known original image and recorded original process identity/argv. It refuses unknown ownership, changed executable/hash, active PDS/JTAG sessions or timing failure. `trial.py launch --seconds 120`, capture, collect and verify_wire_pixels.py produce measured proof.

Per equal camera frame count, C3/C4 pixel payload decreases 75%; a complete six-camera set decreases 25%. These calculated ratios exclude metadata, polling and PCIe framing. Live payload throughput must come from actual frame counts. No recognition accuracy improvement is claimed without a labeled dataset.
