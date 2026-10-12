# YOLOv8 acceleration comparison and FPGA migration status

## Current-board paired benchmark

Executed `run_pipeline_board_benchmark.py --cycles 2` on RK3568 with the
existing full detview still running. This is a standalone inference benchmark sharing board resources with detview;
neither the viewer nor the FPGA bitstream was replaced.

Model: `/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn`.
Pinned SHA256: `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9`.
Both profiles use the same 30 prepared inputs and model. Four paired rounds
alternate AB/BA/AB/BA, with 60 timed completions per block, 240 per profile.

| Profile | Completed inference FPS | Mean completion time |
| --- | ---: | ---: |
| Runtime float output, retained production decoder | 18.9488 | 52.774 ms |
| Direct quantized output, compatible native decoder | 20.9209 | 47.799 ms |

Throughput improves **10.4076%**. Exact scalar/sigmoid checks and semantic
compatibility pass. Certification difference frames and timed difference
completions are both zero. All four paired rounds improve throughput.
Evidence: `benchmark.txt`, pipeline CSV files, `pipeline_source.json`,
`experiment_manifest.json`, and before/after environment snapshots.

These numbers describe completed RK3568 inference, not six-camera display FPS,
MVP model performance, or FPGA arithmetic acceleration. The benchmark shares
resources with the running viewer and does not assume exclusive NPU access.

## FPGA migration: not accepted

Existing migration work resides in
`D:/race/ov56401/project/fpga_v8_migration`, separate from the current cam5-fix
FPGA build. The following retained evidence prevents declaring a successful
full-network FPGA migration or supplying FPGA-on versus FPGA-off FPS:

- `prepare_legacy_backend.py:63` explicitly marks generated assets as
  `HWC16_preparation_assets_not_an_executable_instruction_image`. Its mandatory
  work list includes engine geometry, finish/Add/Concat, ChannelCopy, instruction
  scheduling, DDR ownership and per-layer parity.
- `board_v7/goal_board_validation_01/functional_delivery_execute24/RESULT.json`
  retains `functional_pass=false`. Related receipts report mismatched DDR
  readback and control-register timeouts, followed by transport failures.
- `conv_contract/REPORT.md` records a multiplier pipeline latency defect in
  current arithmetic RTL. An isolated candidate passes vendor simulations;
  that does not constitute a complete mapped network backend.
- `cooperative_linux_transport/README.md` and
  `cooperative_paired_bench/VALIDATION.md` leave physical paired RAW/COOP
  transport acceptance unresolved. Cooperative preprocessing also lacks a
  completed physical inference comparison.

No candidate bitstream was flashed during this comparison. The current working
cam5-fix bitstream remains installed. Completing full FPGA inference requires
the missing backend implementation and hardware acceptance above; this session
has not completed that migration.

After benchmarking, detview PID 17377 remains running, all six cameras are
present, DMA errors are 0/0/0/0/0/0, and sampled NPU load is 13%.
