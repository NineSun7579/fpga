# Cooperative core integration evidence

The final five-case ModelSim 10.6e regression passes. It uses the migration
`.venv/Scripts/python.exe` and `C:/modeltech64_10.6e/win64`. All new files and
generated evidence are confined to `cooperative_core/`. Dependency RTL was
read-only and its hashes stayed unchanged during the regression. No PDS,
production FPGA project or board application was run or edited.

| Suite | Geometry (input -> output) | Claims / releases | Published frames | Complete host-copy bytes | Cycles |
| --- | --- | --- | --- | --- | --- |
| `leases_4x3` | 4x3 -> 4x5, top 1 | 3 / 3 | 3 | 180 | 3,993 |
| `faults_odd_1x1` | 1x1 -> 1x6, top 2 | 3 / 3 | 1 | 18 | 3,795 |
| `common_reset_5x3` | 5x3 -> 5x6, top 1 | 5 / 1 | 1 | 90 | 5,192 |
| `invalid_output_range` | 4x3 -> 4x5, bank0 at 0x10000000 | 2 / 2 | 0 | 0 | 3,784 |
| `full_640x480` | 640x480 -> 640x640, top 80 | 1 / 1 | 1 | 1,228,800 | 1,138,264 |

The reset suite deliberately cancels four outstanding leases by resetting every
model and the DUT together; its 5/1 count reflects four reset reconciliations,
not an ordinary lease release. No canceled transaction later publishes or
returns a ghost release.

Python compares 1,229,088 successful output bytes in total, without truncation.
It also compares 933,888 camera-memory bytes, including untouched burst slots
as guards. The full case checks all 19,200 camera W words from 3,072 camera
bursts, plus all 76,800 single-beat bridge writes. Its trace contains 79,872
independently audited RR selections and B retirements. All six camera streams
compete simultaneously with randomized slave AW/W/B and AR/R stalls/delays.
Camera bursts alternate 16/3/5/1 beats with independent BREADY and W bubbles.
Every camera W word, ID, beat count, full AW descriptor and B route is checked.

The small tests check ownership and protocol details across the actual three
connected modules: two READY outputs; HOST_READING retention; input backpressure
when both outputs are owned; stable claimed metadata while the other bank is
written; stale sequence/generation ACKs returning SLVERR without freeing; last
B held without early READY/CLAIM/release; input-source leases held through
release backpressure; independent host AW/W order; a queued host write behind
blocked B; a queued AR behind stalled R with same-edge R/AR replacement;
RRESP and final-BRESP faults draining before freeing without publication;
partial last words; invalid physical output range rejected before bridge AXI;
and common reset during AR/AW/W stalls and a delayed final B.

The source memory vectors explicitly encode little-endian RGB565. The Python
golden independently expands channels by bit replication and pads rows with
114. Host copies read every modeled DDR byte before ACK. The testbench checks
every strobed bridge byte during writes, every final strobe, untouched trailing
lanes/guards, payload stability under backpressure, and unknown controls/data.
A separate staging scoreboard requires a packed-word capture before m6 AW.

Port declarations were read and connections written manually. A final
declaration-versus-binding audit additionally found no missing, duplicate or
unknown named bindings:

| Dependency instance | Explicit bindings | Interface audit |
| --- | --- | --- |
| `control` | 52 | Clock/reset, certified lease, command/completion, exact release metadata, state and full AXI-Lite |
| `bridge` | 54 | Command/status, four explicitly open debug snapshots, all 4-bit-ID AR/R and AW/W/B fields |
| `write_arbiter` | 48 | Seven packed complete AW/W/B masters, unflattened DDR writer and diagnostics |

Slot m6 is the high part of each concatenation; camera m0 is least significant.
Returned B slices are cameras `[23:0]` / `[11:0]` / `[5:0]` and bridge
`[27:24]` / `[13:12]` / `[6]`. All IDs remain four bits; no IDs are rewritten.
AR/R is directly forwarded, suitable for future crossbar S02 review. Both
output addresses and `DDR_ADDRESS_LIMIT=0x10000000` are explicit defaults.
ASCII checks pass for all handwritten core files, and the new module name has
exactly one definition in production `source/` plus migration RTL, excluding
generated simulation artifacts.

The completed arbiter's API is synchronous active-low `rst_n`, not the
active-high reset described in the initial request. The wrapper follows the
actual verified dependency interface and connects common `rst_n` directly.

Used RTL SHA-256 hashes:

| Source | SHA-256 |
| --- | --- |
| `fpga_v8_cooperative_core.v` | `c94c7aa1cd97535d3bbe50239199c7595198b3f0f74aa19af26670358757064e` |
| `../cooperative_control/fpga_v8_coop_control_axil.v` | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |
| `../cooperative_axi/fpga_v8_raw_frame_axi.v` | `c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f` |
| `../cooperative_arbiter/fpga_v8_ddr_write_arbiter.v` | `c0982b49617f416f96d3b338df822c5ce0e0701aa8425f766da85f00a8ffc969` |
| `../raw_preprocess/fpga_v8_raw_letterbox.v` | `b1ffda1799c350973444ff3bbd6cea2288c6155426397ca8ee62c1cca7d5d1ad` |
| `../raw_preprocess/fpga_v8_rgb888_pack128.v` | `20b691d328b6dc43feb42b6352b169156002a3931a43d003f871fff2289613af` |

`artifacts/results.json` contains exact compile/simulation commands, positive
pass markers, source/test hashes, frame dump hashes, byte counts, trace counts,
elapsed simulation time and the final unchanged-source-hash assertion. Each
case retains its vectors, complete binary dumps, trace and simulator logs.

This remains an isolated internal-IO candidate. Production DDR/crossbar wiring,
PCIe address-window installation and host-side CLAIM/copy/ACK implementation,
safe source leasing, common reset/CDC integration, physical allocation and
mutually disjoint output banks remain external work. The simulation supplies a
stable leased source model; it does not prove original camera RAW stability.
The default bank allocation is not confirmed. No unchanged host-driver support,
installed endpoint, synthesis, timing closure or board throughput is claimed.
