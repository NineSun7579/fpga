# Current cooperative component PDS synthesis evidence

The promoted address-fixed bridge **`raw_frame_axi_03`** compiled and
synthesized successfully. The standalone two-bank controller and seven-master
DDR write arbiter also synthesized successfully after the bridge, in separate
isolated projects. All four PDS invocations returned **exit code 0**. The
expected compile databases, synthesis databases, netlists, and resource reports
exist. All five RTL SHA-256 hashes remained unchanged after all runs.

Target for all projects: **Logos2 PG2L100H -6 FBG484**, PDS 2022.2-SP6.4
build 146967, nominal 150 MHz local clock, all internal interface ports
marked virtual. This is component resource evidence, not integrated-core or
whole-board timing/placement acceptance.

`raw_frame_axi_02` is stale for the current bridge source and remains
historical and immutable. Its 48 files were compared byte-for-byte by SHA-256
before and after this work; none changed. The previous root report is retained
as [REPORT_02_historical.md](REPORT_02_historical.md).

## Actual current resources

| Component project | LUTs | Registers | Latches | DRM | APM | Virtual port bits |
|---|---:|---:|---:|---:|---:|---:|
| `raw_frame_axi_03` | 764 | 874 | 0 | 0.0 | 0.00 | 658 |
| `coop_control_01` | 782 | 938 | 0 | 0.0 | 0.00 | 590 |
| `ddr_write_arbiter_01` | 672 | 89 | 0 | 0.0 | 0.00 | 1,788 |
| Separate-component arithmetic sum | **2,218** | **1,901** | **0** | **0.0** | **0.00** | — |

The arithmetic sum is 3.33% of 66,600 device LUTs and 1.43% of 133,200
device registers. It adds actual separate component results; it is not an
integrated-core synthesis result or an additional board resource guarantee.
Connected-port optimization and surrounding core logic can change totals.
No unfinished core or full production top was included.

Actual vendor reports:

- [Current bridge synthesis report](raw_frame_axi_03/synthesize/fpga_v8_raw_frame_axi.snr)
- [Two-bank controller synthesis report](coop_control_01/synthesize/fpga_v8_coop_control_axil.snr)
- [Seven-master arbiter synthesis report](ddr_write_arbiter_01/synthesize/fpga_v8_ddr_write_arbiter.snr)

Each project's `output_audit.json` confirms that every reported mapped cell
count matches its generated structural netlist and that every IO buffer has
the virtual IO attribute. All three audits passed. Aggregated evidence is in
[subset_summary.json](subset_summary.json).

The bridge total matches historical 02: 764 LUTs and 874 registers. The new
source changed the mapped mix from **59 to 58 GTP_LUT5** and **139 to 140
GTP_LUT6**. No old resource count was assumed or used as a pass condition.

| Mapped cell type | Bridge 03 | Two-bank controller | Seven-master arbiter |
|---|---:|---:|---:|
| GTP_DFF_C | 12 | 15 | 0 |
| GTP_DFF_CE | 861 | 922 | 0 |
| GTP_DFF_PE | 1 | 0 | 0 |
| GTP_DFF_P | 0 | 1 | 0 |
| GTP_DFF_RE | 0 | 0 | 88 |
| GTP_DFF_SE | 0 | 0 | 1 |
| GTP_LUT1 | 1 | 4 | 1 |
| GTP_LUT2 | 24 | 5 | 2 |
| GTP_LUT3 | 121 | 14 | 4 |
| GTP_LUT4 | 115 | 75 | 6 |
| GTP_LUT5 | 58 | 102 | 294 |
| GTP_LUT6 | 140 | 203 | 327 |
| GTP_LUT6CARRY | 218 | 289 | 29 |
| GTP_LUT6D | 87 | 90 | 9 |
| GTP_MUX2LUT7 | 0 | 0 | 273 |
| GTP_MUX2LUT8 | 0 | 0 | 1 |
| GTP_GRS | 1 | 1 | 1 |
| GTP_INV | 1 | 1 | 1 |
| GTP_INBUF | 245 | 279 | 1,502 |
| GTP_OUTBUF | 413 | 311 | 286 |

## Pinned sources and elaborated defaults

Bridge 03 registers exactly the same three source paths as before, with the
promoted bridge hash. The controller and arbiter projects each register one
stable source. No wrapper, vendor IP, testbench, or core source was registered.

| RTL path relative to `fpga_v8_migration` | SHA-256 |
|---|---|
| `raw_preprocess/fpga_v8_raw_letterbox.v` | `b1ffda1799c350973444ff3bbd6cea2288c6155426397ca8ee62c1cca7d5d1ad` |
| `raw_preprocess/fpga_v8_rgb888_pack128.v` | `20b691d328b6dc43feb42b6352b169156002a3931a43d003f871fff2289613af` |
| `cooperative_axi/fpga_v8_raw_frame_axi.v` | `c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f` |
| `cooperative_control/fpga_v8_coop_control_axil.v` | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |
| `cooperative_arbiter/fpga_v8_ddr_write_arbiter.v` | `c0982b49617f416f96d3b338df822c5ce0e0701aa8425f766da85f00a8ffc969` |

PDS selected each intended top as the sole uninstantiated root. The audits
parsed the actual elaborated parameter values from the PDS logs and compared
them to the manifests; all match.

| Top | Actual elaborated default parameters |
|---|---|
| `fpga_v8_raw_frame_axi` | WIDTH=640, HEIGHT=480, OUT_HEIGHT=640, TOP_ROWS=80, FILL_VALUE=114, ID_WIDTH=4, AXI_ID=1, **DDR_ADDRESS_LIMIT=0x10000000** |
| `fpga_v8_coop_control_axil` | OUTPUT_BANK0_ADDR=0x08000000, OUTPUT_BANK1_ADDR=0x08200000, OUTPUT_LENGTH=1,228,800, DEVICE_ID=0x434f4f50, VERSION=0x00010000; fixed two-bank implementation |
| `fpga_v8_ddr_write_arbiter` | **MASTER_COUNT=7**, ID_WIDTH=4, ADDR_WIDTH=32, DATA_WIDTH=128, OWNER_WIDTH=3 |

The bridge's new DDR limit is the exclusive 256 MiB physical address bound;
the RTL constrains it to at most `0x10000000`. This replaces the old bridge's
512 MiB decode limit. The promoted source's ModelSim PASS was supplied by
the parent; no simulation was rerun for this synthesis task.

Per-project evidence includes `expected_inputs.json`, `registration_check.json`,
`source_inputs_before.json`, per-invocation post-stage hashes,
`source_inputs_final.json`, and `output_audit.json`. The audits reread all five
inputs after all PDS runs.

## Actual warnings and errors

Every current log has **0 compiler errors** and empty stderr. No emitted
width/truncation/extension or latch diagnostics were found, and all three
mapping reports explicitly record **zero latches**.

| Log | Warnings | Errors |
|---|---:|---:|
| Bridge 03 standalone compile | 15 | 0 |
| Bridge 03 synthesis invocation including prerequisite compile | 692 | 0 |
| Controller synthesis invocation including prerequisite compile | 666 | 0 |
| Arbiter synthesis invocation including prerequisite compile | 1,812 | 0 |

PDS reruns compile as a prerequisite of synthesis. The bridge's 14
constant-probe warnings therefore occur in both its standalone compile log
and its synthesis invocation log. For controller/arbiter, only `-run synthesize`
was requested; the compile phases were PDS prerequisites.

| Warning category in synthesis invocation logs | Bridge 03 | Controller | Arbiter |
|---|---:|---:|---:|
| License expires in 29 days | 1 | 1 | 1 |
| `Loop was found during constant probe` | 14 | 11 | 23 |
| `Public-4008`: dangling instance cleaned | 5 | 32 | 0 |
| Constant register removed | 9 | 32 | 0 |
| Max fanout constraint could not be honored | 2 | 0 | 0 |
| Net renamed to avoid name conflict | 3 | 0 | 0 |
| Interface IO count exceeds 285 physical package IO | 1 | 1 | 1 |
| `Timing-4087`: unconstrained output bit | 413 | 311 | 286 |
| `Timing-4086`: unconstrained input bit | 244 | 278 | 1,501 |

The bridge fanout warnings name the `gtp_inv` driven net `N113`. The five
bridge dangling instances are `raw_pipeline/done` and `raw_pipeline/m_data[22]`,
`[23]`, `[6]`, `[7]`. Its constant removals cover low address bits [3:0]
and `output_packer/byte_count[4]`. The controller's constant removals are
30 fixed destination-address bits and each AXI-Lite response bit [0]. Its
dangling cleanup entries name those same 30 `cmd_dst_addr` bits plus
`s_axil_bresp[0]` and `s_axil_rresp[0]`.

Constant-probe loop messages lack source locations and remain recorded as
unresolved compiler diagnostics. No RTL was edited to silence them. Original
warnings with log line numbers are retained in each project's
`diagnostics_extracted.txt`; category counts are in `output_audit.json`.

## Virtual IO, clock, and acceptance limits

Each local `component.fdc` contains only a nominal 150 MHz clock
(6.666667 ns) and `PAP_IS_VIRTUAL_IO=TRUE` for all ports. Bridge/arbiter
clock port: `clk`; controller clock port: `core_clk`. PDS and netlist audits
confirm 658, 590, and 1,788 virtual IO buffer instances respectively.

The synthesis reports still compare these internal interfaces with 285
physical IO and warn that the counts exceed the package. These components
are **not whole-board placeable tops**. The unconstrained IO warnings are
preserved; no production pin, voltage, timing, PLL, DDR, or PCIe constraints
were imported. Embedded synthesis timing estimates and `All Constraints Met`
summaries do not constitute routed timing or measured frequency acceptance.

No device mapping, PnR, post-route timing, power run, bitstream, JTAG, board
operation, or simulation was run. Audits found no forbidden-stage directories
or bitstream files. Every task write stayed under `component_synthesis`.
No production PDS, constraints, IP, board, or candidate RTL file was written.

## Sequential commands and isolation evidence

The four actual invocations are recorded with absolute argument arrays,
working directories, timestamps, exit codes, and database checks in each
project's `run_results.json`.

| Project | Requested stage | Start / finish, 2026-10-05 +08:00 | Exit |
|---|---|---|---:|
| `raw_frame_axi_03` | compile | 07:07:54 / 07:07:58 | 0 |
| `raw_frame_axi_03` | synthesize | 07:07:59 / 07:08:11 | 0 |
| `coop_control_01` | synthesize | 07:15:20 / 07:15:32 | 0 |
| `ddr_write_arbiter_01` | synthesize | 07:16:44 / 07:16:55 | 0 |

For each invocation, `pds_shell.exe` was
`C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`, with arguments
`-project <isolated-project>/project.pds -run <stage> -work_dir <isolated-project>`.
All RTL registrations are safe relative paths. PDS reported 9 seconds for
each synthesis stage and peak memory of 364 MB (bridge), 368 MB (controller),
and 350 MB (arbiter).

`Get-Process pds,pds_shell` was clear before preparation, before each
invocation, and after each project completed. Saved `process_check_*.json`
files contain empty process lists. The final cross-project check in
`final_process_check.json` is also clear. No process was killed or modified.

`historical_02_before_03.json` records the 48 historical file hashes;
`historical_02_after_03.json` confirms all 48 still match. No historical
output directories were erased or reused. The main agent may now use this
subset evidence and separately synthesize the integrated core once its
integration test is complete.
