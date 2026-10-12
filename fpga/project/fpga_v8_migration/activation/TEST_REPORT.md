# Isolated activation verification report

Result: PASS. Run started at `2026-10-04T17:01:48.124569+00:00` (UTC),
using Python 3.12.4, NumPy 1.26.4, and ModelSim SE-64 10.6e.
ModelSim's local log date is October 5, 2026. This verifies an isolated
component, not a calibrated model or integrated FPGA inference path.

## Files added

- `fpga_v8_activation_lut.v`: unique synthesizable Verilog-2001 module,
  LANES=16 default, replicated runtime-programmable 256x8 memories,
  synchronous one-cycle lookup, one-slot elastic output, last and identity
  bypass, and idle-only configuration with input arbitration.
- `generate_silu_lut.py`: NumPy affine u8 SiLU CLI, hex table and manifest
  with hashes, explicit uncalibrated status, clipping and reconstruction errors.
- `test_generate_silu_lut.py`: independent scalar reference for all codes,
  error metric checks, negative-value encoding, rounding, invalid parameters,
  CLI files and CLI error exit.
- `tb_fpga_v8_activation_lut.v`: public-interface transaction scoreboard,
  exhaustive code/lane coverage and directed/random streaming tests.
- `run_tests.py`: Python regression runner for the requested ModelSim binaries,
  explicit scoreboard PASS validation and machine-readable evidence.
- `README.md` and `TEST_REPORT.md`: interface, usage, validation and remaining
  integration work.
- `artifacts/`: two generated tables/manifests, command logs, ModelSim work
  library/transcript and `test_results.json`.

All component files and test artifacts are under
`C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/activation`.
Workspace and project AGENTS guidance was read. Before adding RTL, a
byte-level project-wide Verilog module-name scan found no existing
`fpga_v8_activation_lut` or `tb_fpga_v8_activation_lut` declarations.
No production RTL, PDS project, IP, bitstream or board changes were made.
No torch installation was performed.

The final read-only audit confirmed that all seven source/documentation files
are ASCII, the five tested Verilog/Python files match their recorded SHA-256
values, and each new module has exactly one declaration across the project.
Audit output: `AUDIT_PASS tested source hashes match; all 7 source/documentation files ASCII`.

## Commands and output

Invoked from `activation`:

```text
C:/Users/NineSun/anaconda3/python.exe run_tests.py
```

The runner invoked `vlib.exe`, `vlog.exe` and `vsim.exe` from
`C:/modeltech64_10.6e/win64`. Exact argv arrays, working directories,
return codes, source SHA-256 values, generator manifests and simulation
counters are recorded in `artifacts/test_results.json`. All command return
codes were zero. The plain Verilog compile reported `Errors: 0, Warnings: 0`.
Each simulation reported `Errors: 0, Warnings: 1`; the sole warning was
`vsim-8891`, optimization disabled by the environment's `-novopt` setting.

Python test output:

```text
test_all_codes_against_independent_scalar_reference ... ok
test_cli_files_and_error_exit ... ok
test_invalid_parameters ... ok
test_ties_to_even_and_stable_large_negative_domain ... ok
Ran 4 tests in 0.442s
OK
```

Exact final simulation and runner markers:

```text
PASS fpga_v8_activation_lut LANES=1 seed=20260929
PASS fpga_v8_activation_lut LANES=3 seed=17320508
PASS fpga_v8_activation_lut LANES=16 seed=31415926
PASS fpga_v8_activation_lut LANES=16 seed=27182818
PASS isolated regression: 4 generator tests, 4 ModelSim simulations
```

Each simulation reported exactly:

```text
COUNTERS accepted=2056 received=2054 reset_discarded=2 writes=512 rejected=18 priority_checks=512
```

| LANES | Seed | Stalled cycles | Simultaneous input/output | One-cycle checks | Last received | Reset cycles | Total cycles |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 20260929 | 842 | 1924 | 2056 | 112 | 6 | 3550 |
| 3 | 17320508 | 851 | 1938 | 2056 | 112 | 6 | 3545 |
| 16 | 31415926 | 817 | 1912 | 2056 | 112 | 6 | 3537 |
| 16 | 27182818 | 820 | 1921 | 2056 | 112 | 6 | 3531 |

All 256 codes were checked on every lane for both tables and bypass.
Per-lane minimum visits were 2 for table A, 3 for table B and 2 for bypass.
The two reset-discarded outputs are deliberate, accounted-for transactions.
Every other accepted input produced exactly one consumed output.

Full output is retained in `artifacts/generator_tests.log`,
`artifacts/vlog.log`, and the four `artifacts/vsim_lanes_*_seed_*.log` files.

## Test tables and affine error

The two test tables differ at 248 of 256 addresses. They were programmed
through 512 configuration handshakes, rather than a DUT initialization block.
These are deliberately different test domains, not calibrated model scales.
Both domains include negative preactivations; scalar tests also confirm that
negative activation values can encode below a nonzero output zero point.

| Table | Input scale | Input zp | Output scale | Output zp | Low clipped | High clipped | All-code max abs error | Unclipped max abs error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.0625 | 128 | 0.03125 | 16 | 0 | 8 | 0.46591654558438833 | 0.015624435774123313 |
| B | 0.125 | 80 | 0.05 | 120 | 0 | 121 | 15.124999993085574 | 0.02477645046413637 |

Table A all-code mean absolute error is `0.015252055109151489` and RMS
error is `0.05120335723801144`. Table B all-code mean absolute error is
`3.6094880913781195` and RMS error is `6.040694814285175`. Table B deliberately
has substantial positive saturation, which the manifest reports. Unclipped
maximum error stays below half an output quantization step for both tables.
Metrics are output float units at the input code grid, excluding errors from
input quantization, upstream convolution, and model accuracy.

SHA-256 over table bytes (not hex text):

```text
A 59dc66023a7894fa46e776b9913603eb6ba7baa5f5b8b245a0da4ea46a3d4a9f
B 797fe1fc4b9e9f0cef2337e73b0c336251cc3beaac36d459d70b2d129d4251f4
```

## Behavior verified and limits

The scoreboard checks before and after each edge, enforcing synchronous
latency, occupancy and exact output values/last for every accepted input.
It checks random stalls and source gaps, simultaneous consumption/replacement,
identity before programming, identity on all codes, sampled per-beat bypass,
reset with an outstanding output, and table retention through reset.

Configuration is offered concurrently with input during all 512 writes;
input must not be accepted. For each table, eight attempted writes while an
output stalls and one attempted write on its consumption edge must be rejected.
Re-reading the attempted address verifies that rejected writes did not alter
any lane's table. Configuration and input are suppressed during reset.

The primitive prevents table writes with an in-flight result. A complete
table update is a sequence of writes; the controller must keep input stopped
across that entire sequence. There is no double-buffering, atomic table swap,
table-complete flag, calibration database or NPU connection.

Integration is still needed for the audited model's 49 Conv+SiLU boundaries:
calibrated affine domains, convolution requantization, layer table loading,
stream/lane/last adaptation, control and clock/reset wiring, RAM/resource/timing
validation, and model-level and board verification. The current production
NPU's activation support must be checked and extended at integration time.
This report makes no synthesis or FPGA inference claim.
