# Actual capture/core/generated-FIFO DDR regression

All three suites pass ModelSim with actual immutable capture_lease RTL,
unmodified production camera w_en/w/w_ctrl and axi_dma_write,
actual cooperative_core/control/bridge/write arbiter, the production read
crossbar, actual ddr_adapter and generated camera/DDR FIFOs. Official Pango
FIFO/DRM primitives are compiled without substitutes. Production/candidate
RTL compiles as Verilog-2001; the harness and sparse memory use SystemVerilog.

Run `python run_tests.py` in this directory. All writes stay here.

| Suite | Geometry RAW -> RGB | Published | Paired outputs | Front W / vendor W | Front R / vendor R | RAW frame drops |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| small_leases | 16x16 -> 16x24 | 5 | 5 | 1,165 / 1,165 | 685 / 685 | 3 |
| small_reset | 32x16 -> 32x24 | 4 | 3 | 1,999 / 1,998 | 887 / 887 | 1 |
| full_640x480 | 640x480 -> 640x640 | 5 | 5 | 578,565 / 578,565 | 768,005 / 768,005 | 3 |

The reset case deliberately cancels one accepted front AW and one staged W
word while the core is busy. Those obligations are removed by the coordinated
camera/DMA/core/read-crossbar/adapter/FIFO/vendor reset, with no ghost B/R.
One published RAW frame has a lease-bound RAW copy but no completed prepared
copy because its bridge transaction was cancelled. It is explicitly marked
`cancelled_by_coordinated_reset`; no output completion is claimed for it.
The new generation accepts two later good frames and rejects the old RAW
release without freeing the new bank.

Totals: **581,729 front W words**, **581,728 physical vendor W words**,
**769,577 complete R words** at both physical memory and returned AXI boundary,
**14 certified RAW copies** and **13 exact paired software/FPGA prepared
inputs**. The prepared comparisons contain **6,156,672 bytes**. All RAW copies
including full tags contain **3,078,880 bytes**. All 128 data bits, ID, last,
strobe and unknown-state checks are strict; even bytes outside software-visible
regions are retained in complete bus-word checks. These geometries are all
16-byte aligned and their final WSTRB is exactly 0xffff.

Full suite counts:

- Camera RAW/tag W: **192,005** words, from five full captures.
- Prepared RGB/fill W: **384,000** words, compared independently from the
  currently claimed RAW fixture on every word.
- Five competing writers: **2,560** words, 32 independent 16-word bursts each.
- Core reads: **192,000** words with full RID 0x21 (route 010, ID 1).
- Host reads: **576,005** words with full RID 0x06, under RAW or output claim.
- Physical/front write AW and returned B: **396,165** each.
- Physical/front read AR: **228,005**, all retired with strict RLAST.
- Five actual output CLAIM transactions, 55 bound descriptor/register reads,
  and 35 real AXI-Lite writes. Each output copy attempts a stale-generation ACK
  (SLVERR), then exact bank/sequence/generation ACK (OKAY).

The full and small lease suites retain the host RAW lease after actual
cooperative release, then hold both output READY banks. Capture publishes
two further RAW banks; the actual core input_ready remains low. Whole future
sensor frames are dropped with no camera AW/W or publication. A host-only RAW
release cannot clear an unclaimed cooperative obligation. Output ACK frees
the exact output bank and the core converts the queued descriptor, returning
its real source release to the manager. Frozen source and output images are
checked during ownership, legacy boolean ACK and stale releases. A fifth new
sensor frame after all earlier output ACKs proves actual source/output reuse.

The source is real continuous RGB565 within rows, with fixed line blanking,
and never samples ready. The camera overflow/error machinery stays inactive.
Natural vendor AW/AR/W/R delays come from the unchanged existing scheduling
stub. A sparse exact-address memory layer records only actual vendor W
consumption and serves those written bytes on R; no RAW preload occurs. It
uses the entire legal 28-bit physical address space, with disjoint RAW, output
and competitor guards. The physical DDR3 vendor IP is not simulated.

The production read crossbar arbitrates slot 0 host and slot 2 core requests.
Host intentionally stalls consumption until a complete unthrottleable vendor
burst is queued. The existing original-top read-route snapshot runs as an
actual-FIFO shadow on every accepted AR and vendor response. Its full routed
RID/data/last match the adapter under stalls. New requests cannot change the
route before the old final R is consumed. This validates that boundary; it is
not a claim of generic full-top correctness.

Artifacts are under `artifacts/<suite>/`. For each published identity
`g<generation>_s<sequence>`, retain:

| File suffix | Exact binary format |
| --- | --- |
| `_completed_raw.bin` | Actual DDR snapshot: RGB565 payload plus 16-byte tag |
| `_rawbankcopy.bin` | Same bytes read through host DDR path while RAW lease held |
| `_source_pixels_fixture.bin` | Independent LE RGB565 fixture, no tag |
| `_software_preparedinput.bin` | Software NHWC uint8 RGB888 from captured RAW |
| `_preparedinput.bin` | Actual output DDR host copy under control CLAIM |

The RAW file has width*height*2 RGB565 bytes, then **little-endian seq32 + twelve
zero bytes**. Full RAW is 614,416 bytes; full fixture is 614,400 bytes. Prepared
full input is 1,228,800 NHWC row-major RGB bytes, component bit replication,
with 80 rows of byte 114 above/below. No PNG path or repack is used. The three
small/full cases each have `checker.json` with camera=4, source/output banks,
sequence, generation, token64, source/raw/software/output SHA-256, formats,
filenames, exact byte counts, cancellation status and trace counts.
`artifacts/results.json` aggregates all counts, exact ModelSim commands and
current source/contract hashes.

| Current contract file | SHA-256 |
| --- | --- |
| fpga_v8_capture_contract_memory.sv | `2aca2790be2e38590119e8392049a32b46910d8087a7b020b3738ad6b84e0f5b` |
| tb_capture_core_contract.sv | `651fdee2152ad9e2e6c6476c38a4eeb493b1977ae764da5fa5aef72b5c92043e` |
| run_tests.py | `9b0ca901f381c61d71e65a90cd97583aab5e068d3f46a289c8a3d7e7b1918be6` |
| verify_contract.py | `e8e6f6629eace723e8f73a3c0b43217ca6faba97a3868a6c83d19e8e70f32128` |

Latest simulator elapsed times: 1.704 s small_leases, 1.797 s small_reset,
158.719 s full_640x480. Final independent checker replay additionally verifies
all five competitors complete each reset epoch and all final RAW/output leases
and AXI obligations drain.

`immutable_hashes_before.json` and `immutable_hashes_after.json` contain
**119 matching files**: the fixed 42 production pins, the complete finalized
capture_lease tree including all existing evidence, added actual FIFO/read
crossbar dependencies, and actual core/control/bridge/arbiter/adapter/stub RTL.
Neither capture_lease nor production/dependency files were edited. New module
names are unique in a Python bytes-regex scan across source and active migration
Verilog/SystemVerilog excluding generated artifacts. No PDS, SSH, board, NPU,
capture endpoint or other parent integration directory was modified.

Remaining parent bindings: the capture AXI-Lite endpoint and host protocol,
PCIe transport, candidate whole-top wiring, source-region exclusivity against
other writers, persistent fresh-generation allocation, coordinated reset of
all live DDR obligations, and real descriptor/release CDC where clocks differ.
Synthesis and physical DDR/board validation remain separate work.
