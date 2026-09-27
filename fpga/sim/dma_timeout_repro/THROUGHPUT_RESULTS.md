# Camera burst-credit scheduling repair — 2026-09-27

Production change is based on the current frame_recovery/rejection-diagnostics RTL. It preserves cam1/cam2 init84 and cam3 init48, bad-frame rejection, source overflow detection, successful tag publication, and AXI ownership through real B. No PDS, synthesis, place/route, programming, or board access was performed by this subagent.

## Root cause reproduced

The DMA advertised its next AW before its source had enough data for that burst. The shared arbiter correctly locked the chosen owner until B. The top glue correctly waited for the entire 16-beat burst before presenting the DDR IP AW (the IP has no WVALID and cannot tolerate an empty staging slot). Consequently a slow camera could own the entire write path while waiting for future pixels or horizontal blanking to end.

When all cameras overlap, the round-robin arbiter services one 128-pixel burst per camera. With immediate AW requests even from an empty source, the two fast cameras receive approximately the slow camera's service rate. Increasing DDR speed or removing a few AW/B overhead cycles cannot remove this producer-dependent blocking.

At PCLK 84/84/48 MHz, RGB565 has 42/42/24 Mpixel/s during active pixels. HTS=1896, VTS=984 imply 45.0242/45.0242/25.7281 fps, 71.133 MB/s average aggregate payload and 216 MB/s during overlapping active pixels. During active rows, the average source rates are 28.3544/28.3544/16.2025 Mpixel/s. Blocking the fast channels to the slow channel leaves roughly 12.1519 Mpixel/s backlog growth. The existing 8192-pixel DRM capacity fills in roughly 674 us, explaining early-frame overflow without invoking a DDR bandwidth shortage.

The original RTL at 100 MHz AXI reproduces both fast channels failing at pixel 19586: fault `0x80004c82`, one overflow each, no short frame and no successful frame. Cam3 publishes a full correct-length frame. This lies inside the reported hardware fault-count range, approximately 13442–27522 pixels. Logs: `throughput_baseline.log` (initial model) and `throughput_original.log` (actual DDR staging FIFO added).

The initial recovery benches used 100 MHz AXI. The actual project clock was subsequently traced through `top.v: axi_clk=core_clk`, `ddr3.v: core_clk=ddrphy_sysclk`, and the generated DDR PLL / clock.fdc: 25 MHz ×84 /16 = **131.25 MHz**. Both clock settings are explicit test parameters; 100 MHz is retained as a slower-service stress condition. The source PCLK rates remain 84/84/48 MHz in both.

## Minimal production change

* `ov5640_ddr_w.v` counts accepted 32-bit writes into the existing DRM FIFO minus consumed AXI words. A 13-bit counter covers both FIFOs and the intervening read pipeline; complete stored beat credits are exported. It resets on the existing local flush.
* `ov5640_ddr.v` selects payload credits while in DATA and exactly one available beat while presenting a tag. `ov5640_top.v` and `top.v` connect the credits to their corresponding DMA.
* `axi_dma_write.v` adds parameter `WAIT_FOR_DATA`, default 0. Only the three camera instances set it to 1. Before advertising a new AW, the engine requires enough stored beats for `max_burst_len`, including 4 KiB splitting and partial tail bursts. Already asserted AW is held exactly as before; no existing AXI obligation is canceled.
* A missing/partial source before any AW now uses the existing watchdog counter, resetting it on credit progress. If the source stops, the command retires locally as an abort. Source faults, already-advertised AW, accepted W/WLAST and real B retirement keep the existing recovery semantics.
* Generic `axi_dma.v` and the preprocess instance explicitly tie credits to zero and retain default `WAIT_FOR_DATA=0`.

There is **no added data memory**, no FIFO depth/threshold change, no vendor edit, no arbitration-owner change, and no change to the DDR glue. The added state is a 13-bit credit counter and a 16-bit previous-credit register per enabled camera (87 flip-flops before synthesis optimization), plus arithmetic/comparison logic. Implementation resources/timing remain for the main session's PDS build to verify.

Counting the final FIFO alone is unsafe: its existing almost_full threshold is 15 out of 16. With sparse input and no DRM read in flight it may stop at 15 forever. Counting the entire already-stored stream permits draining those 15 words and then reading the already-present next DRM word, without waiting for a future pixel. The generated DRM read path supports consecutive one-per-clock 128-bit reads; the original throughput case observed runs of 17 consecutive reads with the real Pango model. The 32→128 packing/read latency is not the limiting service rate here.

## Simulation contract and results

`tb_throughput.sv` uses three production capture wrappers, three production DMAs, production `ddr_w_arb`, the actual configured `ov5640_ddr_fifo_DRM` with Pango DRM36K primitives, actual `ov5640_ddr_fifo`, and actual `ddr_fifo16_w`. The top glue's single-outstanding AW hold/full-staging/B behavior is modeled cycle by cycle. The DDR IP endpoint is a programmable service model, not the full PHY/DRAM model: AW acceptance is immediate after staging, W consumption starts after LATENCY cycles and repeats every GAP cycles, and the final IP W consumption produces B. LATENCY/GAP represent service delays, not measured board DDR timing.

Each source uses an NCO to map its 84/48 MHz byte clock to AXI cycles, sends exactly 640×480 RGB565 pixels and includes 1896-clock rows and 984-row frames. The first two sources have the same phase; cam3's phase is configurable. The model begins at the capture-wrapper input, after upstream sensor CDC/filtering. It does not claim to simulate analog sampling/metastability or the full DVP/filter pipeline.

Every successful payload pixel is compared, including first and last; tag sequence is checked in the updated suite. Actual DDR staging output is compared against the accepted W stream. Assertions cover stable AW/W under backpressure, exact W count/WLAST, no empty DDR staging read, no flush before retirement, no success/abort overlap, and final AW/B balance.

| Test | Result | Peak stored beats cam1/2/3 | Completion fps cam1/2/3 |
|---|---|---|---|
| Actual 131.25 MHz, LATENCY=8 GAP=1, 2 frames each | 614400/614400 pixels each, no rejects; AW=B=4802 each | 16 / 17 / 16 | 45.0224 / 45.0224 / 25.7275 |
| 100 MHz, LATENCY=8 GAP=1, 3 frames each | 921600/921600 pixels each, 3 successes each, no rejects; AW=B=7203 each | 17 / 20 / 18 | 45.0218 / 45.0218 / 25.7273 |
| 100 MHz, cam3 phase=1137 cycles, 2 frames each | 614400/614400 pixels each, no rejects; AW=B=4802 each | 16 / 18 / 17 | 45.0218 / 45.0218 / 25.7273 |
| 100 MHz, LATENCY=64 GAP=2, cam3 phase=1975 cycles, 2 frames each | 614400/614400 pixels each, no rejects; AW=B=4802 each | 19 / 25 / 21 | 45.0227 / 45.0227 / 25.7273 |

The nominal 100 MHz model measures AW-to-B at 44 cycles for full bursts. Including the next-grant cycle, 256 bytes /450 ns is about 569 MB/s when data is ready. The stressed model measures up to 116 cycles AW-to-B, about 219 MB/s including handoff, still sufficient in the tested overlap. Original cam3 ownership had 1,778,506 no-W cycles for one frame and a maximum AW-to-B duration of 1815 cycles; fixed sources have exactly one no-W cycle per burst for the existing W pipeline. Burst size remains 16, the DDR interface's 4-bit AWLEN limit.

Additional tests:

Actual-clock baseline `throughput_original_actual.log` also reproduces `0x80004c82` on both fast cameras at about 689 us. Cam3 has 2,370,486 owner/no-W cycles and a maximum AW-to-B duration of 2383 cycles. Fixed `throughput_actual.log` checks all pixels and tags with the actual clock; 44 AW-to-B cycles plus one handoff cycle correspond to approximately 747 MB/s ready-data service in this nominal endpoint model. `throughput_suite.log` finishes with **OVERALL PASS**. The suite summary includes previously completed phase/stress/regression logs when invoked with a list of selected reruns; default invocation reruns every listed case.

* `credit_recovery_vendor.log`: enabled-credit path, real configured FIFO, 10 full successful frames /7 injected aborts, AW=B=1422, 30 zero-strobe filler beats. Retains natural overflow at pixel 8331 with W held off, delayed B, missing source, short frame, AW-stall abort, payload/tag errors, bank validity and recovery. The AW-stall source supplies 129 pixels so the new gate can legitimately advertise the AW before fault injection.
* `throughput_regress_credit_recovery.log`: behavioral FIFO equivalent, 10 successes /7 aborts, AW=B=58.
* `credit_tail.log`: 4 KiB split at 0xFF0 into 1+5 beats; partial stored source times out before AW without reserving DDR; subsequent single-beat command succeeds. Final AW=B=3, W=7, success=2, abort=1.
* `throughput_regress_frame_recovery*.log`: unchanged existing tests pass with the compatible default DMA mode (behavioral AW=B=61; vendor AW=B=1425).
* `throughput_regress_ledger_recovery.log`: existing three-owner accepted-burst and delayed-B recovery ledger passes.
* `throughput_regress_rejection_diag*.log` and `throughput_regress_rejection_regs.log`: existing rejection evidence/register tests pass.

## Audit, reproduction and limits

All six edited production files have exact pre-edit `.burst_credit.bak` files. Python bytes performed source search/replacement, preserving all original non-ASCII and SENSOR_PLL_MULT lines. `audit_burst_credit.log` verifies all 422 vendor/IP files against `throughput_protected_hashes.json`, the three top credit nets, explicit non-camera tie-offs and wrapper compilation. `burst_credit_source.diff` is a UTF-8 review artifact; it is not used to rewrite GBK sources. The existing whole-top ModelSim declaration/order failures remain: before and after both have the same 103 error signatures; a clean whole-top compile is not claimed.

From this directory:

```powershell
python make_throughput.py
python make_credit_recovery.py
python run_throughput_suite.py
& C:/modeltech64_10.6e/win64/vsim.exe -c -do throughput_fixed.do -l throughput_fixed.log
& C:/modeltech64_10.6e/win64/vsim.exe -c -do credit_recovery_vendor.do -l credit_recovery_vendor.log
& C:/modeltech64_10.6e/win64/vsim.exe -c -do credit_tail.do -l credit_tail.log
python audit_burst_credit.py
```

Do not rerun `patch_burst_credit.py` on an already-patched tree; it deliberately rejects duplicate/missing anchors and existing backups.

Remaining hardware validation belongs to the main session: build/timing closure, program, and remeasure offered pixels, overflow/short counters, successful frames and frame pixel contents. The model proves removal of this source-dependent bottleneck under the documented service conditions; it does not prove unlimited tolerance of DDR stalls/read traffic. The known gap=2 plus trailing-extra-pixel boundary risk in `boundary_report.md` is unchanged and independent of this overflow repair. No camera clock is reduced and no frame-validity check is disabled.
