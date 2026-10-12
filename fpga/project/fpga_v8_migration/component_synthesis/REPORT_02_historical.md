# RAW frame AXI isolated PDS synthesis report

The three-source `fpga_v8_raw_frame_axi` component compiled and synthesized
successfully using PDS 2022.2-SP6.4 (build 146967). Both invocations returned
exit code 0, and the expected compile and synthesis databases, structural
netlist, and resource report exist in `raw_frame_axi_02`.

Target: Logos2 **PG2L100H -6 FBG484**. Default parameters were elaborated:
WIDTH=640, HEIGHT=480, OUT_HEIGHT=640, TOP_ROWS=80, FILL_VALUE=114,
ID_WIDTH=4, AXI_ID=1. PDS selected `fpga_v8_raw_frame_axi` as the sole
uninstantiated root; the compile log confirms the top and parameter values.

## Actual resource results

Source: [PDS synthesis report](raw_frame_axi_02/synthesize/fpga_v8_raw_frame_axi.snr).
Counts were independently matched against the generated structural netlist by
[the output audit](raw_frame_axi_02/output_audit.json); `audit_pass` is true.

| Resource | Actual synthesis count |
|---|---:|
| LUTs | 764 / 66,600 (1.15%) |
| Registers | 874 / 133,200 (0.66%) |
| Latches | 0 |
| Distributed RAM LUTs | 0 |
| DRM36K/FIFO | 0.0 / 155 |
| APM | 0.00 / 240 |
| Internal interface port bits | 658 |

The hierarchy report assigns 304 LUTs / 279 FFs to `output_packer` and
79 LUTs / 57 FFs to `raw_pipeline`. These are subtrees already included in
the component totals above.

| Mapped cell type | Actual instances |
|---|---:|
| GTP_DFF_C | 12 |
| GTP_DFF_CE | 861 |
| GTP_DFF_PE | 1 |
| GTP_LUT1 | 1 |
| GTP_LUT2 | 24 |
| GTP_LUT3 | 121 |
| GTP_LUT4 | 115 |
| GTP_LUT5 | 59 |
| GTP_LUT6 | 139 |
| GTP_LUT6CARRY | 218 |
| GTP_LUT6D | 87 |
| GTP_GRS | 1 |
| GTP_INV | 1 |
| GTP_INBUF | 245 |
| GTP_OUTBUF | 413 |

## Compiler warnings and errors

The standalone compile log contains **15 warnings, 0 errors**. The synthesis
invocation log contains **692 warnings, 0 errors**; PDS automatically reran
compile as its prerequisite, so its 14 constant-probe warnings appear again.
Both stderr files are empty. All emitted `W:` / `E:` lines and their original
line numbers are saved in [diagnostics_extracted.txt](raw_frame_axi_02/diagnostics_extracted.txt).

| Warning category | Standalone compile | Synthesis invocation including prerequisite compile |
|---|---:|---:|
| License expires in 29 days | 1 | 1 |
| `Loop was found during constant probe` | 14 | 14 |
| `Public-4008`: dangling instance cleaned | 0 | 5 |
| Constant register removed | 0 | 9 |
| Max fanout constraint could not be honored | 0 | 2 |
| Net renamed to avoid name conflict | 0 | 3 |
| 658 IO exceed 285 physical package IO | 0 | 1 |
| `Timing-4087`: unconstrained output bit | 0 | 413 |
| `Timing-4086`: unconstrained input bit | 0 | 244 |

The two fanout warnings name the `gtp_inv` driven net `N113`. The five
dangling instances are `raw_pipeline/done` and `raw_pipeline/m_data[22]`,
`[23]`, `[6]`, `[7]`. Constant removals cover the four low bits of each
read/write address register and `output_packer/byte_count[4]`.

There are **no emitted latch or width/truncation/extension diagnostics**.
The synthesis resource report explicitly records zero inferred latches.
The constant-probe loop messages do not identify a source location; this
report retains them as unresolved compiler diagnostics. Candidate RTL was
not edited to silence warnings.

## Clock, virtual IO, and scope limits

The local `component.fdc` creates only the nominal 150 MHz component clock
(6.666667 ns) and applies `PAP_IS_VIRTUAL_IO=TRUE` to every port. PDS confirms
658 matched port objects, and the generated netlist contains **658 IO buffer
instances with the virtual IO attribute**. PDS still reports the physical
package IO count warning. This wide internal AXI interface is therefore
**not a whole-board placeable top**.

The raw synthesis report embeds timing estimates and an `All Constraints
Met` summary. Those are synthesis-only estimates with unconstrained IO;
they are **not routed timing, measured frequency, or full-board acceptance**.
The nominal clock is a component synthesis target only.

No device mapping, PnR, post-route timing, power run, bitstream generation,
JTAG, board operation, or simulation was run. The audit found no forbidden
stage directories or bitstream files. All generated project data stayed
under `component_synthesis`. No production PDS, production constraints,
vendor IP, or board files were written. Optional finish/activation synthesis
was not needed for this bridge result.

## Source integrity

Exactly three RTL inputs were registered. SHA-256 hashes below match the
pre-run, post-compile, post-synthesis, final, and output-audit readings.

| Input relative to `fpga_v8_migration` | SHA-256 |
|---|---|
| `raw_preprocess/fpga_v8_raw_letterbox.v` | `b1ffda1799c350973444ff3bbd6cea2288c6155426397ca8ee62c1cca7d5d1ad` |
| `raw_preprocess/fpga_v8_rgb888_pack128.v` | `20b691d328b6dc43feb42b6352b169156002a3931a43d003f871fff2289613af` |
| `cooperative_axi/fpga_v8_raw_frame_axi.v` | `235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40` |

The compile `.cmr` lists only these three inputs. Source manifests and
registration checks are saved in `raw_frame_axi_02/expected_inputs.json`,
`source_inputs_before.json`, `source_inputs_after_compile.json`,
`source_inputs_after_synthesize.json`, `source_inputs_final.json`, and
`registration_check.json`.

## Commands and process isolation

[run_results.json](raw_frame_axi_02/run_results.json) records the actual
argument arrays, working directory, timestamps, exit codes, and database
checks. The working directory was
`C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/component_synthesis/raw_frame_axi_02`.

```powershell
& 'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe' -project './project.pds' -run compile -work_dir '.'
& 'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe' -project './project.pds' -run synthesize -work_dir '.'
```

Actual calls used the absolute project and work-directory paths shown in
`run_results.json`; all PDS source registrations use safe relative paths.
The standalone compile ran 2026-10-05 04:49:06-04:49:09 +08:00. The synthesis
invocation, including prerequisite compile, ran 04:49:10-04:49:22 +08:00.
PDS reports 3 seconds / 140 MB peak for compile and 9 seconds / 363 MB peak
for the synthesis stage.

`Get-Process pds,pds_shell` was checked before preparation and before each
invocation. `process_check_initial.json`, `process_check_compile.json`,
`process_check_synthesize.json`, and `process_check_final.json` record empty
process lists. Final check time was 04:49:24 +08:00. No other process was
killed or modified.

The initial `raw_frame_axi_01` attempt is retained with its logs. It failed
project parsing before RTL compilation: `Flow-0131` (custom flow identifier),
`Flow-0130` (missing file `_timespec` metadata), and `Flow-0121` (project
analysis failed), exit code 1. A new clean `raw_frame_axi_02` project used
the required `fab_demo` identifier and metadata. No old database outputs
were copied or erased. The production PDS file and installed tool manuals
were used only as read-only syntax references.

The completed bridge synthesis has no remaining tool blocker. Its warnings
and integration/timing limitations above remain visible for the main agent.
