# DDR adapter with the actual generated FIFOs

Compile and synthesis both returned **0** for `fpga_v8_ddr_adapter` on
**PG2L100H -6 FBG484**, PDS 2022.2-SP6.4 build 146967. The actual mapping is
**370 LUTs, 158 registers, 0 latches, 0 DRM and 0 APM**. Of the total LUTs,
231 implement logic and 139 implement distributed RAM. All 781 scalar IO
buffers are virtual; `clk` has a nominal 150 MHz constraint only.

| Actual hierarchy, included in total | LUTs | Registers | Distributed RAM LUTs |
|---|---:|---:|---:|
| Adapter top | **370** | **158** | **139** |
| `write_fifo` subtree | 91 | 19 | 72 |
| `read_fifo` subtree | 79 | 14 | 67 |

The memories mapped to **138 GTP_RAM32X2DP + 1 GTP_RAM32X1DP**, not DRM36K
blocks. Memory LUTs are included in the 370 total and must not be added again.
The structural netlist independently matches every cell count in the `.snr`.
Full mapped-cell counts are in `output_audit.json`.

## Actual sources and interface

The project contains exactly the adapter and the eight generated FIFO RTL
files used by `ddr_adapter_contract/run_tests.py`. Every FIFO hash matches
that regression's `artifacts/results.json`. All nine sources are unchanged
ASCII; actual hashes were captured before compile, after both stages and
in the final audit. No DDR3 controller, simulation stub, snapshot module,
testbench, `.idf`, or replacement FIFO was registered.

| Source relative to project | SHA-256 |
|---|---|
| `fpga_v8_migration/ddr_adapter_contract/fpga_v8_ddr_adapter.v` | `5b84936d95c74e10bec28734172b49a175e1a17725bc73b3fade9ae089a5e2b8` |
| `ipcore/ddr_fifo16_w/ddr_fifo16_w.v` | `d5deeb12d206e7707a0629d911848f2f0af53abcfa71ae3ce16c230cf7013948` |
| `ipcore/ddr_fifo16_w/rtl/ipm_distributed_fifo_ctr_v1_1_ddr_fifo16_w.v` | `e0c9990effd8907e68e329d76e28517a044821af16e8f644b2713099a958d4b5` |
| `ipcore/ddr_fifo16_w/rtl/ipm_distributed_fifo_v1_4_ddr_fifo16_w.v` | `1e266d686b505166952ad8c3ee4a4948d96d355a862fc003c4a7c09b65bb7d24` |
| `ipcore/ddr_fifo16_w/rtl/ipm_distributed_sdpram_v1_3_ddr_fifo16_w.v` | `d8936a8be42dd14679c99330cd2c162f6d193399a2af2ba15a73f5ac48936b12` |
| `ipcore/ddr_fifo16_r/ddr_fifo16_r.v` | `d91a12b84d41250e0553769e9d786d6f55cd9af6f96e46c62dd499daec683436` |
| `ipcore/ddr_fifo16_r/rtl/ipm_distributed_fifo_ctr_v1_1_ddr_fifo16_r.v` | `d94f42312d53f3be3e0cb9f5570fd8367e6d79783c9a0c7a6c949dcc673c8a33` |
| `ipcore/ddr_fifo16_r/rtl/ipm_distributed_fifo_v1_4_ddr_fifo16_r.v` | `5f5ee9c450ffaf137829c576ebf224895d6e414535c683a5cae886afcc646052` |
| `ipcore/ddr_fifo16_r/rtl/ipm_distributed_sdpram_v1_3_ddr_fifo16_r.v` | `a4186aa66fae0382599413af25772867891b41d7b67c48ade920021e515250e2` |

PDS analyzed and elaborated all nine definitions and selected the adapter as
the sole top. The source audit checked all eight instance bindings. The only
omissions are disabled read/write water outputs in the generated wrappers;
the adapter explicitly opens both almost-full/empty pairs. No missing-module
or black-box diagnostic exists. The top has 58 port declarations / 781 bits.

| Default / fixed contract | Verified value |
|---|---|
| PDS-elaborated DDR_ADDRESS_LIMIT | `0x10000000`, 256 MiB exclusive address bound |
| Upstream read ID / write ID | **7 / 4 bits** |
| Vendor address / ID / length widths | **28 / 4 / 4 bits** |
| Data width / maximum accepted burst | **128 bits / 16 beats** (`AWLEN` and `ARLEN` <= 15) |
| FIFO depth / write width / read width | **16 words / 144 / 133 bits** |
| Actual generated FIFO parameters | `ADDR_WIDTH=4`, `OUT_REG=0`, `RST_TYPE=SYNC`, `FIFO_TYPE=SYNC_FIFO` |
| Almost-full / almost-empty thresholds | **11 / 4**, unused by adapter |

The nine-source signature and bindings are in `source_signature_before.json`.
All FIFO, RAM and control subinstance parameters were parsed from actual PDS
elaboration and matched in `output_audit.json`. Upstream AW/AR validation
requires 16-byte alignment, SIZE=4, INCR, no 4 KiB crossing, and a valid end
address before capturing the narrowed vendor address/length.

## Actual warnings and their limits

| Warning category | Compile | Synthesis invocation |
|---|---:|---:|
| License expires in 29 days | 1 | 1 |
| Constant-probe loop | 18 | 18 |
| Constant register removed | 0 | 9 |
| Dangling instance cleaned | 0 | 16 |
| LUT carry fanout >10000, not replicated | 0 | 2 |
| Max fanout not honored | 0 | 10 |
| IO count exceeds package | 0 | 1 |
| Unconstrained output bits | 0 | 386 |
| Unconstrained input bits | 0 | 394 |
| **Total warnings / errors** | **19 / 0** | **837 / 0** |

Both stderr files are empty. Every diagnostic and original line number is
retained in `diagnostics_extracted.txt`; `warning_review.json` explains the
groups without suppressing them. There are no width/truncation, latch,
missing-module, black-box or undriven-net diagnostics.

Seven dangling entries remove unused FIFO almost-full/empty and disabled
water-level logic. **Write water level remains connected**, both as a top
output and as the adapter's condition for issuing vendor AW only when all
promised W words are present. Nine additional dangling entries and the nine
constant warnings cover aligned address low bits and B-response bit zero.

The fanout diagnostics remain unresolved: two report carry `N112.lt_3` /
`N112`, and ten report `N106_0`, `fifo_rst_1`, `N138_0`, `N134_0`, and
`N117_0`, twice each. The constant-probe loop warnings have no source
locations. Resource evidence does not establish their physical/timing effect.
All 781 IO exceed the package's 285 physical pins; no board timing, Fmax or
FPS acceptance follows from the local nominal clock.

The first output-audit attempt parsed only binary-valued parameters and
stopped at PDS's `RST_TYPE = SYNC`. Its failed result is preserved as
`output_audit_initial_parser.json`; correcting the audit parser verified the
same existing outputs without another PDS invocation or source edit.

## Commands, immutability and external requirements

`run_results.json` records full absolute argument arrays and working directory:
`C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe -project <this>/project.pds
-run compile|synthesize -work_dir <this>`.

| Stage, 2026-10-05 +08:00 | Start | Finish | Exit |
|---|---|---|---:|
| Compile | 10:17:18 | 10:17:21 | 0 |
| Synthesis | 10:17:22 | 10:17:32 | 0 |

PDS reports eight synthesis seconds and 343 MB peak memory. PDS's prerequisite
recompile is retained in synthesis stdout. Process checks were clear before
both stages and afterwards; no process was killed or modified. All 244 prior
component-evidence files are hash-identical, including the integrated core
and historical projects. Only the two new directories and root `REPORT.md`
were authorized for mutations.

This evidence excludes DDR3 controller/PHY behavior. Common reset of adapter,
fabric and vendor controller remains required. The vendor cannot backpressure
R; admission and the bounded 16-word buffering must preserve the tested
contract. Stable certified RAW leasing and safe physical allocation remain
external requirements. No ModelSim rerun, formal change, production/IP edit,
PnR, bitstream, JTAG or board operation was performed.
