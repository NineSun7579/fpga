# SOF / flush / DMA retirement boundary simulation

2026-09-27, ModelSim SE-64 10.6e. Production RTL, project files and IP were not edited; PDS and hardware were not invoked. All additions are in this simulation directory. Python byte reads/replacements were used; the one edited generator was backed up as `make_boundary.py.bak`. 162 source `.v` hashes were recorded before simulation and checked afterward: zero changes.

## Result and contract

An SOF sampled with flush_count=2 really can be admitted after flush_count reaches zero. This is **not by itself a corrupt-frame publication**. With the first pixel at least three axi_clk edges after the sampled SOF, every published frame in the scanned cases matches every expected pixel, including index zero. The supported sensor-style cases with gap=8 also pass around quota completion, final payload response, and tag response.

There is a reproducible short-blanking failure: gap=2 loses exactly the first pixel. If the source supplies quota+1 pixels (one trailing dummy), the dummy fills the quota and the shifted frame is tagged and counted as successful. This also happens when SOF is sampled after flush has ended; it is not specific to flush-period admission. Gap=0/1 loses three/two pixels; quota+8 can conceal those losses too. These gap=0..2 cases do not satisfy sufficient SOF-to-pixel blanking for this admission pipeline. Gap=0 is explicitly unsupported same-cycle SOF/pixel input; gap=1/2 are separate insufficient-blanking probes, not evidence against the normal sensor blanking contract.

For this bench a one-cycle SOF is sampled at edge N, internal m_vsync at N+2, and the capture state can accept the first pixel at N+3. `gap` is the number of sampled clock edges between raw SOF and first offered pixel. For a longer SOF pulse, pixels must additionally wait until SOF is low. This is a measured minimum for these synchronous interface tests, not a characterization of the upstream sensor/CDC path.

## Coverage and logs

| Suite | FIFO | Cases | New frames published | New frames dropped | Shifted frames published |
|---|---|---:|---:|---:|---:|
| boundary_behavior.log | behavioral, WORDS=64 / 512 pixels | 153 | 76 | 77 | 15 |
| boundary_vendor.log | actual generated FIFO + Pango primitives, WORDS=2048 / 16384 pixels | 153 | 76 | 77 | 15 |
| boundary_dummy_behavior.log | behavioral, quota+1 | 63 | 35 | 28 | 5 |

The 153-case suite contains 126 flush cases: seven phases (SOF sees flush_count 4,3,2,1,0,0,0), nine gaps (0..8), and two offered lengths (quota and quota+8). The remaining 27 cases put SOF around quota's final pixels, final payload W/B, and tag W/B. They use gap=8. The dummy suite scans the same 63 flush phase/gap combinations with quota+1. Separate vendor dummy results are recorded in the evidence attachment.

In the exact-quota flush scan no shifted frame is published: insufficient blanking causes a short capture and watchdog abort. In the quota+8 scan there are 15 shifted publications per FIFO implementation: phases 2..6 times gaps 0..2. In the behavioral quota+1 scan there are five: phases 2..6 at gap=2.

All published payloads are checked across all pixels, and their DDR tag is checked against last_cnt. AXI AW/W stability, WLAST obligations, complete AW/B ledger retirement, no overlap of success/abort, and no capture flush before external retirement are checked. The bench intentionally accumulates BAD_PUBLISHED observations instead of terminating at the first mismatch; simulator exit code zero means the scan completed, **not that every adversarial case passed**. Inspect BOUNDARY SUMMARY and BAD_PUBLISHED.

The source, bus, and capture run on one clock; no asynchronous CDC phase coverage is claimed. This is a single full camera capture/DMA path, not a three-channel arbitration test. The optional simultaneous three-channel source-fault case was not added.

## Exact failure timing

`boundary_dummy_behavior.log`, case 21, phase=2, gap=2, quota=512, offered=513:

| Clock cycle | Event |
|---:|---|
| 37433 | raw SOF, flush_count=2, capture count=0, engine idle |
| 37434 | flush_count=1 before edge; reaches zero after edge |
| 37435 | internal ADMIT, first offered pixel 0x4000 is not accepted because capture state is still IDLE before this edge |
| 37436 | first accepted pixel is 0x4001 |
| 37957 | payload DONE, count=512, frame_good=1 |
| 37968 | tag DONE, count=512, frame_good=1 |
| settled | last_cnt=1; stored tag=1; all 512 payload positions shifted, index zero actual=0x4001 versus expected=0x4000 |

Clock period is 10 ns; cycle labels are the bench counter sampled in the active region. DONE is the DMA retirement indication, not the raw AXI B handshake. Cycles 37434/37435 input/state detail follows directly from the stimulus and synchronous RTL; the other rows have TRACE records. The same short-blanking symptom exists in phases 4..6 where raw SOF sees flush_count=0.

Positive comparison: primary vendor suite case 85 sees SOF cycle 1490219 at flush_count=2, admission 1490221, first accepted pixel 0x4000 at 1490222 (gap=3), and all 16384 pixels compare correctly. Primary vendor suite case 153 sees a new SOF cycle 3136674 at flush_count=2 after the previous tag retires; gap=8, first pixel 0x6000 at 3136682, both published banks compare correctly.

Quota phases 0..3 overlap the last four offered pixels with the next SOF, so the old frame is incomplete and aborted. Phase 4 is the first edge after the final pixel: old frame completes and matches. The new frame is dropped while the engine remains busy. Payload/tag phases 0..8 are anchored to the final W beat; the TRACE DONE records show the scan spans retirement (phase 5 aligns SOF with DONE). Tag phase 8 reaches flush_count=2 and admits the new frame correctly with gap=8.

## Reproduction

Run from this directory with `C:/modeltech64_10.6e/win64/vsim.exe -c -l <fresh-log-name> -do boundary.do`, `boundary_vendor.do`, `boundary_dummy.do`, or `boundary_dummy_vendor.do`. Each uses its own work library. Choose fresh log names to retain the evidence. Existing frame_recovery suite scripts and logs were not overwritten.

Vendor warnings are the existing unconnected FIFO water-level outputs (wr_water_level, rd_water_level) and the ModelSim -novopt warning; the behavioral run has only -novopt. No simulator errors occurred in the completed primary or behavioral dummy runs.
