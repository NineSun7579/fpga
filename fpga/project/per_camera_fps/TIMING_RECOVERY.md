# Timing recovery for CAM3/4 VTS843

The completed isolated build `fpga/build_ny4i9z_e` failed its full final STA gate. PDS returned success for the report command, but `final_sta/report_timing/top.rtr` states **Some Constraints Violated**. No bitstream from that route is acceptable.

The original `strong_pnr.log` gives the actionable cause: `Route-2037` found **15,733** paths needing hold repair, exceeding `-max_hold_violated_paths_num 15000`, so router hold repair stopped with **zero iterations**. Subsequent hold repair ran 96 iterations but left violations on CAM3/4. Raising iterations or weakening clocks would not address that early abort.

| Check | Corner | Clock | Worst slack, ns | Total negative slack, ns | Failing endpoints |
|---|---|---|---:|---:|---:|
| Hold/min | Slow | cmos3_pclk | -0.170 | -1.204 | 12 |
| Hold/min | Slow | cmos4_pclk | -0.332 | -5.626 | 31 |
| Hold/min | Fast | cmos3_pclk | -0.037 | -0.100 | 5 |
| Hold/min | Fast | cmos4_pclk | -0.172 | -1.076 | 18 |

All setup/max summary rows pass in both corners. Slow setup margins are CAM1 2.417 ns, CAM2 0.287 ns, CAM3 3.172 ns, CAM4 3.656 ns, DDR system 0.209 ns, and SFP fabric 0.215 ns. Fast CAM3/4 setup margins are 5.899/6.044 ns. Recovery, removal, and pulse-width summaries pass. The report contains 66 violated path entries; these are corner-specific entries, not 66 distinct physical endpoints.

Worst CAM3 path in both corners: `cam3_ov5640_top/ov5640/cmos_capture/valid_flag/opit_0_L6QL5Q1_perm/CLK` to `cam3_ov5640_top/ov5640/cmos_capture/cmos_data_t[8]/opit_0/D`. Worst CAM4 path in both corners: `cam4_ov5640_top/ov5640/ov5640_cdc/src_drop[8]/opit_0_inv_AQ_perm/CLK` to `cam4_ov5640_top/ov5640/ov5640_cdc/src_drop[9]/opit_0_inv_AQ_perm/CIN`. Other failing paths include capture temporary-data/control logic, VSYNC filtering, raw debug counters, and diagnostic CDC source counters/snapshots. These are same-clock hold paths, not justification for new CDC exceptions.

`fpga/timing_recovery.py` copies the failed candidate inputs, synthesis, map, physical constraints, and prior route into a unique `fpga/recovery_*` directory. It reruns ordinary PNR from the exact map with the original strong PNR options, changing only the repair-path limit to 50,000. Hold targets remain 100/200/200 ps, 500 iterations, multi-corner optimization, slack priority, logic optimization, and `fast_router FALSE`. PDS User Guide command reference pages 251–252 document hold repair and `-gplace_seed`; a different placement seed remains a possible subsequent experiment if this retry cannot pass. The runner retains the inherited default seed.

All six registered constraints, clocks, exceptions, RTL, and protected IP remain unchanged. CAM3/4 remain 20.833 ns (48 MHz), CAM1/2 11.905 ns. The only RTL differences from the frozen motion baseline remain top lines 1571/1672, VTS984 to VTS843. CAM1/2/5/6 at 40 FPS and CAM3/4 at 30 FPS remain the user policy; achieved rates need later board measurement by the parent. No SSH, programming, download, or hardware action is performed.

Before each vendor stage, the runner records tasklist and rejects PDS GUI, shell, backend, or programming processes. It shares the parent's exclusive build lock, requires the parent receipt to be completed/failed at final STA, and uses subprocess argument arrays with `shell=False`. Parent and frozen input hashes are checked throughout. New private source/IP copies prevent regeneration from writing frozen IP.

Pin equality and exact HSST placement/dedicated pad connections must match the frozen route. Each of the four motion detector histories must retain all eight attributed `GTP_DRM36K_E1` single-port READ_BEFORE_WRITE banks in the candidate synthesis report and routed database. Physical depth is 32768 per one-bit bank, implementing the unchanged logical 19200-byte history. The synthesis/map are reused byte-for-byte; the frozen resource review is not claimed as a candidate review.

The final audit requires production timing models, full multi-corner min/max STA, every baseline setup/hold clock, all five timing summary kinds in both corners, nonnegative slack/total and zero failing endpoints, and no violated path anywhere in the complete report. Bitgen runs only after these timing and physical/resource gates pass. Hashes bind the exact final route, report, reused map/synthesis, and candidate bit. A failed audit leaves a blocked receipt and generates no final bitstream.

Commands from the workspace root:

```powershell
python -B project/per_camera_fps/fpga/timing_recovery.py --check
python -B project/per_camera_fps/fpga/timing_recovery.py --vendor-help
python -B project/per_camera_fps/fpga/timing_recovery.py --run
```

Each recovery receipt and stage log is retained in its new directory. `original_failure.json` records all original violated paths and summary rows; `final_sta_analysis.json` records the new report even if it fails. A receipt marked `built_for_parent_review` is a successfully timed artifact, not hardware acceptance.

The first recovery on 2026-10-04 in `fpga/recovery_0s32b_lb` used the saved placement through `-input_place_db_file`. Raising the repair limit enabled six router hold-fix iterations; the subsequent hold stage reported no violated paths. However, its pin report labeled every IO bank `BANKL6`, while ball/site/function/direction fields remained unchanged and site-function names identified multiple physical banks. The strict full-row pin gate correctly rejected this route before STA/bitgen. The original blocked receipt is retained, and the updated runner avoids placement reuse rather than weakening the equality check. Full final STA has not been established for this rejected route.

The subsequent recovery reruns ordinary PNR from the exact candidate map and physical constraints. The parent must not launch another PDS instance while the runner owns `fpga/build.lock`. Runtime vendor help is retained in `fpga/recovery_cr3g2wd2/vendor_help.log` and confirms `-input_place_db_file`, `-max_hold_violated_paths_num`, and `-gplace_seed`.

Preflight passed the completed-parent, frozen-input, candidate-input, project, stage-log and idle-vendor checks. Read-only validation also confirmed all 32 candidate READ_BEFORE_WRITE motion banks and physical DRM placements in the original route, frozen pin/PHY equality, and that the STA gate rejects the original failing report. Script syntax compilation passed without writing bytecode. These checks establish recovery readiness; they do not claim that rerouting has passed timing.

## Verified successful recovery

`fpga/recovery_0so0ct0h/receipt.json` is **built_for_parent_review**. Ordinary PNR from the exact reused candidate map, with only the router repair limit increased from 15000 to 50000, passed full pin equality, HSST site/dedicated-pad equality, and all four motion histories (32 physical READ_BEFORE_WRITE DRM banks). The final production multi-corner min/max report states **All Constraints Met**, with zero failing summary endpoints and no violated paths. The final audit was independently rerun after background completion.

| Corner | CAM3 setup | CAM4 setup | CAM3 hold | CAM4 hold |
|---|---:|---:|---:|---:|
| Slow | 3.270 ns | 4.370 ns | 0.327 ns | 0.280 ns |
| Fast | 5.905 ns | 6.744 ns | 0.258 ns | 0.253 ns |

Global minimum setup slack is 0.209 ns (slow DDR system) / 2.273 ns (fast PCIe pclk); global minimum hold slack is 0.249 ns (slow cam1_sccb) / 0.199 ns (fast pclk_div2). Recovery/removal and pulse-width summaries pass in both corners; minimum pulse-width margin is 0.011 ns. The original clock and exception constraints remain byte-identical.

Generated candidate: `fpga/recovery_0so0ct0h/top.sbit`, 3,791,112 bytes. Bit generation occurred after the positive timing/resource/physical audit. Verified SHA256:

```text
bit     a323d6dfad78aff2a4da975bad7c317dc7f6755d56c6a667c08c694893222a3d
route   b644efa55771d54936c640c26f47d21fbfb117fa3b05f9e86aa88235358fb19c
STA     23807659d378edc39825cd02072d20aca1b3c0ca46558122a6eabb0e1012b5d8
```

Post-completion verification confirmed all protected parent artifacts and reused synthesis/map/PCF hashes, all 694 frozen source/IP input hashes, and the route/report/bit hashes. The candidate build lock has been released. No original/frozen IP was modified, and no hardware deployment, SSH, download, sensor-rate measurement, or motion/video hardware acceptance occurred.

Independent follow-up audit confirmed 112/112 rejected-run rows differ exclusively in field 2 (bank): all were reported as BANKL6. Ball, site, function, direction, and assigned-status differences each count zero; no ports are added or removed. This is evidence of inconsistent bank metadata in the saved-placement flow, not proof that the rejected database is electrically safe. Both recovery Tcl files explicitly load their byte-identical candidate `device_map/top.pcf` via `add_constraint -physical -pcf`; missing PCF loading was not the cause. Ordinary PNR omits `-input_place_db_file` and restores exact frozen full-row equality without relaxing the validator.

The successful run took 20 minutes 5 seconds end to end (14:06:11–14:26:16). The follow-up audit revalidated all 126 final STA summary rows and zero violated paths across the complete 1,854,789,548-byte report, exact PHY equivalence, four histories/32 routed banks, protected/reused hashes, and the 3,791,112-byte bitstream hash. No rerun is pending. Future blocked receipts identify `error_stage` and completion time; pin validation is explicitly marked `pin_verification` rather than leaving a completed reroute as the apparent failing stage. Historical receipts remain untouched.
