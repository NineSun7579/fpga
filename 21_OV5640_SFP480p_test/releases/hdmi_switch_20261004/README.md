# hdmi_switch_20261004 — PGL50H HDMI switch / dual-OV5640 optical link release

Production-qualified build of the `21_OV5640_SFP480p_test` design: dual OV5640
cameras over SFP optical link (1280x480 RGB565, 100H column packing), MS7200
HDMI input (1080p60/720p), physical KEY1/KEY2 source switching. Validated by
behavioral simulation, PDS routed timing, JTAG programming and on-board GL
screenshots on the RK3568 + MES2L50H board (2026-10-04).

## Layout

- `project/` — rebuildable PDS project (all paths relative)
  - `ov5640_sfp480p_test.pds` — minimal committed project file
  - `build.tcl` — non-interactive build entry
  - `ov5640_sfp480p_test.fdc`, `hdmi_in_mes50hp.fdc`, `timing_cdc.fdc` — constraints
  - `source/rtl/` — production RTL plus generated IP sources (`DDR3_50H`, `hsst_test`,
    `pll`, `rd_fram_buf`, `wr_fram_buf`): generated `.v` + `.idf` IP definitions + IP `rtl/`
  - `sim/` — Questa testbenches and `.do` scripts (see `sim/INTEGRATION.md`, `sim/CAPTURE_FORMATS.md`)
- `receiver/sfp/` — reference receiver RTL (`sfp_video_rx.v`, `sfp_rx_cam_if.v`).
  Simulation scripts expect it at `../../receiver/sfp/` relative to `project/sim`;
  keep this layout when checking out.
- `evidence/` — validation, programming and screenshot evidence (below)

## Build

Pango Design Suite 2022.2-SP6.4, PGL50H-6FBG484. Open `project/ov5640_sfp480p_test.pds`
or run `project/build.tcl`. The committed `.pds` references only relative paths;
compile/device_map/place_route/report_timing output directories regenerate on build.

## Simulation

From `project/sim` (Questa/ModelSim): `do run_hdmi_modes.do`, `do runformat.do`,
`do run_input_pll.do`, `do run_camera_disable.do`, `do run_diagnostic_boot.do`.
Scripts are unchanged from the tested versions; they resolve the receiver at
`../../receiver/sfp/sfp_video_rx.v`.

## Bitstreams (SHA256)

| File | SHA256 | Note |
| --- | --- | --- |
| `evidence/validation_20261004_185843/hdmi_ddr_ov5640_top_PRODUCTION.sbit` | `a4d3b58fc38c6c4247fa1e17e34965cf9d6477e676b173f004097082fdda7a52` | Production default (dual OV5640), timing-clean |
| `evidence/diagnostic/generate_bitstream/hdmi_ddr_ov5640_top.sbit` | `4c45ec6bf4c08771c1096e2a4eead4a5a2b7f1ddcf12818e71e803131eebe1b9` | Diagnostic HDMI boot image |
| `evidence/program_production_default_20261004_190636/cfg_verify_result.sbit` | `bcc1b543b5b9e2280d206a2dfdffd5e136d6d5782fcd6a5a88f7ceb8109486a5` | Verify readback after production program |
| `evidence/program_hdmi_diagnostic_20261004_191533/cfg_verify_result.sbit` | `bcc1b543b5b9e2280d206a2dfdffd5e136d6d5782fcd6a5a88f7ceb8109486a5` | Verify readback recorded in diagnostic program run (identical file) |

## Timing summary

Production build `evidence/validation_20261004_185843` (worst values, see
`timing_closure.md` / `timing_review.json` inside): all setup, hold, recovery,
removal and pulse-width summary sections pass.

| Check | Slow corner | Fast corner |
| --- | ---: | ---: |
| HDMI external input setup | +0.575 ns | +0.411 ns |
| HDMI external input hold | +0.476 ns | +0.994 ns |
| HDMI internal setup | +1.133 ns | +1.854 ns |
| HDMI internal hold | +0.202 ns | +0.116 ns |

Camera local hold passes. The HDMI input analysis assumes a 0..4 ns external
arrival budget at 148.5 MHz; this budget was not externally measured.
Diagnostic build `evidence/diagnostic/validation_20261004_190617` also passes
all timing sections (see its `timing_review.json`).

## Evidence map

- `evidence/validation_20261004_185843/` — production PDS run: routed `.rtr`,
  `timing_review.json`, `timing_path_evidence.json`, `timing_closure.md`,
  `timing_handoff.json`, `build_result.json`, candidate hashes
  (`candidate_before/after.json`), simulation manifests and matching sim logs,
  PRODUCTION bitstream.
- `evidence/diagnostic/validation_20261004_190617/` — diagnostic PDS run (same evidence set).
- `evidence/program_production_default_20261004_190636/`, `evidence/program_hdmi_diagnostic_20261004_191533/`
  — single-PGL50H JTAG scan, 100% program + cfg_verify logs, `programming.json`.
- `evidence/RESULT.md`, `evidence/completed.json` — outcome summary; user-confirmed
  on-board behavior. Note: both files reference the original workspace layout
  (`project/validation_20261004_185843/...`, `E:/build/50k_hdmi_switch/...`); in this
  release those map to `evidence/validation_20261004_185843/...` etc.
- `evidence/*_gl_*.png` — on-board GL screenshots (production camera default and
  received 1080p HDMI desktop, plus C5/C6 crop).
- `evidence/production_default_runtime.log`, `evidence/hdmi_runtime.log` — runtime logs.

Programming was JTAG SRAM (volatile, no flash persistence claim). At release time
the diagnostic image was left loaded on the board; the production artifact above
is the default-camera image.

## Excluded from this release

Build artifacts and scratch: `build_and_exit_*.pds/.tcl/.lock`, PDS run databases
(`compile/`, `device_map/`, `place_route/`, `report_timing/`, `synthesize/`,
`logbackup/`), earlier `validation_*` iterations, `format_sim_*` scratch dirs,
Questa `work_*` libraries, `.wlf`/`transcript` files, `vendor_50k`/`pds_questa`
compiled libraries, IP `example_design/`/`pnr/`/`sim/`/`sim_lib/` trees and IP
`*_tb.v` example testbenches, `*.bak_*` file backups, probe/scratch files
(`stage_probe.*`), and any file larger than 60 MB (none present).
