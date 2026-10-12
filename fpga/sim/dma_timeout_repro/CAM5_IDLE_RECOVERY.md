# Cam5 idle capture recovery

Only production change: `source/ov5640/ov5640_ddr/ov5640_ddr.v`.
No DMA, controller, vendor IP or project edits were made by this subagent.
Original exact bytes are `cam5_idle_recovery_before.v`; the byte patch script
preserves line endings and checks every original non-ASCII comment line.

## Evidence and limits

Reported hardware: cam5 tags stop at 0x42f/0x42e, ctrl state remains IDLE=1,
fault snapshot remains zero, offered input pixels remain 0x4b000.
`engine_busy` is exactly `(ctrl.curr_state != IDLE)`, so this excludes that
controller busy signal as the persistent gate while the sampled state is IDLE.
Wrapper admission is also gated by capture_flush/bad/complete. Complete is
capture_open && pixel_count == pixel_limit. It blocks all future admitted SOFs;
raw SOF does not mark a complete frame short. Without a live DMA command,
the DMA watchdog cannot recover it. Therefore orphaned complete metadata
can freeze indefinitely with a zero source fault, matching the reported shape.

This proves the recovery gap, **not the originating board event**. A normal
completion plus new SOF race was investigated but not naturally reproduced as
an idle trap. No board waveform establishes how capture metadata became stale.
Do not describe this as a proven same-cycle race fix. To resolve the origin,
sample capture_open/complete/bad, flush_count, cmd_valid and DMA trans alongside
ctrl state on hardware.

## Repair

Count eight consecutive idle cycles only when capture_open has complete/bad
metadata, no offered command, no admitted SOF and no existing flush. Reset the
counter on any busy controller or command activity. Stale metadata invokes the
existing four-cycle local packer/capture flush. The delay allows the existing
admitted-SOF -> controller edge detector -> command pipeline to settle.
Do not alter live command retirement, tag publication or outstanding AXI work.

## Fresh ModelSim results

All runs checked log contents; ModelSim may exit zero after `$fatal`.

* `cam5_idle_baseline.log`: identical full-DMA test using pre-edit wrapper fails
  `idle complete capture remains permanently closed` after depositing orphaned
  metadata. No AXI output is forced.
* `cam5_idle_recovery.log`: complete and bad orphan metadata recover, no fake
  publication/command; subsequent full patterned frames pass pixel/tag/bank
  comparison. success=12, abort=7, AW=B=68.
* `cam5_idle_vendor.log`: same test using actual configured vendor FIFOs;
  success=12, abort=7, AW=B=1680, 16384 pixels checked per successful frame.
* `cam5_regression_credit_recovery_vendor.log`: existing source-fault/error/backpressure recovery
  passes, success=10, abort=7, AW=B=1422.
* `cam5_regression_frame_recovery.log`: existing compatible non-credit DMA path passes,
  success=10, abort=7, AW=B=61.
* `cam5_boundary_baseline.log` versus `cam5_boundary_fixed.log`: same 153 SOF /
  quota / payload completion / tag completion / flush phase cases. Both yield
  published_new=76, dropped_new=77, bad_published=15. The existing short-blanking
  pixel-origin bug is unchanged and is not claimed repaired by this change.
* `cam5_regression_ledger_recovery.log`: existing three-DMA ledger test times out. Its do-file
  compiles only axi_dma_write, stream_pipe and ddr_w_arb, all untouched here;
  it does not compile or instantiate the changed wrapper. This is not a passing
  regression and is not caused by the wrapper repair.

Run from this directory with ModelSim 10.6e:

```
C:/modeltech64_10.6e/win64/vsim.exe -c -do cam5_idle_baseline.do -l cam5_idle_baseline.log
C:/modeltech64_10.6e/win64/vsim.exe -c -do cam5_idle_recovery.do -l cam5_idle_recovery.log
C:/modeltech64_10.6e/win64/vsim.exe -c -do cam5_idle_vendor.do -l cam5_idle_vendor.log
C:/modeltech64_10.6e/win64/vsim.exe -c -do cam5_boundary_fixed.do -l cam5_boundary_fixed.log
```

Board build, timing closure and programming remain with the main agent.
