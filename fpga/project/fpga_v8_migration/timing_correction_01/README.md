# Targeted timing correction 01

**RTL regression PASS; timing NOT CLOSED / unmeasured for this candidate.** Everything produced here is local to this new directory. No PDS, synthesis, mapping, routing, bitgen, SSH or board access was invoked. Parent owns the fresh whole build and v3 integration. Core clock remains **131.25 MHz / 7.619 ns**; no FDC edits, false paths, hold cuts or clock relaxation.

The complete v2 report identifies two setup clusters, not a cooperative arithmetic or H2F packing critical path. New source modules are `rtl/ovreg_axil_decode_tc01.v` and `rtl/block_motion_detector_tc01.v`. Register them and apply the **two exact instance-type replacements** in `parent_handoff.json` to the parent-owned fresh candidate. That manifest records the observed v3 binding-source hashes; this session did not edit v3. Original definitions can stay registered because candidate names are unique.

## Actual v2 setup paths

All **39** failures are slow-corner, `ddrphy_sysclk -> ddrphy_sysclk`, units ns; TNS **-8.067**. Fast core setup WNS is **+2.608**. Exact 39 entries, bit endpoints and full source hierarchies are in `evidence/exact_setup_paths.json`; representative complete paths are in `address_decode.txt` and `motion_reduce.txt`.

| Cluster | Endpoints | Worst slack | Actual critical chain |
| --- | ---: | ---: | --- |
| Camera 4 register write enable | 25 | -0.429 | `axi_crossbar_7x3/axi_crossbar_inst/axi_crossbar_wr_inst/m_ifaces[1].reg_inst/genblk1.m_axi_awaddr_reg_1[14]/opit_0/CLK` -> `cam4_ov5640_top/ov5640_reg/cam_addr_2[*]/opit_0_inv/CE` |
| Camera 4 motion reduction | 14 | -0.356 | `cam4_ov5640_top/u_motion_tap/u_detector/block_hits[170][1]/opit_0_L6QL5Q_perm/CLK` -> `min_x_work`, `max_x_work`, `blocks_work`, `bbox_work_valid` enables |

Address endpoints are cam_addr_2 bits **0,2,3,4,5,6,7,8,10,12,13,14,15,16,17,18,19,20,21,22,23,24,25,27,30**. Worst endpoints are bits 19/20/23/25 at -0.429. Motion endpoints are min_x[0:3] (-0.356), blocks[2:4] (-0.161), bbox_valid and blocks[6:7] (-0.129), max_x[0:3] (-0.001).

The address path has six logic levels, **1.176 ns logic / 6.286 ns route (84.240%)**, clock skew -0.210. Its motion-page equality traverses shared LUTs named `u_v8_cooperative_core/bridge/output_packer/N7_5` and `N7_20`; the path carries `cam_axil_awaddr[14]`, not packed tensor data. Then it traverses `ovreg_axil_decode_u`, camera handshake and the cam_addr_2 enable. The longest net segment is **3.033 ns** at `cam4_ov5640_top/ov5640_reg/N2`, followed by **1.484 ns / fanout 32** at `N50`. Hierarchical LUT labels alone would misidentify this as an output-packer datapath issue.

The motion path has five levels, **1.177 ns logic / 6.207 ns route (84.060%)**, clock skew -0.215. Block-hit net fanout 4 takes **2.462 ns** before local threshold detection; `mark_block[170]` then takes **1.257 ns** into the 192-block reduction and bbox enable. `evidence/datapath_hot_nets.json` preserves high-delay datapath net occurrences; it is not a design-wide hot-net census.

## Concrete correction and semantics

**Decoder:** Factor default camera write routes directly from page bits. The exact motion page is 0x200008xx and cannot select camera 2/3/4 for default ADDR_SEL_LSB=8. The live camera 4 valid therefore no longer depends on address bits 31:12 or a wide motion equality. Motion override remains on camera 1/prep selection. Save response steering as a one-hot route. Nondefault parameters retain original routing. No AW/W/AR/B/R pipeline edge or throughput bubble is added; every output was checked against the actual original decoder before/after each test edge.

**Motion:** Register each block's next threshold eligibility in parallel with the existing compare/decision stage. Forward the pending local increment so consecutive changed samples in the same block, including SAMPLE_STEP=1, use the correct count. Forward work clears too, including threshold=1. Global marking/reduction now starts at a threshold metadata FF rather than a local multi-bit hit count. Counters still saturate exactly once at threshold, samples still count all changes, bbox and bitmap publish identically.

No stage was added to the sample stream: update remains sample+2, result remains frame_end+2, adapter capture remains end+3. Earliest legal next-frame start, active restart, short frame, reset, final sampled pixel, gap/dummy behavior and frame sequence are unchanged. Default RTL adds **192 one-bit threshold metadata registers per detector / 768 for four cameras**; actual mapped resource delta is not measured. Histories retain the same synchronous read-first template and dimensions **four x 19200 x 8 = 614400 bits**. Event FIFO/marker logic and raw DDR/NPU pixels are unchanged.

Actual v2 mapped top resources: **29856 LUT / 30779 FF / 71.5 DRM**. The four motion taps consume 1514/1512/1504/1497 LUT, each 1939 FF and 8 DRM; decoder consumes 84 LUT / 8 FF; cooperative core 1703 LUT / 1416 FF; output_packer 298 LUT / 279 FF. Full hierarchy rows are extracted in `evidence/v2_relevant_mapped_resources.json`. Parent must recheck RAM inference and the newly introduced local threshold-forwarding register paths after mapping/routing.

## Hold/removal and effective clocks

All **611** detailed negative paths have matching launch/capture clock names. Actual effective clock groups and clock interaction are saved in `evidence/effective_v2_clock_groups.txt` / `effective_v2_clock_evidence.json`. The existing camera-pclk/DDR asynchronous groups are effective; there is no reported pclk->axi violation that justifies a new cross-domain cut. Camera and vendor same-domain minimum-delay paths remain genuine hold/removal requirements.

| Domain | Slow hold count / WNS | Fast hold count / WNS |
| --- | --- | --- |
| free_clk | 7 / -0.158 | 3 / -0.040 |
| cam1_sccb | 7 / -0.193 | 3 / -0.051 |
| cam2_sccb | 11 / -0.203 | 3 / -0.035 |
| cam3_sccb | 51 / -0.523 | 18 / -0.209 |
| cam4_sccb | 50 / -0.319 | 19 / -0.095 |
| cmos1_pclk | 28 / -0.998 | 21 / -0.515 |
| cmos2_pclk | 25 / -0.939 | 22 / -0.504 |
| cmos3_pclk | 97 / -2.039 | 81 / -1.178 |
| cmos4_pclk | 55 / -1.507 | 50 / -0.842 |
| ddrphy_sysclk | 1 / -0.028 | 1 / -0.015 |
| pclk_div2 | 1 / -0.057 | 1 / -0.038 |
| sfp_fabric | 3 / -0.012 | 3 / -0.007 |
| Total | **336** | **225** |

There are **11 slow removal** failures in free_clk: three camera-control-reset -> camera 3 I2C counter reset pins (worst -0.101), eight inherited SFP vendor-reset paths (worst -0.059). Fast removal has no failures. Every exact endpoint, clock skew and check kind is preserved in `evidence/all_611_classified.csv`; path-group labels alone would incorrectly mix removal into hold totals.

The core hold representative is `ov5640_top/u_cam_fir3/out_pixel[15]/opit_0_AQ/CLK` -> `ov5640_top/u_motion_tap/events_7/ram32x2d/DIH`: **0 logic levels**, tco 0.174 + route 0.091 = 0.265 ns, actual hold requirement 0.264 ns plus 0.029 ns skew, slack -0.028. This is a real register-to-distributed-RAM data hold path. No artificial RAM delay was inserted; parent should first allow physical hold repair to run successfully.

The frozen baseline final STA report, verified by actual `top.rtr` hash **bcbcc28a9e159784f7abdb1bd8076ef8efbbf3a49a2f857de1a438789cbfb774**, says All Constraints Met and has no negative clock rows. Baseline slow core setup was +0.030 ns. Thus these subsystems are inherited, but the current failures cannot be described as already failing in the frozen baseline. `baseline_final_sta_comparison.json` preserves every baseline slow/fast row.

## Specific parent route action

The v2 run contains **`Route-2037: Number of hold violated paths is 15016, over the limit 15000 and hold violation fix will be stopped`**. It also reports 772 SRB-clock paths below the requested 200 ps margin and the -2039 ps slow cmos3 endpoint. Exact warning lines are in `evidence/hold_route_abort.txt`. This is direct evidence of a repair-capacity skip, not speculation about missing constraints.

Installed **PDS 2022.2-SP6.4 User Guide**, PDF pages 110-112, documents **Options > Place & Route > General > Max Number Of Hold Violated Paths To Fix**, valid **0..100000**. Propose **30000** for the parent's fresh run so this 15016-path set is eligible for repair; check its new log and actual PRR settings to ensure no capacity skip. The selected value is a proposal, not a closure guarantee.

`proposed_route_settings.json` records the exact documented `pnr` flags from PDF pages 252-253 and baseline-matched physical options for review: multi-corner and hold repair enabled, 500 iterations, 100 ps hold margin, in-route hold repair enabled, cross-SRB 200 ps, clock-tree 200 ps. Actual v2 used multi-corner=false, hold repair=false, in-route=true, cross-SRB=200, clock-tree=100 and path capacity=15000. The manual's page 118 says PG2L100H uses the single-thread router and its general/router options follow Logos. No undocumented effort option is invented. The path-capacity CLI flag is not listed in the installed manual; use the exact documented GUI setting or inspect `pnr -help` in the parent's authorized session before choosing a CLI spelling. No PDS help process was launched here.

Physical hold-routing settings preserve STA requirements. They do not prove closure and may not resolve reset removal. The parent's new startup/reset guard has separate unmeasured timing effects. Final all-clock slow/fast setup, hold, recovery, removal and min pulse remain required. Existing 62 missing input delays, 71 missing output delays and 470 unscored IO paths do not count as IO signoff.

## Regression and review evidence

- **ModelSim PASS:** actual `project/sim/motion/tb_block_motion_detector.sv` independent frame/history oracle against TC01, plus original detector side by side with every output checked each active cycle. Five geometries: sparse, dense STEP=1, 1x1 threshold=1, default 640x480, and packed 11-bit geometry. Default instances each publish 16 results over **5,094,401 cycles**; includes literal +/-15/16/17, final eighth hit, split blocks, earliest restart, gaps/dummies, resets and incomplete frames. `simulation/motion.log` has zero errors.
- **ModelSim PASS:** all actual decoder output ports paired against original, LSB=7/8/9, **65536 stimuli per case / 131073 comparisons per case**, exact motion/aliases, full low-page offsets, CDC offsets, randomized split AW/W, downstream ready/response/backpressure and periodic resets. `simulation/decoder.log` has zero errors.
- **ModelSim PASS:** actual `tb_four_motion.sv` with only detector binding replaced in a private adapter copy. Four default 640x480 streams, **10 phases / 3,378,505 cycles**, complete atomic 320-bit records, frozen packet snapshots, independent seed/static/short recovery oracle, end+2/end+3 assertions and unused slots 4/5 zero. `four_simulation/four_motion.log` has zero errors.

`regression_result.json` / `four_regression_result.json` preserve test and candidate SHA256s and before/after identity of original source/test inputs. `evidence/source_hashes.json` includes actual v2 constraints, RTL, reports and candidate hashes; full source diffs are retained alongside the path evidence. Candidate detector SHA256 **109a04b0714c3a0cc302686171e4776abe31351ce0ccdd19927c27d1347952ca**; decoder **8e77852f4e969984ad7e333445acc067c7cac0714f6b5adaf8156a4a4fbd5c5e**.

Reproduce with local Python: `analyze_paths.py`, `run_regression.py`, `run_four_integration.py`, `prepare_handoff.py`. Scripts write only here. The initial shell wrapper timed out after 1 second; the complete repeated regression passed with no timeout and its logs/results are authoritative.

PCIe/H2F/ARM, signed-byte packing/strobes, 4KiB splitting, FIFO latency, final-B retirement, reset-fault data drain and capture-control APIs were not modified. Their prior component tests are not claimed as new whole equivalence evidence. The tests above cover the paths changed here; whole v3 physical timing and whole functional equivalence remain the parent's responsibility.
