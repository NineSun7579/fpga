# Isolated DDR adapter contract validation

`fpga_v8_ddr_adapter.v` is an ASCII Verilog-2001 candidate between a single
AXI write path / serialized crossbar read path and the board's vendor DDR port.
It instantiates the actual, unmodified `ipcore/ddr_fifo16_w` and
`ipcore/ddr_fifo16_r` generated RTL. All eight FIFO source files compile in
ModelSim directly; they contain behavioral distributed RAM/control logic and
require no additional primitive library in this configuration. The DDR3
controller itself is an independent scheduled stub, not a simulated physical
vendor controller. No board/PDS/synthesis action is performed.

Only this directory contains new files/artifacts. Production `source/top.v`
stays byte-for-byte unchanged at SHA-256
`dca00ca2ecbc0b1418a32fc9abb09c673e522960a0150ef568f1e528a1681347`.
Production GBK and IP sources are inspected with Python byte reads. The runner
checks production, dependency and test hashes before/after each complete run.

The production findings are:

| Production construct | Actual-FIFO simulation finding |
| --- | --- |
| `top.v:524` ties `arb_s_bid` to zero | Incompatible with the new bridge ID 1 and arbiter's ID checker. Isolated exact-assignment reproduction triggers bridge error and arbiter ID error. |
| `top.v:242` uses `wr_en(ddr_axi_wvalid)` with upstream ready `!full` | The generated FIFO gates RAM writes and pointer advance with `!full`. Nine VALID cycles while full preserve all 16 words. This full-stall condition is safe for the inspected IP/configuration. |
| `top.v:268` reconstructs upper RID from latched `ar_sid`, and `601..607` clears inflight on vendor RLAST | The FIFO-empty AR gate retains the SID until all old buffered responses drain. A 16-beat burst fills the actual FIFO while RREADY=0; a pending S05 request cannot retag it. |

The production FIFO fact is specific: upstream WREADY currently equals
`!full`. Adding other WREADY gates without gating `wr_en` would change the
contract. The candidate explicitly writes only on accepted VALID/READY and
only while it owns an accepted AW. It prevents writes from a queued next burst
from entering the current FIFO or bypassing a held B.

Candidate write ports use AWID/BID=4 bits and 32-bit byte addresses, AWLEN=8,
AWSIZE=3 and AWBURST=2. W is 128 bits with 16 strobes and WLAST. Read ports use
ARID/RID=7 bits, full 32-bit addresses and 8-bit ARLEN. Unused AXI
LOCK/CACHE/PROT/QOS/REGION are not meaningful to this vendor port and remain
outside the adapter interface; a production wrapper must terminate them
explicitly. This adapter is not an AXI crossbar and does not arbitrate S00,
S02 and S05. The directed tests alternate their route prefixes after drain.

Accepted requests must be 16-byte aligned INCR bursts, SIZE=4, LEN<=15
(1..16 beats), fit one 4 KiB page, and end at or below
`DDR_ADDRESS_LIMIT` (default `0x10000000`, nonzero/aligned and no larger than
256 MiB). Wide range checks precede address/length narrowing to vendor
28-bit/4-bit fields. Exact physical-end transactions are legal. Invalid
requests are not accepted and set sticky diagnostics. There is no synthesized
DECERR response/drain for unsupported bursts: a master that presents an invalid
request must use common reset/system recovery. Integrators must enforce this
burst contract before submitting requests; otherwise a master may wait
indefinitely. Invalid test requests are withdrawn only because they were never
accepted.

The write path accepts/snapshots AW, then accepts exactly LEN+1 W words into
the generated 144-bit FIFO. Vendor AW is asserted only after the complete
burst is buffered. Its address/ID/LEN remain stable until vendor acceptance.
Vendor W has no VALID: its unthrottleable `v_wready` schedule consumes one
FIFO word at a time. Only the vendor's final-consumed indication mints B.
The accepted AWID is retained for BID. A wrong vendor returned ID or malformed
vendor LAST sets diagnostics and returns SLVERR under that accepted ID; a
valid returned vendor ID therefore gives the expected nonzero BID.
Upstream WLAST errors are flagged but do not end staging or mint B early.
Held B blocks new AW, preserves its response, and holds write ownership.

The read path snapshots all seven ARID bits and serializes acceptance through
the final downstream RLAST handshake. The generated 133-bit FIFO stores the
vendor's four-bit RID, LAST and all 128 data bits; the retained upper three
route bits reconstruct RID. Because the complete burst is at most the FIFO
depth, vendor R needs no READY. A 16-beat burst can be fully buffered even with
RREADY permanently low until after vendor LAST. No next AR can change the
route owner before drain. Candidate RRESP is constant OKAY because the vendor
port has no response field; malformed RID/LAST or unsolicited vendor beats are
sticky diagnostics, not a newly invented per-beat response. Unexpected vendor
protocol failures require system recovery. Changing live RRESP after a later
vendor beat would violate a held response, so the candidate does not do that.

All clocks are `clk`. `rst_n` must reset the adapter, both generated FIFOs,
upstream masters/fabric, vendor controller and lease bookkeeping together.
There is no local cancellation or transaction timeout. An adapter-only reset
cannot retract accepted vendor requests. Synchronous reset must span clock
edges. Reset reconciliation is external.

| Error bit | Meaning |
| --- | --- |
| 0 | Unsupported AW contract |
| 1 | Unsupported AR contract |
| 2 | Upstream WLAST disagrees with accepted LEN |
| 3 | Vendor requests W outside active nonempty burst |
| 4 | Vendor W ID/LAST disagrees with accepted AW/count |
| 5 | Vendor emits R outside active burst or into full FIFO |
| 6 | Vendor RID/RLAST disagrees with accepted AR/count |
| 7 | Downstream last R count differs from accepted ARLEN |

Run in PowerShell from this directory:

```powershell
& '../.venv/Scripts/python.exe' run_tests.py
```

ModelSim defaults to `C:/modeltech64_10.6e/win64`; `MODELSIM_BIN` overrides it.
Repeat `--case NAME` to select suites. All generated work libraries and
evidence stay in `artifacts/`. The runner requires explicit pass markers and
rejects simulator errors; `$finish` exit status alone is insufficient.
Known warnings are unused water-level outputs inside unmodified generated
FIFO wrappers and the installation's optimization setting.

The directed suite exercises 1/2/3/16-beat staging, partial final strobes,
simultaneous reads/writes, 16-word FIFO full/backpressure, queued AW/W behind
held B, ID 1/4/7/15, all held payloads, S00/S02/S05 RID reconstruction,
late SID changes after vendor LAST, invalid LEN/address/alignment/SIZE/BURST/
4 KiB crossing, exact 256 MiB end, wrong vendor WID, upstream WLAST faults,
and common resets at write staging/vendor AW/vendor W/vendor read/filled R/
pending B phases. It also simulates isolated logical snapshots of the original
read gate and the exact original BID tie, rather than compiling board `top.v`.

The integrated tests reuse the existing read-only cooperative-core harness and
explicitly replace its behavioral DDR response drivers with this adapter and
the vendor stub. Core ARID is presented as `{3'b010,core_arid}` (S02) and the
returned prefix is checked before the low four bits return to the core. Reset
stimulus can stall the front boundary; directed tests separately stall vendor
boundaries. The original BID failure case disables camera traffic so bridge
ID 1 is the first transaction. Passing lease/reset/full cases retain all six
competing camera streams and the existing ownership/metadata/RR checks.

Python independently compares every successful host-copy byte, actual vendor
output DDR dump, full camera-memory bytes/guards, all 128 bits of each observed
vendor camera W, physical address order, IDs and counts. Full-resolution output
is never truncated. The DDR stub has independent arbitrary W-consumption and
R-emission schedules without WVALID/RREADY, plus random AW/AR delay. It checks
every core output byte and final strobe as the vendor consumes it.

Production integration is still external. Review must resolve the original
BID tie, preserve complete FIFO staging and read-drain rules, terminate all AXI
attributes, map actual crossbar SID widths, wire AP/control ports as required
by the DDR IP, enforce valid burst/address contracts, and install safe common
reset/source leases and output allocations. No production endpoint, host
driver compatibility, FPGA Fmax, timing closure or board throughput is claimed.
