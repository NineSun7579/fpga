# Current isolated PDS component evidence

The new **DDR adapter with all eight actual generated FIFO RTLs** and the
**connected AXI128 endpoint/controller** each passed compile and synthesis
with exit 0. Runs were sequential on **PG2L100H -6 FBG484**, with all top IO
virtual and a nominal 150 MHz clock. Candidate RTL and generated IP were
read-only; all **244** previous component-evidence files remain unchanged.

| Actual synthesized top | LUTs | Registers | Distributed RAM LUTs, included | Latches | DRM | APM |
|---|---:|---:|---:|---:|---:|---:|
| `ddr_adapter_01`: `fpga_v8_ddr_adapter` | **370** | **158** | **139** | **0** | **0** | **0** |
| `endpoint_ctrl_01`: `fpga_v8_endpoint_ctrl_synth` | **1,008** | **1,127** | **0** | **0** | **0** | **0** |
| Previous `cooperative_core_01`: `fpga_v8_cooperative_core` | 2,074 | 1,773 | 0 | 0 | 0 | 0 |

Each row is actual resource evidence from its own top. The endpoint top
contains the real controller; its mapped child rows are 187 LUTs / 191 FFs
for the endpoint and 821 LUTs / 936 FFs for the controller. This is a connected
synthesis, not a standalone endpoint estimate. The cooperative core already
contains another controller, so these rows must not be summed into a claimed
integrated-system resource count.

**Endpoint warning requiring follow-up:** PDS reports `Verilog-2021` at
endpoint source line 81: `eligible.addr_end_1` has no driver and is tied to
zero. The source assigns `addr_end` before the upper-window eligibility
comparison, but the effect of the generated tie-off is unresolved. Compile
success and the resource audit do **not** establish synthesized address-check
equivalence. The exact message and read-only source/netlist review are in
[endpoint report](endpoint_ctrl_01/REPORT.md) and
[warning review](endpoint_ctrl_01/warning_review.json). No candidate change or
simulation rerun was made.

| Actual diagnostic totals | Compile warnings / errors | Synthesis invocation warnings / errors |
|---|---:|---:|
| DDR adapter + generated FIFOs | **19 / 0** | **837 / 0** |
| Endpoint + controller | **22 / 0** | **908 / 0** |

Synthesis totals include PDS's prerequisite recompile. No width/truncation,
latch, missing-module or black-box diagnostics were emitted. All nine adapter
modules and all three endpoint/controller modules were analyzed and elaborated.
Every mapped cell count matches the respective structural netlist.

The adapter's actual storage mapping is **138 GTP_RAM32X2DP plus
1 GTP_RAM32X1DP**, totaling 139 distributed RAM LUTs within the 370 total.
It has no DRM36K blocks. Unused FIFO almost-full/empty and disabled water-level
logic were cleaned; **write occupancy remains used and exposed**. The adapter
also retains 18 constant-probe warnings, two unreplicated carry-fanout warnings
and ten unmet fanout warnings. The endpoint retains 20 constant-probe warnings,
the function warning, constant/dangling cleanup and one net rename. All raw
diagnostics are retained and categorized in the project reports/audits.

Actual elaborated/source-checked defaults: adapter limit **`0x10000000`
(256 MiB)**, upstream **read ID 7 bits / write ID 4 bits**, vendor address
28 bits and maximum **16 beats**; actual FIFOs are 16 words by 144/133 bits,
synchronous with no output register. Endpoint **ID_WIDTH=7**, window
**`0x40010000` + `0x1000`**, controller output banks **`0x08000000` /
`0x08200000`**, output length **1,228,800**. The ASCII Verilog-2001 wrapper
connects all 19 AXI-Lite signals directly; all other instance ports are exposed
without tie-offs, open ports, behavioral code or hierarchy forces.

Full actual before/after hashes, top signatures, parameter overrides, commands,
logs, maps and audits are retained under the new directories:

- [DDR adapter report](ddr_adapter_01/REPORT.md),
  [pinned sources](ddr_adapter_01/expected_inputs.json),
  [actual output audit](ddr_adapter_01/output_audit.json),
  [PDS mapping report](ddr_adapter_01/synthesize/fpga_v8_ddr_adapter.snr).
- [Connected endpoint/controller report](endpoint_ctrl_01/REPORT.md),
  [pinned sources](endpoint_ctrl_01/expected_inputs.json),
  [actual output audit](endpoint_ctrl_01/output_audit.json),
  [PDS mapping report](endpoint_ctrl_01/synthesize/fpga_v8_endpoint_ctrl_synth.snr).

Adapter SHA-256:
`5b84936d95c74e10bec28734172b49a175e1a17725bc73b3fade9ae089a5e2b8`.
Endpoint SHA-256:
`5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e`.
Controller SHA-256:
`fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae`.
The eight FIFO hashes match the exact compile list and prior five-suite
actual-FIFO ModelSim evidence; all source hashes remain unchanged. Wrapper
SHA-256: `d6abd0f29f1da0f732a1d6b624ae434789ba4b207c7aae43b58baf201758ab4c`.

All four invocations ran sequentially, with `Get-Process pds,pds_shell` clear
before each invocation and after each project's completion. Actual argument
arrays/timestamps are in each `run_results.json`. Final source/artifact,
history and non-overlap checks are saved in
[final verification](endpoint_ctrl_01/final_verification.json).
No GUI/shell was killed, no old project rerun, and no parent capture/host work
was touched.

The adapter has **781** virtual IO bits and endpoint/controller **740**, both
exceeding the package's 285 physical IO. The unconstrained virtual-input/output
warnings remain visible. This is compile/synthesis resource evidence only:
no DDR3 controller/PHY, PnR, bitstream, JTAG, board load, timing/Fmax or FPS
acceptance. **Common reset, certified stable RAW leases, safe disjoint physical
allocations, production endpoint decode and host integration remain required.**
Formal assumptions and verification were untouched.

## Preserved integrated cooperative core evidence

**`cooperative_core_01` compiled and synthesized successfully as
`fpga_v8_cooperative_core`. Its actual integrated mapping is 2,074 LUTs and
1,773 registers, with zero latches, DRM, and APM.** Both invocations returned
exit code 0. All six pinned ASCII RTL sources were analyzed and elaborated;
there are no missing-module, black-box, width, or latch diagnostics.

This integrated result is the current resource evidence. The earlier
2,218-LUT / 1,901-register arithmetic sum describes three separate standalone
syntheses; it is not the integrated result. Historical standalone evidence is
preserved in [REPORT_components_historical.md](REPORT_components_historical.md),
[subset_summary.json](subset_summary.json), and the unchanged project directories.

Target: **Logos2 PG2L100H -6 FBG484**, PDS 2022.2-SP6.4 build 146967.
The local clock is nominal 150 MHz and all top ports are virtual. This closes
isolated core compile/synthesis validation; it does not establish board
placement, timing, measured frequency, FPS, or board deployment acceptance.

## Actual integrated resource result

Source: [PDS integrated synthesis report](cooperative_core_01/synthesize/fpga_v8_cooperative_core.snr).
[output_audit.json](cooperative_core_01/output_audit.json) independently matches
every reported mapped cell count to the generated structural netlist;
`audit_pass` is true.

| Integrated top | LUTs | Registers | Latches | Distributed RAM | DRM | APM |
|---|---:|---:|---:|---:|---:|---:|
| `fpga_v8_cooperative_core` | **2,074** | **1,773** | **0** | **0** | **0.0** | **0.00** |

PDS reports LUT use of 2,074 / 66,600 (3.11%) and register use of
1,773 / 133,200 (1.33%). It also maps **273 GTP_MUX2LUT7** cells. These are
component synthesis counts, not total board resource acceptance.

| Historical standalone project, unchanged | LUTs | Registers | Latches / DRM / APM |
|---|---:|---:|---|
| `raw_frame_axi_03` | 764 | 874 | 0 / 0 / 0 |
| `coop_control_01` | 782 | 938 | 0 / 0 / 0 |
| `ddr_write_arbiter_01` | 672 | 89 | 0 / 0 / 0 |

The integrated top uses **144 fewer LUTs and 128 fewer registers** than the
standalone arithmetic sum. Actual integration changes the mapping through
connected ports and constants. The bridge's four 32-bit debug snapshot ports
are explicitly open in the wrapper; PDS reports their removal. Its integrated
subtree has 746 FFs versus 874 standalone FFs. No candidate RTL was edited.

| Integrated hierarchy, already included in top totals | LUTs | FFs |
|---|---:|---:|
| `bridge` | 638 | 746 |
| `bridge/output_packer` | 256 | 279 |
| `bridge/raw_pipeline` | 64 | 57 |
| `control` | 734 | 938 |
| `write_arbiter` | 699 | 89 |

Packer and letterbox rows are nested bridge subtrees; do not add them again.
The top also contains three LUTs outside the three immediate child subtrees.

| Integrated mapped cell | Actual instances |
|---|---:|
| GTP_DFF_C | 27 |
| GTP_DFF_CE | 1,655 |
| GTP_DFF_P | 1 |
| GTP_DFF_PE | 1 |
| GTP_DFF_RE | 88 |
| GTP_DFF_SE | 1 |
| GTP_LUT1 | 7 |
| GTP_LUT2 | 52 |
| GTP_LUT3 | 21 |
| GTP_LUT4 | 131 |
| GTP_LUT5 | 492 |
| GTP_LUT6 | 586 |
| GTP_LUT6CARRY | 468 |
| GTP_LUT6D | 317 |
| GTP_MUX2LUT7 | 273 |
| GTP_GRS | 1 |
| GTP_INV | 1 |
| GTP_INBUF | 1,698 |
| GTP_OUTBUF | 562 |

## Six-source integrity and complete binding

Exactly these six files were registered, using relative paths. Their actual
SHA-256 hashes matched before compile, after compile, after synthesis, and
in the final audit. All are ASCII. The wrapper hash matches the completed
five-suite ModelSim evidence in `cooperative_core/REPORT.md`, which was read
only; no simulation was rerun here.

| RTL path relative to `fpga_v8_migration` | Pinned SHA-256 |
|---|---|
| `cooperative_core/fpga_v8_cooperative_core.v` | `c94c7aa1cd97535d3bbe50239199c7595198b3f0f74aa19af26670358757064e` |
| `cooperative_control/fpga_v8_coop_control_axil.v` | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |
| `cooperative_axi/fpga_v8_raw_frame_axi.v` | `c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f` |
| `cooperative_arbiter/fpga_v8_ddr_write_arbiter.v` | `c0982b49617f416f96d3b338df822c5ce0e0701aa8425f766da85f00a8ffc969` |
| `raw_preprocess/fpga_v8_raw_letterbox.v` | `b1ffda1799c350973444ff3bbd6cea2288c6155426397ca8ee62c1cca7d5d1ad` |
| `raw_preprocess/fpga_v8_rgb888_pack128.v` | `20b691d328b6dc43feb42b6352b169156002a3931a43d003f871fff2289613af` |

PDS selected `fpga_v8_cooperative_core` as the sole uninstantiated root and
successfully elaborated all six module definitions. The source binding audit
found no missing, duplicate, or unknown named port bindings in any of the
five instances:

| Owner / instance | Bound module | Named bindings |
|---|---|---:|
| core / `control` | `fpga_v8_coop_control_axil` | 52 |
| core / `bridge` | `fpga_v8_raw_frame_axi` | 54 |
| core / `write_arbiter` | `fpga_v8_ddr_write_arbiter` | 48 |
| bridge / `raw_pipeline` | `fpga_v8_raw_letterbox` | 16 |
| bridge / `output_packer` | `fpga_v8_rgb888_pack128` | 11 |

The four intentional open bridge outputs are `active_src_addr`,
`active_dst_addr`, `active_frame_id`, and `completed_frame_id`. No other
named port is open. The top has **111 port declarations** comprising
**2,260 scalar IO bits**. The full top parameter and port signature, parameter
overrides, and binding names are saved in
[source_signature_before.json](cooperative_core_01/source_signature_before.json)
and the final `output_audit.json`.

## Actual default parameters

The audit parsed these values from PDS's elaboration log and matched them
to the pinned manifest:

| Parameter / interface | Actual value |
|---|---|
| WIDTH / HEIGHT / OUT_HEIGHT / TOP_ROWS | 640 / 480 / 640 / 80 |
| FILL_VALUE | 114 |
| OUTPUT_BANK0_ADDR / OUTPUT_BANK1_ADDR | `0x08000000` / `0x08200000` |
| DDR_ADDRESS_LIMIT | `0x10000000` (exclusive physical bound) |
| AXI_ID | 1, declared as four bits |
| Derived OUTPUT_LENGTH, passed to controller | **1,228,800** = `3 * 640 * 640` |
| Bridge fixed ID_WIDTH | **4** |
| Arbiter fixed MASTER_COUNT / ID_WIDTH | **7 / 4** |
| Arbiter fixed ADDR_WIDTH / DATA_WIDTH / OWNER_WIDTH | 32 / 128 / 3 |
| Controller bank count | 2, fixed implementation |
| Controller DEVICE_ID / VERSION | `0x434f4f50` / `0x00010000` |

`OUTPUT_LENGTH` is a wrapper localparam with expression
`32'd3 * WIDTH * OUT_HEIGHT`, not an independently overridden parameter.
PDS confirms the derived value in `fpga_v8_cooperative_core/control`.
Six camera writers occupy slots m0-m5; the bridge occupies m6.

## All compiler diagnostics retained

Standalone compile: **49 warnings, 0 errors**. Synthesis invocation,
including PDS's prerequisite recompile: **2,372 warnings, 0 errors**.
Both stderr logs are empty. Every warning/error line and its original log
line number is saved in
[diagnostics_extracted.txt](cooperative_core_01/diagnostics_extracted.txt).

| Actual warning category | Compile log | Synthesis invocation log |
|---|---:|---:|
| License expires in 29 days | 1 | 1 |
| `Loop was found during constant probe` | 48 | 48 |
| Constant register removed | 0 | 12 |
| `Public-4008`: dangling instance cleaned | 0 | 49 |
| Max fanout constraint not honored, `gtp_inv` net `N113` | 0 | 2 |
| 2,260 IO exceed 285 physical package IO | 0 | 1 |
| `Timing-4087`: unconstrained output bit | 0 | 562 |
| `Timing-4086`: unconstrained input bit | 0 | 1,697 |

The 49 dangling entries include the four intentionally open bridge debug
vectors, the unused letterbox done signal, eight low read/write address
bits, four duplicated RGB expansion bits, 30 controller destination-address
bits, and the low bit of each AXI-Lite response. The 12 constant removals
cover controller `cmd_dst_addr` bit 0, both response bit 0 signals, eight
bridge address bits, and packer `byte_count[4]`.

The 48 constant-probe warnings lack source locations and remain unresolved
compiler diagnostics; the two fanout warnings are also retained. Neither
successful synthesis nor the prior ModelSim PASS is presented as proof that
these warnings can be ignored. RTL was left unchanged.

There are no emitted width/truncation/extension, latch, missing-module, or
black-box diagnostics. The resource report explicitly confirms zero latches,
and all six module definitions were both analyzed and elaborated.

## Scope and external integration requirements

The local FDC creates only a **nominal 150 MHz** clock on `core_clk` and
marks every port `PAP_IS_VIRTUAL_IO=TRUE`. The netlist audit confirms this
attribute on all 2,260 IO buffer instances. The excessive pin-count and
unconstrained IO warnings remain visible. This internal-interface top is not
a whole-board placeable design. No Fmax, timing closure, or FPS acceptance
is claimed from synthesis.

The core still requires a **common reset** across outstanding AXI, interconnect,
and lease participants, and a **certified stable RAW source lease** retained
until the source-release handshake. The simulation's leased-source model does
not prove live camera RAW stability. Default output addresses are parameters,
not proof that their physical storage is allocated, reserved, and disjoint
from all live buffers. Source ownership, safe allocation, host CLAIM/copy/ACK,
production endpoint/DDR wiring, and reset/CDC integration remain external work.
Formal assumptions and verification were not changed or run here.

Only compile and synthesis were run. No production project/constraint/IP write,
candidate RTL edit, device mapping, PnR, post-route timing, power run, bitstream,
JTAG, board operation, or simulation occurred. No forbidden-stage directory
or bitstream file was found. All task files and generated project data stayed
under `component_synthesis`.

## Actual commands and preserved history

[run_results.json](cooperative_core_01/run_results.json) records absolute
command argument arrays, working directory, timestamps, exit codes, source
integrity, and database checks. The actual executable was
`C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`. Each invocation used
`-project <component_synthesis>/cooperative_core_01/project.pds`,
`-work_dir <component_synthesis>/cooperative_core_01`, and the stage below.

| Requested stage | Start / finish, 2026-10-05 +08:00 | Exit |
|---|---|---:|
| `-run compile` | 07:53:23 / 07:53:27 | 0 |
| `-run synthesize` | 07:53:29 / 07:53:45 | 0 |

PDS reports 13 seconds for the synthesis stage and 425 MB peak memory.
Its prerequisite recompile is retained in the synthesis invocation log.
Compile and synthesize ran sequentially, with `Get-Process pds,pds_shell`
clear before each invocation. Saved initial, stage, final, and post-audit
process checks contain empty process lists. No GUI or other shell was killed
or modified.

The before/after audit compared **171 files** across `raw_frame_axi_02`,
`raw_frame_axi_03`, `coop_control_01`, and `ddr_write_arbiter_01`; every
path, size, and SHA-256 hash remained unchanged. The snapshot is
`cooperative_core_01/historical_projects_before.json`, with the final result
in `output_audit.json`. No prior output was erased, reused, or regenerated.
