# Independent timing review — run_20261003_192131

Review scope: read-only inspection of `project/motion_100h/build.py`, the archived run inputs/constraints, baseline timing summary, full STA command/log, and one sequential inspection of the existing final `top.rtr`. No PDS launch, parent-build polling, or source edits. Only this findings file was written.

## Immediate blocker: final STA fails

The inspected report is `project/motion_100h/run_20261003_192131/final_sta/report_timing/top.rtr` (2,098,480,827 bytes at both start and end of inspection). It identifies Production timing models and multi-corner analysis, but line 88 says **`Design Summary : Some Constraints Violated.`**

| Check | Clock | WNS (ns) | TNS (ns) | Failing endpoints | Total endpoints |
| --- | --- | ---: | ---: | ---: | ---: |
| Slow setup (report line 105) | ddrphy_sysclk | -0.398 | -52.576 | 309 | 77590 |
| Slow recovery (report line 141) | ddrphy_sysclk | -0.221 | -0.868 | 8 | 13149 |

The scan found 317 `Slack (VIOLATED)` path markers. All other summary rows for setup/hold/recovery/removal at both corners have nonnegative slack and zero failing endpoints. These are actual closure failures, not missing formal evidence. The report summary alone does not identify which detector or existing logic owns each failing path; do not attribute all failures to one instance without its path details.

The preserved baseline `baseline/top_timing_summary_after_hold_fix.txt` reports all constraints met: slow DDR setup +0.796 ns (45722 endpoints), slow DDR recovery +2.666 ns (3155 endpoints). Current DDR endpoint counts increase substantially and both checks now fail. `timing()` at build.py:178–183 should reject the current report because the required all-constraints-met text is absent, before bitgen at line 284. Successful vendor command execution is not timing success (`full_sta.log`:210).

## min_max coverage is established by the actual report

`full_sta.tcl`:2 runs:

```tcl
report_timing -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/motion_100h/work/place_route/top_pnr.adf} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE
```

The report contains nonempty **setup, hold, recovery, removal, and minimum pulse width summaries at both Slow and Fast corners**. Their headings are at report lines 90/112/134/148/162 and 188/210/232/246/260. Thus this command covers all requested check types for this routed database. `-nworst 1` limits reported paths per endpoint; it does not prevent the summary from counting the 309 setup and 8 recovery failures.

Minimum pulse width passes at both corners, including DDR PHY clocks omitted from the setup/hold rows. The narrowest reported pulse margin is +0.011 ns for `phy_dq_clk_0` and `phy_dq_clk_1` (35 and 42 endpoints). The baseline summary has empty pulse-width sections; those empty baseline sections do not invalidate the nonempty pulse checks in this full STA report.

`timing()` explicitly parses/requires the eight setup/hold/recovery/removal sections and checks all 15 baseline capture clocks in setup/hold at each corner (build.py:184–204). It does **not explicitly parse or require pulse-width summaries**. Its all-constraints-met check and violation-marker rejection protect against reported failures, but its returned proof rows do not record pulse coverage. This is a coverage-recording weakness, not a pulse failure in this run. A modest improvement would explicitly validate and retain the two pulse summaries; no formal proof or baseline pulse endpoint matching is necessary.

## New detector and register paths use the correct constrained clock

All six instantiated detectors and their motion record consumers run in the existing AXI domain:

- Archived `inputs/source/top.v`:397 assigns `axi_clk = core_clk`; `inputs/ipcore/ddr3/ddr3.v`:295 assigns `core_clk = ddrphy_sysclk`.
- Archived `inputs/source/constraints/clock.fdc`:28 creates `ddrphy_sysclk` on the DDR PHY GPLL `clkout0`, derived from 40 ns `free_clk` with multiply 84/divide 16: **131.25 MHz / 7.619 ns**.
- Camera 1–4 `ov5640_top.video_clk` connections use `axi_clk` (top.v:1334,1536,1608,1709). Their `u_motion_tap` uses `video_clk` (ov5640_top.v:411), after the FIR/KF output in that same domain (FIR clock at line 390; bypass at 459–461).
- SFP camera 5–6 taps `u_cam5_motion` / `u_cam6_motion` use `axi_clk` directly (top.v:1795,1799), after `sfp_rx_cam_if` crosses into its `i_axi_clk` (top.v:1781).
- The adapter passes its clock directly into `u_detector` (motion_stream_adapter.v:67), including detector history RAM (block_motion_detector.v:68) and control (line 92).
- `prep_regs_u` uses `axi_clk` (top.v:1203), and `u_motion_register_bank` uses that same clock (prep_regs.v:208–209). Motion record transfer to this register bank therefore needs no extra generated clock or result CDC mailbox.

The six registered FDC files appear in the archived project.pds:1335–1355. No active motion-specific false path, max/min delay, or whole-detector hierarchy cut was found in those files. The asynchronous clock-group declarations separate domains but do not cut the same-clock detector/register paths. The report retains `ddrphy_sysclk` in setup, hold, recovery, removal and pulse checks at both corners; its failures demonstrate that this domain is being timed.

**No newly uncovered detector clock or missing detector clock constraint was identified.** The unused `clk_150m` warning (`full_sta.log`:65 / report_timing/run.log:50) explicitly says it has no clock endpoints; it is not the detector clock and is not a reason to require another detector constraint. The inspected report scan did not emit an unconstrained/no-clock diagnostic. This review does not claim a separate exhaustive endpoint audit, but the source clock trace and existing STA summaries provide concrete evidence of the intended AXI-domain coverage.

## Required next action

Resolve the reported slow DDR setup and recovery failures using their endpoint paths and rerun final STA through the parent build flow. Preserve the current timing gate. Do not waive these failures by adding clock groups/false paths to the same-domain motion logic or by accepting the previously passing baseline as current closure.
