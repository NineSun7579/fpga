# build01 global STA review

Chinese detailed cone diagnosis and verified isolated RTL candidate: `CAMERA_CONE_REPORT_ZH.md`. Machine-readable actual path hashes, original-source verification, and exhaustive/miter log counts are in `camera_cone_evidence.json`. Candidate functional checks passed; no candidate physical STA or timing improvement is claimed.

## Completed independent final STA

PDS exited 0 with no detected errors. The routed DB and all 747 original input hashes verified unchanged after execution. Exact final tables are in `final_native_tables.json`; the ten parsed groups are in `final_global10summary.json`; complete scored negative paths are in `final_negative_paths.json`. The prior parser failure was offline-only: global reports also emit unconstrained paths without Slack. `finish_offline.py` recovered the actual existing report without another PDS run and retained all 1598 unscored records in `final_unscored_paths.json`. Unscored paths are not timing passes.

| Check | Slow worst slack (ns) | Fast worst slack (ns) | Failing endpoints Slow/Fast |
|---|---:|---:|---:|
| Setup | **-0.882** | 1.501 | 3 / 0 |
| Hold | 0.242 | 0.174 | 0 / 0 |
| Recovery | 1.429 | 2.373 | 0 / 0 |
| Removal | 0.287 | 0.247 | 0 / 0 |
| Minimum Pulse Width | 0.011 | 0.011 | 0 / 0 |

All three negative paths are Setup Slow, same-clock `cmos2_pclk -> cmos2_pclk`, with common start `cam2_ov5640_top/ov5640/cmos_frame_vsync_r/opit_0_inv/CLK`:

| Actual endpoint | Slack (ns) |
|---|---:|
| `source_diagnostics/cameras[1].source/cg/q[10]/opit_0/D` | -0.882 |
| `source_diagnostics/cameras[1].source/cg/prefix[1]/opit_0/D` | -0.692 |
| `cam2_ov5640_top/ov5640/ov5640_cdc/drop_prefix[7]/opit_0_inv/D` | -0.159 |

Negative endpoint coverage equals the final summary's three failing endpoints. Final TNS is -1.733 ns. Final DDR/pclk/pclk_div2 Setup Slow minima are **+0.250 / +1.090 / +0.896 ns**, respectively. No negative DMA endpoint was exported. Therefore DMA candidate v2 is **not needed to address the demonstrated remaining timing violation**; optimize the camera2 frame-vsync-to-count/prefix logic first. This does not establish functional DMA acceptance or whole-board signoff: sync-packing rejection remains a separate gate, and the 1598 unscored paths require constraint-coverage review. Final MPW now has actual rows and passes in both corners, resolving the PNR-native empty-table uncertainty.

The remaining sections retain the earlier PNR evidence for comparison. The final STA value -0.882 ns supersedes the embedded PNR value -0.853 ns for the optimization decision.

## Earlier embedded PNR evidence

Actual routed DB: `source_diagnostics_timing_build_01/place_route/v7_sdt_top_pnr.adf`.
SHA256: `e3dd999b8b352ed34cc7d6f34faea48893d2ee626ead6b8a0004928c46d2e847`.
All 747 entries in the original `evidence/input_hashes.json` verified unchanged before queue launch.

Boundary: these are PNR embedded STA results after hold fix, not independent final STA. Original `summary.extract` extracted the actual `place_route/prr.db`; it contains no setup/hold/recovery/removal/MPW tables or detailed timing paths. The ten groups below come from the same actual run's `v7_sdt_top_timing_summary_after_hold_fix.txt`, preserved by hash in `global10summary.json`. Empty MPW tables do not establish MPW coverage or pass.

| Check | Corner | Global worst slack (ns) | Failing endpoints |
|---|---|---:|---:|
| Setup | Slow | -0.853 | 3 |
| Hold | Slow | 0.058 | 0 |
| Recovery | Slow | 1.447 | 0 |
| Removal | Slow | 0.286 | 0 |
| Minimum Pulse Width | Slow | no rows | coverage unknown |
| Setup | Fast | 1.502 | 0 |
| Hold | Fast | 0.043 | 0 |
| Recovery | Fast | 2.380 | 0 |
| Removal | Fast | 0.248 | 0 |
| Minimum Pulse Width | Fast | no rows | coverage unknown |

The remaining negative group is **cmos2_pclk -> cmos2_pclk Setup Slow**, WNS **-0.853 ns**, TNS **-1.629 ns**, **3/1842** failing endpoints. This is a same-clock camera group. Native PNR reports do not identify these three endpoints, so their exact RTL cone must await the detailed export.

DMA-related clock-domain setup margins in the same native report: ddrphy_sysclk **+0.296 ns** (Slow), pclk **+1.096 ns**, pclk_div2 **+0.952 ns**. All have zero failing setup endpoints. These are clock-domain minima, not proof that a particular DMA endpoint was exported.

Decision: current evidence does **not justify integrating DMA candidate v2 to repair the remaining violation**; the demonstrated violation is in cmos2_pclk. Keep candidate v2 unintegrated until independent final negative endpoints establish a DMA-specific need. Existing sync-packing failure and empty MPW coverage still prevent whole-board signoff regardless of positive DMA-domain setup margins.

`queue_final_sta.py` is an idle-priority observer. It holds no PDS slot while any map01 run/recover/audit controller, build01 finisher, build02 controller, route03 controller, or actual PDS/TA process remains alive. It acquires the existing global PDS mutex only after two empty full scans, scans again under that mutex, and verifies the routed DB and all original input hashes before and after the tool. It never changes those controllers, their queues, project sources, constraints, or project files. It performs no remote/device/program operation.

The final Tcl uses the supported native option spelling: `report_timing -input_db_file {actualroute} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE`. Outputs are isolated under this review's `final_sta`. Final exports include exact native tables, all ten summary sections, and negative path records with clock-group/same-clock classification. `queue_status.json` distinguishes waiting, running, exported, and failed states; independent final results must not be inferred from a queued state.
