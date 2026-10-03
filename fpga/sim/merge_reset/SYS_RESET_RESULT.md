The production top now uses a shared `sys_rst_n` for the 50 MHz power sequencer, heartbeat counter/LED, and status input synchronizers. It asserts without a clock and releases after two `sys_clk` edges. The initialized 10,000-cycle cfg startup counter, PLL qualification, sensor programming table, byte packer, common merge request and three merge reset chains are preserved.

Production file: `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hdmi_ddr_ov5640_top.v`.

Exact scope:

- Insert initialized two-flop `sys_rst_sync`, with `ASYNC_REG`, immediately following the original `rstn_int` assignment; derive `sys_rst_n` from stage 2.
- Change `power_on_delay_inst.reset_n` from `rstn_int` to `sys_rst_n`.
- Change the active sys-clock status synchronizer and heartbeat LED asynchronous reset sensitivity/conditions to `sys_rst_n`.
- Change the heartbeat counter synchronous reset condition to `sys_rst_n`.
- No TX, FIFO, FDC, vendor IP or CMOS packer edits. No existing source bytes were decoded/re-encoded. The patch uses bytes and preserves line endings and all comments, including inactive legacy examples.

Exact byte-preserving diff: `sys_reset_top.diff` (Latin-1 transport of the original bytes). Original snapshot: `sys_reset_top_before.bin`. Repeatable one-shot patch/audit generator: `apply_sys_reset.py`.

SHA256 immediately before this scoped change:
`7d4e775688c76daafdb8c3e0ed4f179da909c1d4bd9d5c9b03a4d603ef5a9257`

SHA256 immediately after this scoped change:
`e240a10e6087789cabde8b09331562a8c8b75c2583aa0d0f28b727a7528f4cb0`

These hashes describe this patch boundary. Another agent may subsequently edit independent top sections; `production_hashes.json` records the snapshot actually verified by each regression run.

Validation: `powershell -ExecutionPolicy Bypass -File project/sim/merge_reset/run_production.ps1` passed all four simulations with zero errors. Production hashes were unchanged throughout that run. No PDS compile was launched.

- `tb_sys_reset`: literal extracted production counter/reset blocks, real 10,000-cycle cfg counter and all unreduced power counters; first-edge release prohibited, second-edge release required; PLL loss between edges while cfg/sys clocks are stopped; short lock-loss capture; deterministic startup and rerun; common merge release. Power milestones remain 262145/327681/1376257 sys cycles after synchronized reset release. Release adds two sys edges (approximately 20–40 ns), then the power sequencer first advances on the following edge.
- `tb_config_startup`: actual power/config/I2C production modules; 357 identical sensor commands twice, no START before enable, async reset with stopped SCCB clock, meaningful negative controls against legacy behavior.
- `tb_merge_reset`: actual merge/FIFO modules and literal production reset blocks; PLL/config reruns, stopped-clock reset assertion and eight complete merged frames without stale/corrupt pixels.
- `tb_power_startup`: actual full power delays and rerun, reproducing the old tied-high reset failure as a negative control.

The power sequencer itself retains its synchronous three-stage reset propagation. Its outputs settle to reset over three sys edges, as before. The new reset chain asserts immediately and holds reset through the restarted cfg delay. This change does not claim asynchronous reset of every power-sequencer register or immediate camera output transitions with sys clock stopped.

Timing evidence and parent constraint work:

The available current `place_route/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt` reports cfg_clk -> sys_clk setup WNS -2.980 ns, 55 failing endpoints, and recovery WNS -4.698 ns, 13 failing endpoints at slow corner. Production source proves the raw cfg counter decode feeds sys-domain synchronous resets and status/LED asynchronous resets. This is a concrete topology diagnosis; the summary does NOT identify individual STA startpoints/endpoints, so none are claimed here. The new topology removes the cfg decode from sys-domain D/reset logic except for the dedicated reset synchronizer's asynchronous control pins. Timing improvement remains unmeasured until parent builds/reports the new RTL.

Parent should resolve the mapped asynchronous reset pins of ONLY the two `sys_rst_sync` stages and apply a narrowly scoped reset recovery/removal exception from the qualified startup request to those pins. Do not broadly false-path cfg_clk -> sys_clk: they are related PLL/root clocks. Keep stage-1 -> stage-2 setup/hold timing and stage-2 -> all downstream synchronous reset/recovery/removal timing enabled. Confirm the tool retains both reset stages, their initialization, and close placement; `ASYNC_REG` recognition by this PDS release is not verified here. Use actual mapped pin names/nonempty collections before adding any exception. The preexisting cfg -> clk_25M recovery violations require a separate destination-domain reset assessment; this scope does not fix them.

CMOS hold diagnosis:

The production top samples data/href/vsync on camera pclk before `cmos_8_16bit`. The actual packer uses two input bytes to write `pdata_out1` on pclk, and captures through `pdata_out2 -> pdata_out3 -> pdata_o` on divided pixel_clk. DE similarly traverses `de_out2 -> de_out3 -> de_o`. `GTP_IOCLKBUF` feeds `GTP_IOCLKDIV(DIV_FACTOR=2)`; no IP was changed. Direct register-to-register divided-clock pipeline paths are plausible short-path candidates, but no report currently establishes that they are the failing paths.

The current summary identifies slow-corner cmos1_pclk_16bit -> itself WHS -0.077 ns, THS -0.106 ns, THREE failing endpoints. Fast corner has WHS -0.112 ns, THS -0.260 ns, FIVE failing endpoints. cmos1_pclk -> cmos1_pclk_16bit passes hold at both corners (+0.241/+0.113 ns). Thus the reported hold failures are within the divided-clock domain, not the pclk-to-divided-clock crossing. That domain also clocks thousands of merge writer endpoints, so assigning all failures to the packer would be unsupported.

The FDC declares the camera divided clocks with divide-by-two and 0.200 ns setup AND hold uncertainty; preserve it. The route log reports six hold-fix iterations and no forward progress in the last four iterations, which demonstrates the automatic hold repair reached a limit for this run, but does not identify CMOS endpoints. `report_timing/run.log` was generated Oct 1 and belongs to an older build; it must not be used to claim Oct 2 fullrepair endpoints.

Required parent report export: current routed database, slow AND fast hold paths for cmos1_pclk_16bit -> itself, enough paths to cover all 3/5 unique endpoints (e.g. 20 worst paths), full launch/capture clock paths, startpoint, endpoint, data delay, skew and uncertainty. This export should establish whether the issue is packer pipelines, merge/FIFO writer paths or clock distribution. Use physical hold buffering/placement/routing repair appropriate to the actual paths. No hold uncertainty relaxation, false hold exception, RTL delay chain, clock-phase modification or vendor-IP edit is justified by the current summary.
