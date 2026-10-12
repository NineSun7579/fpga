# DMA abort / capture recovery results — 2026-09-27

Implemented in `C:\Users\NineSun\Desktop\ov56401\project`. No PDS run, synthesis, place/route, programming, or board access was performed. SENSOR_PLL_MULT is unchanged (cam3 init48, default cam1/2 84). Original source bytes were backed up before edits as `*.frame_recovery.bak`; subsequent refinement backups also end in `.bak`. All source changes use Python bytes. `audit_recovery.log` verifies every original non-ASCII line and PLL parameter line against the first backup.

## Final behavior

* `axi_dma_write`: new `abort_req` input and separate `data_in_abort` retirement pulse. `data_in_last` now means successful command only. A source fault, starvation watchdog, or AXI SLVERR/DECERR cannot generate success. Advertised AW remains asserted and stable until accepted; accepted W obligations, including a stalled pipe tail, and the actual B reply complete before retirement. Filler beats use zero WSTRB, preserving memory where no real source data exists. Unissued tail bursts are discarded. Abort with no advertised/outstanding burst can retire locally. No global AXI reset is used.
* `WD_LIMIT` is parameterized with unchanged hardware default `24'hFFFFFF`; integration simulation uses 64. Watchdog counts source starvation when the input pipe can accept, not a healthy source stalled by AXI. Waiting AW/B cannot be canceled by this timer.
* `ov5640_ddr`: admitted SOF owns a pixel quota latched from command length. Source is stopped at the quota, preventing the dummy pixel or next frame from contaminating this frame. A new raw SOF before the quota or either FIFO overflow latches a source fault and asks DMA to abort. No new frame is admitted while recovering.
* `ov5640_ddr_w`: local reset clears packing phase, pending write enables, both FIFO pointers/validity and stream counters. A four-cycle flush runs after a failed payload command or a retired tag command. A successful payload keeps capture validity through tag retirement. Data storage bytes with validity cleared are unobservable; the reset packing phase repopulates all bytes before the next valid output.
* `ov5640_ddr_w_ctrl`: a failed payload returns to idle without issuing a tag. Tag payload is prospective `frame_cnt+1`; only successful tag B retirement increments frame_cnt/last_cnt, flips bank and raises req. Failed tag retirement does none of these. A new write invalidates the target bank's old req; the opposite bank remains valid. SOF is not queued while busy.
* `ov5640_ddr_w_en`: capture_stop closes admission immediately; the next admitted frame requires a fresh SOF after flush. The existing SOF synchronizer/blanking assumption is retained.
* `ddr_w_arb` is unchanged. Ownership through actual B is required for AXI correctness. The source abort path makes a short frame release this owner after legal drain; it does not bypass the outstanding transaction.

## Modified source files

1. `source/axi_dma/axi_dma_write.v`
2. `source/axi_dma/axi_dma.v`
3. `source/ov5640/ov5640_ddr/ov5640_ddr.v`
4. `source/ov5640/ov5640_ddr/ov5640_ddr_w.v`
5. `source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v`
6. `source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v`
7. `source/ov5640/ov5640_top.v`
8. `source/top.v`

All five live `source/` axi_dma_write instances are explicitly adapted. Three camera engines receive their respective source fault and return their respective abort pulse through ov5640_top. The preprocess engine ties abort_req low and explicitly leaves the error pulse unused. Generic axi_dma ties abort_req low and exposes data_in_abort; its data_in_last has the new success-only meaning. Archived/migration copies were not changed.

## Verification

ModelSim SE-64 10.6e; commands below run from `sim/dma_timeout_repro`:

Preferred combined command: `python run_recovery.py`. It runs the three simulations in separate libraries, checks PASS markers and fatal/error text (not only process exit status), runs the source/interface audit, and writes `recovery_suite.log` plus the review-only UTF-8 `recovery_source.diff`. The final combined run reported `OVERALL PASS`. Whole-top baseline failures remain explicitly accounted for as described below.

```powershell
& 'C:\modeltech64_10.6e\win64\vsim.exe' -c -do frame_recovery.do -l frame_recovery.log
& 'C:\modeltech64_10.6e\win64\vsim.exe' -c -do frame_recovery_vendor.do -l frame_recovery_vendor.log
& 'C:\modeltech64_10.6e\win64\vsim.exe' -c -do ledger_recovery.do -l ledger_recovery.log
python audit_recovery.py
```

| Test | Final result |
| --- | --- |
| Behavioral FIFO integration, 512 pixels/frame | PASS; 10 successes, 7 aborts, 61 AW / 61 B, 75 zero-strobe filler beats |
| Actual configured Pango FIFO RTL + GTP_DRM36K_E1, 16384 pixels/frame | PASS; 10 successes, 7 aborts, 1425 AW / 1425 B, 75 zero-strobe filler beats |
| Three DMA engines + real ddr_w_arb + modeled top DDR staging | PASS; cam1 success/abort=5/0, cam2=1/0, cam3=0/2; accepted-burst drain and unissued-tail retirement |
| Source byte / wiring / module audit | PASS; five DMA instances wired, unique changed module names, original non-ASCII and PLL lines preserved |
| ov5640_top and generic axi_dma wrapper compilation | PASS |
| Whole top.v ModelSim compilation | NOT PASS; baseline and current both have 103 identical error signatures (pre-existing declaration/order issues) |

Integration assertions cover every pixel of every successful frame, including first (0,0) and last; tag contents; req/bank/count publication; no flush while any DMA/AW/W/B ledger is live; stable AW and W under backpressure; W count and WLAST; one outstanding burst; mutually exclusive success/abort; final AW/B balance. Cases include:

* odd-pixel short frame (13 pixels) terminated by the next SOF;
* missing data (11 pixels) with no subsequent SOF, requiring watchdog;
* source fault while AW is advertised but backpressured;
* natural FIFO overflow while W is stalled, including a delayed real B;
* payload and tag SLVERR injection;
* recovery after each failure with a distinct pixel pattern and full comparison;
* two retained bank requests followed by a failed overwrite of one bank;
* tag B withheld for 100 clocks (> simulation WD_LIMIT), with no early publication.

Vendor test really fills the configured 4096x32 DRM FIFO: source fault was latched around pixel 8331. It does not substitute the small behavioral FIFO. Vendor simulation has only the existing unused FIFO water-level port warnings and environment `-novopt` warning. Three-camera test retains existing unused-output/width warnings from its original testbench.

Logs: `frame_recovery.log`, `frame_recovery_vendor.log`, `ledger_recovery.log`, `audit_recovery.log`, `wrapper_compile.log`, `top_baseline_compile.log`, `top_current_compile.log`. `integration_compile.log` is the earlier exploratory failed top compile before moving the newly added fault-wire declarations ahead of use; use the audited current/baseline pair for final status.

Existing `tb_timeout.sv`, `run.do`, `tb_vsync.sv`, `baseline.do` remain historical reproductions; use the new *_recovery tests for the new interface/semantics. `tb_timeout_recovery.sv` is an adapted copy of the old three-camera test. The older DONE label in that inherited test means total retirements; its new final success/abort assertion is authoritative.

## Limits and remaining source investigation

1. This fixes abort accounting, local capture recovery and publication validity. It does not prove the camera's original CDC stream is correctly aligned. Raw marker synchronization and pixel FIFO crossing upstream remain separate. A stream with the right pixel count but shifted origin, duplicated/missing compensating pixels, or malformed row widths can still pass the quota check. Cam2's prior 461-column cross-row shift needs upstream SOF/pixel CDC investigation and board pattern evidence.
2. Recovery flush covers the packer and its two capture FIFOs in axi_clk, not upstream sensor CDC FIFOs, VIP/FIR/KF, or the preprocess mirror. Fresh SOF must truly precede pixel (0,0) at the wrapper. Existing several-cycle admission synchronization assumes VSYNC blanking; simultaneous SOF and the first valid pixel is not a supported proven contract.
3. DDR tag memory from an older frame is not erased on write start. The target bank's req is invalidated, and no new success tag is written for failed payload. A host that ignores req/current successful sequence and treats any old nonzero tag as valid can still read a partially overwritten bank. There is no reader/writer ownership handshake preventing a host read already in progress from racing a later overwrite. SLVERR/DECERR can also mean the slave partially committed data/tag despite reporting failure; hardware publication remains suppressed.
4. No full-resolution sensor-to-DDR simulation or CDC timing analysis was run. Tested camera format is the current 16-bit RGB565 path. Generic 8/24-bit packer branches retain their existing byte packing but were not separately simulated; non-byte-integral pixel quotas are not validated configurations.
5. If the AXI target permanently refuses AW/W or never returns B, safe release is impossible without system-level recovery. The engine deliberately keeps its obligation. A stopped sensor without another SOF still waits the unchanged hardware watchdog (~0.168 s at 100 MHz); other cameras can wait behind that burst until retirement.
6. No PDS synthesis/place/route or timing report exists for this edit. Main session must build and validate on hardware. The software-visible success counter now counts committed frame+tag completions, so the prior ~2.66/s timeout-generated completion figure will no longer measure bad-frame attempts.

The initial simulation command used `vmap recovery work_recovery` once, which added a `recovery` mapping to the installation ModelSim ini. Final scripts use direct library paths and do not modify mappings. No vendor IP file was edited.
