# DDR adapter validation results

All five final ModelSim suites pass using the actual generated write/read FIFO
RTL from `project/ipcore`. The final production top SHA-256 remains
`dca00ca2ecbc0b1418a32fc9abb09c673e522960a0150ef568f1e528a1681347`.
All production/IP/cooperative RTL and the reused cooperative-core testbench are
read-only and unchanged across the run. Every new source and artifact is under
`fpga_v8_migration/ddr_adapter_contract`.

| Suite | Verified result |
| --- | --- |
| `directed_actual_fifo` | 12 retired directed writes, 39 fully compared candidate R words, 17 original-gate R words, 12 unsupported AW/AR rejections, 16 common-reset calls, 1,121 clocks |
| `original_bid_failure` | AWID=1, minted BID=1, exact original assignment returns BID=0; bridge error and arbiter ID-error bit both asserted |
| `core_leases_actual_fifo` | Three published/copied frames, 180 output bytes, 912 vendor W slots and 6 vendor R slots; 144 competing camera bursts; 4,769 clocks |
| `core_reset_actual_fifo` | Four interrupted leases reconciled by common reset, then one clean published/copied frame; 90 output bytes; 6,183 clocks |
| `core_full_actual_fifo` | Complete 640x480 -> 640x640 frame, 1,228,800 bytes, 96,000 vendor W slots, 38,400 vendor R slots; 3,072 competing camera bursts; 999,669 clocks |

Python compares every host-copy byte: 1,229,070 bytes total. It separately
compares the actual vendor-memory output dumps and all camera-memory bytes and
guards. All 19,200 camera W words and 76,800 output W words in the full case
are observed at the vendor consumer, with IDs, physical addresses, strobes,
order and counts checked. Full output SHA-256 is
`fb04064361624702ae85783736aaca6d04564789f9e2f4b0ce71eeef991b64ec`.
There is no sampled or truncated frame comparison.

The source inspection and original-behavior tests show:

1. **The production BID tie is incompatible with this core.**
   `source/top.v:524` contains `assign arb_s_bid = {3'b000, 1'b0};` even though
   the B bridge at lines 561..565 rebuilds a real vendor ID. The isolated
   `fpga_v8_top_bid_snapshot.v` reproduces that exact assignment. With camera
   traffic disabled, the cooperative bridge's ID=1 is the first write, and the
   original assignment independently triggers both ID checkers. The passing
   candidate snapshots accepted AWID and returns it without truncation or a
   route prefix. A wrong vendor WID test accepts AWID=4, supplies vendor ID=12,
   then verifies BID=4 plus SLVERR and a sticky vendor-ID diagnostic.

2. **The ungated write-enable is safe under the inspected full-only ready
   contract.** `top.v:242` uses VALID as FIFO write enable, but the generated
   FIFO RAM gates it with `!full` and the sync pointer also stops at full.
   The actual FIFO fills with 16 distinct words, sees nine more VALID cycles
   while full, then returns every original word unchanged. This is not evidence
   that other upstream WREADY gates may be added while retaining ungated enable.
   The candidate uses accepted VALID/READY and active-AW ownership. A separate
   full-FIFO test holds a following AW/W behind vendor AW and B stalls, then
   confirms exactly one next-burst acceptance after ownership retires.

3. **The original read owner is protected by FIFO emptiness.** The extracted
   production read logic clears `rd_inflight` on vendor RLAST and reconstructs
   the upper route bits from one latched SID. With all 16 responses buffered
   in the actual 133-bit FIFO and RREADY=0, `rd_inflight` is already clear, but
   a pending different-SID AR remains blocked. Every old RID/data/LAST stays
   associated with S00 during drain, then the S05 request accepts and returns
   its correct full RID. The candidate retains its full ARID until the final
   downstream RLAST handshake, a stricter ownership boundary. Candidate
   traffic tests S00/S02/S05 prefixes, including late SID changes and the last
   buffered beat. These are finite simulation and source-contract checks,
   not formal verification of every possible schedule or full board `top.v`.

All eight unmodified generated FIFO source files compile as supplied. No
functional FIFO substitute or patched vendor file is used. Their distributed
RAM implementations are behavioral Verilog for this configuration and need no
official primitive library beyond those sources. Known ModelSim warnings are
unused water-level outputs inside generated wrappers and the installation's
optimization option. They do not indicate an absent FIFO model. The physical
DDR3 controller is not compiled/simulated; an independent stub reproduces its
unthrottleable W-consumption and R-emission interface and arbitrary schedules.

The candidate waits for the actual FIFO water level to cover the complete
accepted AWLEN+1 before offering vendor AW. Tests cover AW before W, bubbled W,
vendor AW stalls, arbitrary vendor W slots, partial final strobes, stable
accepted ID/address/LEN, blocked B and no early B from upstream WLAST.
Simultaneous read/write tests fill a complete 16-beat read burst without any
vendor RREADY port and drain it through downstream stalls without overflow.

Unsupported 17-beat requests, physical alias addresses at `0x10000000`, bad
alignment/SIZE/BURST, and 4 KiB crossings are flagged and never accepted or
truncated. Both write and read tests accept an exact physical end at
`0x10000000`, preserving address `0x0ffffff0` as all 28 vendor bits. The
candidate has no DECERR/drain machinery for unsupported requests. A production
integrator must enforce valid requests; a violation may require common reset
and can otherwise leave the source waiting forever.

Common resets cover a partially staged write, pending vendor AW, scheduled
vendor W, pending vendor read, full buffered R and pending B. Adapter, actual
FIFOs, vendor stub, core/front harness and lease model reset together. Clean
restarts return no ghost responses/publications/releases. No independent local
reset or timeout recovery is claimed.

Selected used-source SHA-256:

| Source | Hash |
| --- | --- |
| `fpga_v8_ddr_adapter.v` | `5b84936d95c74e10bec28734172b49a175e1a17725bc73b3fade9ae089a5e2b8` |
| `fpga_v8_top_bid_snapshot.v` | `8db41a51bb13f6ae8212ae4bc5e45bbabad1e532b6bd6e6f186f49e040ce8fd5` |
| `fpga_v8_top_read_route_snapshot.v` | `5d929cd5bdae8d55ed4c99e268c11ad90c8d9315283fb1c705ca9391968465d7` |
| Actual `ddr_fifo16_w.v` | `d5deeb12d206e7707a0629d911848f2f0af53abcfa71ae3ce16c230cf7013948` |
| Actual `ddr_fifo16_r.v` | `d91a12b84d41250e0553769e9d786d6f55cd9af6f96e46c62dd499daec683436` |
| Inspected actual `ddr3.v` interface | `2cc25d03394260e553094de5337ab411a3241b5ecda330837ab80c0ea674d404` |

`artifacts/results.json` records all source hashes, exact compiler/simulator
commands, positive pass markers, complete output hashes, vendor trace counts,
unchanged-dependency assertion and FIFO/controller simulation status.
`artifacts/production_glue_excerpt.bin` retains exact bytes from the inspected
top ranges. Case directories retain vectors, full memory dumps and traces.
Handwritten candidates are ASCII Verilog-2001; only test code uses
SystemVerilog. Candidate module names have exactly one definition in the
production source plus migration source trees, excluding generated artifacts.

For production review, the proven necessary BID change is to stop forwarding
zero and preserve the accepted writer ID. Any future integration must also
keep accepted W enable gating, full-burst vendor staging, read ownership through
buffer drain, valid address/length narrowing, common reset, actual route-ID
mapping, and DDR AP/control wiring. No production change is applied here.
Source leasing, output allocation/disjointness, host CLAIM/copy/ACK endpoint,
crossbar arbitration and CDC remain outside this validation. No FPGA Fmax,
timing closure, board throughput or unchanged-driver support is claimed.
