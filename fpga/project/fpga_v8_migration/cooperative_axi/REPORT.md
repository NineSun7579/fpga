# Promoted physical DDR limit validation

The physical address correction is promoted into the original isolated module
`fpga_v8_raw_frame_axi`. Its default and maximum `DDR_ADDRESS_LIMIT` are
`0x10000000` (256 MiB). Original-name RTL and full regression are current;
the staged copy and all `address_fix/artifacts/` results remain unchanged as
history. No board/source, shared preprocessing, IP, or PDS file was edited.

Diagnostic: live `project/source/top.v:626` assigns
`ddr3_aw_addr <= ddr_axi_awaddr[27:0]`; line 647 assigns
`ddr3_ar_addr <= ddr_axi_araddr[27:0]`. The 512 MiB crossbar decode does not
preserve address bit 28 at the physical DDR adapter. `0x10001000` aliases to
`0x00001000`, so both source and destination must be bounded to 256 MiB.
Overrides must be nonzero, 16-byte aligned, and no larger than `0x10000000`.
The `0x20000000` override and addresses above the physical limit are rejected.

Result: PASS, ModelSim SE-64 10.6e, run on 2026-10-05. Reproduce from this
directory with:

```powershell
& 'C:/Users/NineSun/anaconda3/python.exe' run_tests.py
```

The authoritative machine report is `artifacts/results.json`, including tested
module/RTL hash, exact compile/simulation argument lists, original source and
shared hashes, per-frame output hashes, rejection counts, stale synthesis
status, and transcript markers. All five compilation logs have zero warnings
and zero errors. Simulation logs have zero errors and only the existing
`vsim-8891` disabled-optimization warning. The configuration testbench marks
unused output ports explicitly unconnected to avoid missing-port warnings.

| Case | Geometry W/H/OUT_H/TOP | DDR limit | Retired frames | Compared bytes | Simulation time |
| --- | --- | --- | ---: | ---: | ---: |
| small_4x3 | 4/3/5/1 | 0x10000000 | 16 | 960 | 1.590 s |
| overflow_1x1 | 1/1/6/2 | 0x10000000 | 16 | 288 | 1.575 s |
| smaller_limit_4x3 | 4/3/5/1 | 0x02000000 | 16 | 960 | 1.653 s |
| full_640x480 | 640/480/640/80 | 0x10000000 | 1 | 1,228,800 | 3.164 s |
| invalid_config | Eight invalid parameter sets | Mixed invalid | 0 | 0 | 1.532 s |

Total: 49 retired frames and 1,231,008 bytes compared in the AXI testbench and
again by independent Python, with 45 rejected address commands and eight
rejected parameter configurations. Fifteen frames intentionally retire with
sticky error (five response faults in each small suite); the rest retire
without error. Faulted frames still drain the configured read/write counts
and preserve output byte ordering. No failed frame is described as successful.

Each of three small suites covers 15 invalid-address commands, three sequential
clean frames, independent RID/RRESP/RLAST/BID/BRESP faults, exact end-of-memory
reads and writes, adjacent disjoint ranges, and five common-reset phases
followed by clean frames. Rejections include source/destination `0x10001000`
aliases and old `0x20000000` addresses. Base-at-limit and footprint-end-above-
limit cases also reject. Every accepted AR/AW bus footprint is checked against
the configured physical limit. All rejected commands leave AXI idle and do
not report `done` or change the completed frame ID.

Source and destination ranges ending exactly at `0x10000000` pass. For 4x3
input and 4x5 output, their bases are `0x0fffffe0` (32 bus bytes) and
`0x0fffffc0` (64 bus bytes). For 1x1 input and 1x6 output, they are
`0x0ffffff0` and `0x0fffffe0`. The `0x02000000` override also passes exact
boundary reads/writes and rejects footprints beyond the smaller limit.

The configuration test rejects zero width, insufficient output height,
excessive top padding, a footprint larger than DDR, zero address limit,
unaligned `0x08000001`, forbidden `0x20000000`, and a `0x10` limit too small
for the frame. It checks `CONFIG_OK` directly and the observable command
rejection contract for every instance.

The 4x3 input uses two R words with four meaningful pixels in the final word.
Its 60-byte output uses four W words with final WSTRB=0x0fff. The 1x1 case
uses one meaningful source pixel and packs 18 output bytes into a full word
plus two bytes, final WSTRB=0x0003. It also uses ID_WIDTH=3 and AXI_ID=3.
Source padding lanes are poisoned; destination padding and guard bytes remain
0xa5.

The default full baseline has 38,400 AR/R transactions and 76,800 AW/W/B
transactions. It retires in 950,492 simulated active cycles. Every final B
is delayed by 80 cycles; `done` and `cmd_ready` remain low throughout the
81 observed slave scheduling cycles before that final response is presented.

Full output SHA-256:

```text
a5bffe15ad024e7311ac19ec729420dc83db3d37df7fccd509cedab092811074
```

Observed channel coverage for the full baseline: 55,680 AR stall cycles,
52,486 AW stall cycles, 212,476 W stall cycles, 172,800 R bubble cycles, and
307,276 B bubble cycles. AR, AW, and W payload/valid stability are asserted
through backpressure. The testbench checks transaction counts and all
outstanding state at completion, snapshots while a second command is pending,
single-cycle `done`, sticky errors, and restart without ghost responses.

The promoted bridge equals the staged physical module after restoring the
original module name and source comment. Its SHA-256 is:

```text
c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f
```

Every case's output SHA-256 values, frame/reset/address markers, counts, and
cycle metrics match the staged results after pass-marker renaming. The frame
testbench matches the staged version after module/pass-marker renaming; the
configuration testbench additionally has explicit unused output connections.
The module names of all six cooperative original/staged Verilog files are
unique across the project, and their content is ASCII. Shared preprocessing
RTL hashes stayed unchanged throughout the regression:

```text
fpga_v8_raw_letterbox.v
b1ffda1799c350973444ff3bbd6cea2288c6155426397ca8ee62c1cca7d5d1ad
fpga_v8_rgb888_pack128.v
20b691d328b6dc43feb42b6352b169156002a3931a43d003f871fff2289613af
```

The completed `component_synthesis` run observed the pre-address-fix bridge
SHA-256 `235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40`.
That result is stale for the promoted bridge. Isolated component compile and
synthesis must be rerun against the current hash before relying on the PDS
result; no PDS run was started by this promotion task. This stale status and
old hash are recorded in the current machine report.

Promotion and original-name ModelSim validation are complete. This result
validates the isolated candidate against behavioral memory. Board/DDR
arbitration, protocol/source integration, timing closure, and hardware speedup
remain outside this subtask. Publish only on `done && !error`; outstanding
AXI requires common bridge/interconnect/slave reset.
