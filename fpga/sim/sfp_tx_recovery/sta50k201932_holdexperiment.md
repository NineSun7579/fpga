# Isolated 201932 physical hold experiment

## Completed result

The corrected isolated PNR and separate fresh STA both returned 0, completing at 2026-10-02 21:33:37 after about 11 minutes. The final routed database demonstrates physical repair of the old mapped design's local CMOS1 DIV2 hold violations without changing constraints or inputs. PDS/PNR/TA process check after completion was idle.

| Fresh STA check | Baseline slow | Repaired slow | Baseline fast | Repaired fast |
|---|---:|---:|---:|---:|
| cmos1_pclk_16bit local hold WNS (ns) | -0.150 | +0.199 | -0.179 | +0.103 |
| Local hold failing endpoints | 1 | 0 | 5 | 0 |
| CMOS1 local setup WNS (ns) | +16.766 | +16.590 | +18.794 | +18.746 |
| TX fab-local setup WNS (ns) | +3.351 | +2.845 | +4.686 | +4.327 |

Baseline setup comparisons above use the independently generated `sta50k201932_isolated/fifo_fresh_all.rtr`. CMOS1 endpoint totals differ (baseline 3823, experiment 3800); these are clock-group WNS comparisons, not proof of identical endpoint enumeration. Protected mapped inputs are hash-identical. These settings are a measured physical-repair candidate for the parent's subsequent production mapping, which still requires its own min/max validation.

Fresh evidence is `report_timing/hdmi_ddr_ov5640_top.rtr`, not the inherited root-level baseline `.rtr` files. Its summary lines 107/215 establish hold closure across all 3800 endpoints in the CMOS1 DIV2 group. Individual original failing WADM4 endpoints, all launched by the actual mapped wbin[5] CLK, are:

| Endpoint below u_cam2_merge/u_afifo | Repaired slow (ns) | Repaired fast (ns) |
|---|---:|---:|
| mem_20_6/ram32x1dp/WADM4 | +0.649 | +0.358 |
| mem_29_11/ram32x1dp/WADM4 | +0.517 | +0.288 |
| mem_29_14/ram32x1dp/WADM4 | +0.797 | +0.449 |
| mem_17_8/ram32x1dp/WADM4 | +0.782 | +0.452 |
| mem_29_8/ram32x1dp/WADM4 | +0.636 | +0.331 |

`hold_path_evidence.json` records 390 wbin5->WADM4 min paths per corner and exact report lines. Each of the original failing endpoints still reports 0.200 ns clock uncertainty. Reproduce extraction with `python project/tools/analyze_sta50k_holdexperiment.py`.

Important vendor artifact ordering: `place_route/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt` is an intermediate snapshot and still shows -0.188/-0.189 ns hold violations. Later `place_route/run.log:318-322` records another hold-fix pass, seven iterations, and final +199/+103 ps. The separately generated STA of the final routed ADF independently confirms those final values. Do not present the intermediate summary as the final result.

Final routed ADF SHA-256: `a4fea4dc0012e49f488ff1766cb15c287363c96e033659d49f2035ddd00a63b1`.
Fresh report SHA-256: `efeff24c0cf363f9e8028299e4557d4db0d711d4e86fd200a4934822def48410`.
Mapped input SHA-256: `ede336f327665065b5d79ba4d578896648cc583babab249a7f7298bd09ee504c`.

Integrity: all 319 protected source/IP/build.pds/compile/synthesize/device_map files unchanged; original before/after audit found zero changed, added or missing files during the corrected run. No production file or IP was edited. Other old-map setup/recovery violations remain, so this is physical hold repair evidence only and does not approve a release or demonstrate closure of the parent's new mapped design.

Runner: `project/tools/run_sta50k_holdexperiment.py`.
Vendor Tcl: `project/tools/sta50k_holdexperiment.tcl`.
Distinct output root: `C:/Users/NineSun/AppData/Local/Temp/sta50k_holdexperiment`.

The first submission failed at Tcl parsing before physical execution: an immediate file-existence check after the registered PNR command ran before deferred PNR execution. The corrected runner uses separate PNR and report Tcl invocations. It was resubmitted in background notification mode with `--resume --run --timeout-seconds 3000`; physical results are pending. The runner refuses to overwrite an existing experiment unless explicitly resuming; resume verifies all protected copied inputs. The initial copy verified every snapshot file copied from `sta50k201932_isolated` and checked the documented baseline routed ADF hash. Only the new copy's old place_route/report_timing directories are removed. It never opens or writes the original project. Concurrent parent edits are recorded separately by its original-file audit.

PDS process checks were idle during preparation. The runner checks again immediately before launch; any initial or current busy PDS/PNR/TA process produces `prepared_busy_no_launch` instead of launching. Other agents must not start PDS while this background experiment is active. There is no busy-loop or completion polling. The timeout kills only this subprocess tree.

All PNR arguments are confirmed by the preserved runtime `pnr -help` in `sta50k201932_isolated/fifo_help_shell.log`; the documented command is reproduced in `sta50k201932_fifo_candidate.md`. Thresholds are ps. Architecture is explicitly Logos / PGL50H / -6 / FBG484, matching this old 50K mapped design, not the separate Logos2 project. No compile, synthesis, device mapping, bitstream generation, source/IP edits or FDC edits are requested.

The experiment enables placement and route hold repair, 500 iterations, 100 ps path threshold, 200 ps clock-path thresholds, up to 15000 violated paths, multi-corner optimization and non-fast routing. A successful PNR is followed by fresh `report_timing -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE` against the resulting routed ADF. Existing timing constraints, including 0.200 ns hold uncertainty, remain intact.

Evaluation must select actual cmos1_pclk_16bit local hold paths by reported clocks and WADM endpoints; clock-name filter options were unreliable in the earlier report. The baseline worst path is wbin[5] Q0 -> mem_20_6/ram32x1dp/WADM4, -0.150 ns slow / -0.179 ns fast. Four additional fast failures are mem_29_11 (-0.036), mem_29_14 (-0.036), mem_17_8 (-0.018), mem_29_8 (-0.012). Require measured post-route min slack and local setup checks at both corners before claiming physical repair. More iterations alone are not evidence of closure.

Read `experiment_status.json`, `hold_stdout.log`, generated reports, `copy_manifest.json`, `original_audit.json` and `isolated_input_audit.json` in the output root upon background completion. A zero return code alone does not establish timing closure. This old-map experiment cannot establish closure of the parent's updated RTL or constraints and is not a release build.
