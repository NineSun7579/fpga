# Project Instructions

## Scope

- This directory is the active Pango Fabric Compiler project for Logos2 `PG2L100H-6FBG484` (`-6`), with top module `camera_ddr3_test_top`.
- The design captures OV5640 DVP RGB565 data in `rtl/ov5640_dri/`, crosses into the DDR3 clock domain through the FIFO in `rtl/camera_ddr3_test_top.v`, and writes through the generated `DDR3` controller.
- `impl.pds` is the source of truth for the registered RTL and IP inputs; keep paths relative to this project directory.

## Build And Verify

- Use Pango Fabric Compiler `2022.2-SP6.4` from `C:\pango\PDS_2022.2-SP6.4`.
- Run from this directory with the Fabric Compiler shell/project flow: `source impl.tcl`, then `compile -top_module camera_ddr3_test_top`, `synthesize -ads -selected_syn_tool_opt 2`, `dev_map`, `pnr`, `report_timing`, and `gen_bit_stream`.
- The checked-in generated outputs are placed under `compile/`, `synthesize/`, `device_map/`, `place_route/`, `report_timing/`, and `generate_bitstream/`; inspect their logs for warnings and failures instead of treating an existing artifact as proof of a new build.
- For timing checks, use `constraints/ddr3_target.fdc`; the project currently constrains `sys_clk` at 40.000 ns and `cam_pclk` at 41.667 ns. The latest checked-in timing summary reports all constraints met, but RTL or constraint edits require a fresh full flow.
- No project-level simulation or testbench targets the camera top. The testbenches under `ipcore/` are vendor-IP examples and must be run with their own simulator setup.

## Source And Generated Files

- Hand-edited design sources are under `rtl/` and board timing/pin constraints are under `constraints/`.
- Treat `ipcore/DDR3`, `ipcore/PLL`, `ipcore/rd_fifo`, and `ipcore/wr_fifo` as vendor-generated IP. Change generator settings and regenerate rather than hand-editing generated RTL.
- Treat implementation databases, logs, reports, lock files, and bitstreams as build outputs. Do not use them as RTL source or modify them to fix a design issue.
- The DDR3 interface is 16-bit (`mem_dq[15:0]`, two DQS lanes); do not copy 32-bit wiring or constraints from another project without an explicit adapter and matching pin review.

## Hardware-Specific Constraints

- `sys_clk` is the 25 MHz reference used by the camera I2C setup and DDR3 IP; the top-level OV5640 instance is configured with `CLK_FREQ = 25_000_000`.
- Keep clock-domain crossings and active-low reset behavior explicit. Camera packing runs on `cam_pclk`; DDR3 AXI writes run on the generated `ddr_core_clk`; the FIFO is the intended crossing point.
- Verify DDR3 initialization (`ddr_init_done`), camera initialization (`cam_init_done`), and the physical pin assignments in `constraints/ddr3_target.fdc` after hardware-facing changes.
