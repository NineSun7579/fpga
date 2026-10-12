# Connected AXI128 endpoint and two-bank controller

Compile and synthesis returned **0** for `fpga_v8_endpoint_ctrl_synth` on
**PG2L100H -6 FBG484**, PDS 2022.2-SP6.4 build 146967. Actual connected
mapping: **1,008 LUTs, 1,127 registers, zero latches, distributed RAM, DRM and
APM**. All 740 scalar IO buffers are virtual, with a nominal 150 MHz `clk`.

**PDS emits an unresolved `Verilog-2021` undriven-function-net warning.**
Successful compilation and mapped-resource audits do not prove synthesized
address-rejection behavior. See the exact diagnostic and source review below.

| Actual hierarchy, included in total | LUTs | Registers |
|---|---:|---:|
| Connected top | **1,008** | **1,127** |
| `control` | 821 | 936 |
| `endpoint` | 187 | 191 |

These are actual hierarchy rows from one connected synthesis, not an
arithmetic sum of standalone runs. The endpoint subtree is not a standalone
endpoint resource result; PDS optimized across the AXI-Lite connection.
The old controller standalone remains 782 LUTs / 938 registers, unchanged.
This new top includes another instance of that controller and is not connected
to the cooperative core or DDR adapter, so no combined-system total is claimed.

## Wiring and source integrity

The unique ASCII Verilog-2001 wrapper is wiring only: no `always`, `initial`,
`assign`, `force`, constants on instance ports, simulation gates or behavioral
replacement. It directly connects all 19 AXI-Lite signals and uses one shared
clock/reset. Every other controller port and the entire upstream endpoint
AXI interface is exposed, including descriptor, producer, completion/error,
command-readiness and source-release-readiness inputs. All 60 endpoint and
52 controller named ports are connected with no open, missing, duplicate or
unknown binding. The top has 72 declarations / 740 scalar IO bits.

The port mapping follows the actual endpoint/controller testbench with its
simulation backpressure gates and tie-offs removed. A byte-level scan found
exactly one wrapper definition across 9,691 RTL files; evidence is in
`wrapper_module_scan.json`. PDS analyzed and elaborated all three source
modules and selected only the wrapper as top.

| Source relative to project | SHA-256 |
|---|---|
| `fpga_v8_migration/component_synthesis/endpoint_ctrl_01/fpga_v8_endpoint_ctrl_synth.v` | `d6abd0f29f1da0f732a1d6b624ae434789ba4b207c7aae43b58baf201758ab4c` |
| `fpga_v8_migration/cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v` | `5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e` |
| `fpga_v8_migration/cooperative_control/fpga_v8_coop_control_axil.v` | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |

All actual hashes and byte lengths matched before compilation, after both
stages and in the final audit. Both candidate files and the existing
controller were read-only. The endpoint/controller hashes match the prior
419-operation / 3,803-event ModelSim report; that regression was not rerun.
Full signatures, bindings and direct-link checks are saved in
`source_signature_before.json` and `output_audit.json`.

| Actual PDS-elaborated default | Value |
|---|---|
| Endpoint and wrapper ID_WIDTH | **7** |
| BASE_ADDR / WINDOW_BYTES | **`0x40010000` / `0x00001000`** |
| Controller output banks | **`0x08000000` / `0x08200000`** |
| OUTPUT_LENGTH | **1,228,800** bytes |
| Controller DEVICE_ID / VERSION | `0x434f4f50` / `0x00010000` |
| Upstream AXI / local AXI-Lite data widths | **128 / 32 bits** |

All wrapper and child parameter values are independently matched against
`expected_inputs.json`. Controller bank/address constants may be optimized;
the wrapper exposes dynamic producer/status ports so live controller behavior
is retained. The adapter's 16-beat limit is a separate contract; the endpoint
accepts singleton register accesses and drains invalid promised bursts.

## Actual diagnostics, including the undriven net

| Warning category | Compile | Synthesis invocation |
|---|---:|---:|
| License expires in 29 days | 1 | 1 |
| Undriven `eligible.addr_end_1`, tied zero | 1 | 1 |
| Constant-probe loop | 20 | 20 |
| Constant register removed | 0 | 8 |
| Dangling instance cleaned | 0 | 137 |
| Net renamed to avoid conflict | 0 | 1 |
| IO count exceeds package | 0 | 1 |
| Unconstrained output bits | 0 | 422 |
| Unconstrained input bits | 0 | 317 |
| **Total warnings / errors** | **22 / 0** | **908 / 0** |

Every warning and log line number is retained in `diagnostics_extracted.txt`.
Both stderr files are empty. There are no width/truncation, latch, missing
module or black-box diagnostics. All cell counts match the mapped netlist.

Exact relevant PDS message, once in each invocation:

```text
Verilog-2021: fpga_v8_coop_axi128_endpoint.v(line number: 81)
Net eligible.addr_end_1 in fpga_v8_coop_axi128_endpoint
does not have a driver, tie it to 0
```

Source line 81 declares the function-local `reg [32:0] addr_end`. Line 83
unconditionally assigns `{1'b0, addr} + 33'd16`; line 87 uses it for the
upper-window eligibility check. The function is called for write validation
at line 143 and read validation at line 175. Thus the source does contain an
assignment, while PDS reports an undriven generated name. Neither `eligible`
nor `addr_end` survives by name in the mapped netlist, so this review cannot
identify the affected generated bit or establish that the tie-off is harmless.
It remains an **unresolved elaboration warning in address-validation logic**.
No source fix or additional tool run was performed; RTL ModelSim PASS is not
proof of mapped-netlist equivalence.

The 137 dangling entries group as 96 zero-extended R-data bits, 30 constant
destination bits, two ignored PROT vectors, two controller response low bits,
two endpoint response low bits, two controller AW-address high bits, two
endpoint AR-address high bits, and one endpoint AW-burst low bit. Eight
constant-removal entries are retained separately. Known causes include the
32-bit local register data, fixed bank addresses, OKAY/SLVERR responses,
shifted local addresses, ignored PROT and BURST 0/1 singleton eligibility.
These groups do not resolve the separate function warning. One mapped net
`control/active_bank` was renamed `control/active_bank_rnmt`.

The 20 constant-probe warnings lack source locations and remain visible.
The 740 virtual IO exceed 285 package pins; 422 output and 317 non-clock input
bits are unconstrained. Nominal 150 MHz does not establish board placement,
timing closure, Fmax or FPS acceptance.

## Invocation and retained evidence

Full absolute argument arrays, timestamps and source checks are in
`run_results.json`. Executable:
`C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`, using
`-project <this>/project.pds -run compile|synthesize -work_dir <this>`.

| Stage, 2026-10-05 +08:00 | Start | Finish | Exit |
|---|---|---|---:|
| Compile | 10:29:53 | 10:29:57 | 0 |
| Synthesis | 10:29:58 | 10:30:11 | 0 |

PDS reports ten synthesis seconds and 389 MB peak memory. Synthesis stdout
includes its prerequisite recompile. Both stages followed the completed DDR
adapter stages. Every saved pre-stage and post-stage PDS process check is
clear; no GUI/shell was killed. All 244 existing component-evidence files
remain unchanged; final cross-project evidence is in `final_verification.json`.

Only the two new directories and root `REPORT.md` were mutated. No production
project, constraints, IP, host or capture-agent work was touched. No simulation
rerun, formal change, PnR, bitstream, JTAG or board operation occurred.
Common reset, stable certified RAW leases, safe and disjoint physical buffer
allocation, production endpoint decode reservation and host CLAIM/copy/ACK
remain external integration requirements.
