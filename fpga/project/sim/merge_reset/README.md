# Simulation-only 50K merge reset recommendation

Production follow-up: the parent applied the changes. `PRODUCTION_RESULT.md`
records byte/hash audits and three passing actual-production simulations.
Use `./run_production.ps1` after application; prior candidate-generation runners
describe the pre-application workflow.

Follow-up: `CONFIG_RESULT.md` and `config_candidate.diff` now document a passing
simulation-only fix for the `reg_config`/`i2c_com` startup/rerun limitation below.
Production remains unchanged. Run `./run_config.ps1` for that separate full
power-delay and 357-command I2C test.

Run `./run.ps1` in PowerShell. ModelSim 10.6e compiles the actual sources in
`ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl`; no production RTL, PDS or IP
files are edited. `reset_candidate.sv` is a simulation extraction, not a new
production module. Diagnostic 2388 is suppressed for the existing duplicate
`initial_en` declaration in `power_on_delay.v`; declaration warning 2248 remains.

## Exact top-only candidate

In `hdmi_ddr_ov5640_top.v`:

1. Initialize the existing declaration to `reg [15:0] rstn_1ms = 16'd0;`.
   Change its sensitivity list to `always @(posedge cfg_clk or negedge locked)`.
   Keep the existing `if (!locked)` clear and saturating count to `16'h2710`.
   Set `assign rstn_int = locked & (rstn_1ms == 16'h2710);`.
   This clears the counter without cfg-clock edges on unlock, and explicitly
   asserts reset from unlock. Declaration initialization matches the existing
   top's initialized fabric reset/divider registers; verify device synthesis
   supports that power-up initialization. In simulation start `locked=0` and
   hold it low before releasing it; an unknown PLL model is not a reset source.
2. Replace `power_on_delay_inst.reset_n(1'b1)` with `.reset_n(rstn_int)`.
   This module resets synchronously: allow three live `sys_clk` edges for all
   dependent reset registers/counters to become defined. It does not provide
   immediate asynchronous sensor reset assertion.
3. Inline the three two-bit reset synchronizers from `reset_candidate.sv` in
   the top, using the actual clocks/signals:

   ```verilog
   wire merge_req_n = rstn_int & (&cmos_init_done_int);
   reg [1:0] merge_a_sync = 2'b00;
   reg [1:0] merge_b_sync = 2'b00;
   reg [1:0] merge_o_sync = 2'b00;
   always @(posedge cmos1_pclk_16bit or negedge merge_req_n)
       if (!merge_req_n) merge_a_sync <= 2'b00;
       else merge_a_sync <= {merge_a_sync[0], 1'b1};
   always @(posedge cmos2_pclk_16bit or negedge merge_req_n)
       if (!merge_req_n) merge_b_sync <= 2'b00;
       else merge_b_sync <= {merge_b_sync[0], 1'b1};
   always @(posedge mrg_clk or negedge merge_req_n)
       if (!merge_req_n) merge_o_sync <= 2'b00;
       else merge_o_sync <= {merge_o_sync[0], 1'b1};
   ```

4. Connect `u_cam2_merge.a_rst_n` to `merge_a_sync[1]`, `b_rst_n` to
   `merge_b_sync[1]`, and `o_rst_n` to `merge_o_sync[1]` (replace current
   individual config-done / fab-reset connections). A drop in either config
   flag now resets both writers, both readers, and all merge logical state.
   Deassertion occurs separately on the second rising edge in each domain;
   identical release times or a handshake are unnecessary for these FIFOs.
   Do not synchronize release on `clk2core_tx` and reuse it for `mrg_clk`.

`fab_rst_n` currently comes from a synchronous two-flop shift register on
`clk2core_tx`, with declaration initialization. It is not an asynchronous
stopped-clock reset. The dedicated merge reset above replaces its use for the
merge only; existing SFP transport reset behavior is outside this candidate.
Do not add `fab_rst_n` as an independent reader-only reset later. Any future
merge reset cause must enter `merge_req_n` so it resets both FIFO ends.
Independent HSST PLL loss is outside the tested request; if that must reset the
merge, add its raw lock/reset cause to the common request, not just `o_rst_n`.

## Evidence (ModelSim run 2026-10-02)

- `tb_merge_reset.log`: PASS at 128082 ns. Actual merge and FIFO RTL, reduced
  16-pixel / 4-row geometry, 42 MHz camera clocks with frequency difference and
  62.5 MHz merge clock. Four recovery epochs, two complete frames each, checked
  A pixel position/row integrity, current epoch on all emitted nonblack pixels,
  B pixel positions including permitted repeat/black fallback, continuous
  32-pixel rows and four rows per generated frame.
- PLL unlock in an active merged row while cfg/A/B/merge clocks are stopped:
  both FIFO pointers, synchronization registers, full/empty flags, page-ready
  bits, snapshot-valid, pair counter, input line counters and DE/VS clear
  without edges. Relock without cfg edges does not release reset. A and B
  individual config reruns mid-row repeat these clear/recovery checks;
  config-done rising with destination clocks stopped does not release reset.
- Negative control using the old merge wiring retained writer pointers
  A=153/B=170 on stopped-clock PLL unlock. Its output reset also remains stale
  when its clock stops. This demonstrates incoherent reset state, not a claim
  that every reset phase necessarily corrupts visible output.
- `tb_power_startup.log`: PASS at 55051390 ns. Actual unreduced power delay
  counters run twice. Three sys-clock reset edges define all outputs and
  counters; PWDN goes low after 262145 cycles, camera reset releases after
  327681 cycles, initial-enable after 1376257 cycles (27.52514 ms at 50 MHz).
  Tied-high reset negative control leaves all three counters X.

## Boundaries and assumptions

- Config-done is explicitly modeled in the merge test. This does **not** prove
  SCCB configuration startup or rerun. Actual `reg_config.v` lines 67-74 clear
  its state only on `posedge clock_20k`, but lines 51-55 hold `clock_20k` low
  while `camera_rstn` is low. At startup no rising edge may initialize
  `reg_conf_done_reg`; on rerun a previous high flag may remain high. It also
  does not use `initial_en` in the configuration FSM. Full camera startup/rerun
  needs this independent issue resolved or evidence of an effective external
  reset mechanism. A top-only reset-wiring patch cannot honestly claim that.
- The common request assumes both config flags reliably assert low during
  their respective configuration reset and return high when configuration is
  finished. If rerun starts through another explicit reset signal, include
  that signal in the common request.
- Recovery traffic starts in blanking before complete lines. A reset released
  mid-camera-frame can discard a partial row; no frame identity matching or
  restart at a shared VSYNC is added. Existing merge framing is autonomous,
  and B fallback behavior is retained. Sensor-frame alignment is not proven.
- FIFO memory arrays and `c_data` are not reset, and the FIFO RAM write block
  is not reset-gated. Clearing both pointers and merge validity is sufficient
  for the tested restart: old RAM is inaccessible as valid data. During reset
  DE is zero; downstream consumers must honor DE. RTL #1 delays are allowed
  to settle before checking asynchronous clears.
- This is RTL simulation, not CDC/metastability, timing, or board validation.
  Keep production `16'h2710` and existing FIFO/merge parameters. No normal
  steady-state datapath changes are recommended.
