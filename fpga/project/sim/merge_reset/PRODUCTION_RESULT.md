# Production reset verification

2026-10-02 ModelSim 10.6e: **PASS**. Run `./run_production.ps1`.
Production files were read and compiled directly; none were written. No PDS
launch, process inspection, build polling or IP changes were performed.

## Byte and top integration audit

- Production `reg_config.v` and `i2c_com.v` equal the prior simulation candidate
  copies byte for byte (zero diff), including the four asynchronous reset
  sensitivities and the initial-enable launch guard.
- Sensor-table suffix equals the original legacy copy byte for byte. Command
  limit stays 357; divider and I2C transaction behavior stay unchanged.
- Production top counter initialization, asynchronous unlock sensitivity,
  saturating 16'h2710 count, locked-qualified `rstn_int`, and power-delay reset
  wiring are asserted by the byte audit. The common reset block matches the
  candidate after mapping actual clock/config signal names. All three merge
  clock and reset port connections are checked.
- `actual_top_reset_extracted.sv` contains literal production reset declaration,
  counter and common synchronizer blocks. Only external signal names are mapped
  to harness ports and 16'h2710 is replaced by a parameter, set to ten in the
  reduced merge test. Counter saturation uses the actual top's self-hold branch.
  Thus this run does not rely on the handwritten top reset candidate.
- All six production source hashes were rechecked after all simulations and
  remained unchanged. Full SHA256 values are in `production_hashes.json`.

## Actual-production results

`production_tb_config_startup.log`: PASS at 3269258340 ns.
Actual `power_on_delay`, `reg_config`, and `i2c_com`; full delay/divider counters.
Two sequences each completed 357 decoded START/payload/STOP transactions and
1428 ACK bits with index 357. Second sequence payloads equal the first sequence.
No transaction launches before `initial_en`. After the first completed sequence,
configuration-clock-stopped reset clears done, index, divider, FSM and I2C core;
configuration rerun completes. All three legacy negative controls reproduce
the original defects. No candidate source is compiled as the active controller.

`production_tb_merge_reset.log`: PASS at 128082 ns.
Actual merge and async FIFO with actual-top extracted reset blocks. Reduced
16-pixel/four-row geometry; eight complete frames over startup, midframe PLL
unlock with all clocks stopped, and individual A/B config reruns. Both FIFO ends
and merge validity/logical state clear without edges; recovered data has no
stale epoch pixels. Legacy reset wiring retains writer pointers A=153/B=170.

`production_tb_power_startup.log`: PASS at 55051390 ns.
Actual power sequencer, unreduced counters, two complete startups. Initial enable
at 1376257 cycles each time, outputs/counters defined through the three-stage
synchronous reset. Reset-tied-high negative control retains X counters.

## Integration issues and limits

No mismatch was found between applied functional reset changes and the tested
recommendation. This is isolated RTL validation, not a compiled entire FPGA top
with vendor PLL/HSST/IO primitives or physical camera streaming. The config test
drives the top's `rstn_int` input to the power sequencer rather than simulating
the PLL acquisition delay; that delay is audited and exercised separately by
the merge extraction with a reduced count.

The existing `power_on_delay` duplicate `initial_en` declaration still requires
ModelSim diagnostic 2388 suppression; warning 2248 remains. It was not changed.
Production declarations and hashes are preserved.

SCCB reset assertion is now asynchronous; its release timing and the divided
clock implementation still need implementation timing review. Sensor reset
itself remains synchronous through the power sequencer. Existing `fab_rst_n`
and SFP transport reset remain unchanged, and independent HSST PLL loss is not
part of the common merge request. These are the previously documented boundaries,
not new mismatches detected by this run. The ACK-only slave stub proves successful
writes, not NACK handling, sensor readback or bus recovery.

PDS build completion/status is unknown and was not inspected. Older
`run_config.ps1`/`prepare_config_candidate.py` are pre-application candidate tools;
after applying production edits, use `run_production.ps1` instead (it does not
regenerate candidates from already-patched RTL). Earlier reports describing
production as unchanged are historical; this report verifies the parent's apply.
