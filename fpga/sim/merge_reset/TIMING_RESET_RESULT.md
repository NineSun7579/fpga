# Actual top reset/watchdog timing repair

Applied only `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hdmi_ddr_ov5640_top.v` in production after candidate validation. All edits use exact byte replacements; existing comments/encoding/line endings are preserved. No IP, FDC, PDS, or other production RTL was written. Before-image: `timing_reset_top_before.bin`; review diff: `timing_reset_top.diff` (Latin-1 byte representation); preparation/application: `prepare_top_timing_reset.py`.

SHA-256 before: `e240a10e6087789cabde8b09331562a8c8b75c2583aa0d0f28b727a7528f4cb0`.

SHA-256 candidate and applied production: `f035cd6c9c81b881cdcb2a81110707d13b6030fd6bb916f1ffcd7376b438dd4c`.

- Added initialized `startup_ready`, asynchronously cleared by loss of `locked`, with the 10000 comparison sampled on cfg_clk. `rstn_int = locked & startup_ready`; the saturating counter is unchanged. Release occurs on cfg edge 10001, one edge later than the former combinational compare. It cannot release before the full 10000-cycle countdown. Lock loss still asserts immediately, clears both counter and request without clocks, and forces the full countdown after even a short lock-loss pulse.
- Added initialized, ASYNC_REG-marked `diag_rst_sync[1:0]`, asynchronously cleared by rstn_int and released after two clk_25M edges. Both SCCB diagnostic instances now use `diag_rst_n`.
- Changed HSST `i_wtchdg_clr_0` to `~sys_rst_n`, removing cfg-counter-to-sys synchronous watchdog control. The actual hsst_test top wrapper has no `i_rst_n` port; its reset input is active-high `i_pll_rst_0`. Changed that input to `~sys_rst_n` too. Read-only inspection of `ipml_hsst_rst_pll_v1_0.v` confirms this feeds `pll0_rstn_sync` through an inversion and uses the free-clock domain. Existing IP reset synchronization remains intact, adding its normal release latency.

Validation ran `run_production.ps1` with TOP_RESET_CANDIDATE pointing at the literal candidate top, then applied the candidate and ran the production extraction/wiring/hash audit again. Applied production is byte-identical to the tested candidate. Four ModelSim tests passed with zero errors:

- Actual unchanged configuration RTL: 357 identical real I2C commands twice, 357 START/STOP/completions and 1428 ACK bits each run, no pre-enable START, stopped-clock reset, meaningful legacy negative controls.
- Actual merge/FIFO RTL: stopped-clock lock-loss reset, each camera configuration rerun, no stale/corrupt epoch pixels, eight complete frames across four recoveries; legacy retained-writer-pointer failure reproduced.
- Actual unreduced power counters: PWDN at 262145, camera reset release at 327681, configuration enable at 1376257 sys edges, repeated after reset; legacy X startup reproduced.
- Extracted literal top: cfg release exactly at edge 10001 on both startups; sys and diagnostic release only after their second local edge; sys/diagnostic/common merge reset assertion with clocks stopped; short lock-loss pulse cannot bypass countdown; full power delays and coordinated merge release.

Updated `verify_production.py` to audit the registered request, diagnostic chain and both diagnostic ports, HSST free clock/watchdog/reset ports, and to extract literal diagnostic RTL for simulation. Updated `tb_sys_reset.sv` with unreduced countdown and diagnostic assertions. Candidate override in `run_production.ps1` also participates in the across-run hash check. `production_hashes.json` records the top and six unchanged production dependencies plus the unchanged sensor table. Logs are `production_tb_*.log`.

Timing rationale: the old cfg-to-sys watchdog setup crossing is replaced by local sys control; the 84 diagnostic functional RS endpoints now receive a local synchronous release; the cfg binary comparator is behind a register before reaching reset networks. Parent must re-synthesize/route/report to confirm physical timing. Any cfg-to-sys/25M asynchronous-reset exceptions must be restricted to dedicated `sys_rst_sync`/`diag_rst_sync` RS pins after mapped-name review. Do not cut the watchdog, synchronizer data propagation, downstream local reset recovery, or whole clock groups. HSST reset now originates in sys_clk; retain local recovery checks unless a specifically reviewed dedicated-sync-pin exception is needed. Parent owns all FDC and FIFO physical timing work.
