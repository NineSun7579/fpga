# Isolated PDS component synthesis

Current integrated result: [REPORT.md](REPORT.md),
[integrated output audit](cooperative_core_01/output_audit.json).

| Integrated top | Actual LUTs | Actual registers | Latches / DRM / APM |
|---|---:|---:|---|
| `fpga_v8_cooperative_core` | **2,074** | **1,773** | 0 / 0 / 0 |

The full six-source top compiled and synthesized with both exits zero,
unchanged source hashes, complete dependency bindings, and virtual IO.
This replaces the standalone arithmetic sum as current integrated resource
evidence. Nominal clock: 150 MHz; no board timing/Fmax/FPS acceptance.

Historical standalone evidence: [REPORT_components_historical.md](REPORT_components_historical.md),
[subset_summary.json](subset_summary.json).

| Completed isolated project | LUTs | Registers | Latches / DRM / APM |
|---|---:|---:|---|
| `raw_frame_axi_03`, promoted address-fixed bridge | 764 | 874 | 0 / 0 / 0 |
| `coop_control_01`, two-bank controller | 782 | 938 | 0 / 0 / 0 |
| `ddr_write_arbiter_01`, seven masters | 672 | 89 | 0 / 0 / 0 |

All invocations returned zero. All five source hashes stayed unchanged.
`raw_frame_axi_03` uses DDR_ADDRESS_LIMIT=0x10000000 and exactly the
three pinned letterbox, packer, and bridge RTL inputs. Controller and arbiter
each use a separate one-source project. These prior project directories were
not changed by the integrated core run.

Target: Logos2 PG2L100H, speed -6, package FBG484; nominal clock 150 MHz.
The local FDC marks all ports virtual. This internal AXI component is not a
whole-board pin or timing design. Resource results do not imply board acceptance.

Only `compile` and `synthesize` are authorized. No production project,
production constraint, vendor IP, device mapping, PnR, bitstream, JTAG, board
operation, or RTL edits are part of this flow. The production PDS file was read
only as a syntax template; stale database/output registrations were not copied.

Current run commands, issued sequentially from this directory:

```powershell
& 'C:/Users/NineSun/anaconda3/python.exe' ./run_isolated.py ./raw_frame_axi_03
& 'C:/Users/NineSun/anaconda3/python.exe' ./run_isolated.py ./coop_control_01
& 'C:/Users/NineSun/anaconda3/python.exe' ./run_isolated.py ./ddr_write_arbiter_01
& 'C:/Users/NineSun/anaconda3/python.exe' ./run_isolated.py ./cooperative_core_01
```

The runner verifies exact source hashes, manifest source registration, the sole
uninstantiated root, and the absence of `pds` / `pds_shell` processes before
each invocation. It saves actual commands, timestamps, exit codes, stdout,
stderr, and source hashes before and after each invocation. Existing output
directories cause a stop; it does not delete any output or kill any process.

PDS documentation consulted read-only: ADS Synthesis User Guide pp. 17,
49-51 (top autodetection and shell flow), and User Constraint Editor User
Guide p. 100 (`PAP_IS_VIRTUAL_IO` for early component resource evaluation).

`raw_frame_axi_01` retains the initial project-parser failure: custom flow
identifier and missing `_timespec` file metadata. No RTL compile occurred there.
`raw_frame_axi_02` is immutable historical evidence for the previous bridge;
it is stale for the promoted address fix. Its 48 files remain unchanged, and
the previous report is preserved as [REPORT_02_historical.md](REPORT_02_historical.md).

`audit_outputs.py` audits only current 03/controller/arbiter evidence, compares
reported cell counts with generated netlists and default parameter values with
PDS elaboration logs, checks virtual IO, and verifies all sources and historical
02 hashes. It does not invoke PDS. Detailed compiler warnings are retained.

The integrated `cooperative_core_01/audit_core.py` captures all six source
hashes and the top signature, verifies all five dependency bindings, matches
actual elaborated defaults and mapped cell counts, checks all 2,260 virtual
ports, and confirms 171 prior project files remain unchanged. Its before/after
evidence is confined to the new core directory. Common reset, stable certified
RAW leasing, and safe physical buffer allocation remain integration requirements.
