# Isolated programmable u8 activation LUT

`fpga_v8_activation_lut` is a standalone Verilog-2001 primitive for the V8
migration. The audited model has 49 Conv+SiLU pairs; a ReLU-only activation
path cannot implement those pairs. This component maps an unsigned input code
to an unsigned output code using a programmable 256-entry table. Nonzero
affine zero points represent negative floats in unsigned codes.

This directory is isolated from the production RTL and PDS project. The
primitive is not connected to the NPU. No synthesis, placement, timing,
bitstream, board, or end-to-end model validation is claimed.

## Hardware contract

- `LANES` is a positive integer, default 16. Lane `i` occupies bits
  `[8*i +: 8]` of both stream buses.
- `rst` is synchronous, active high. It clears output data, valid, and last,
  discards a pending result, and suppresses input/configuration handshakes.
  It preserves table contents. Hardware tables have no built-in initialization.
- A source transfers only when `s_valid && s_ready` at a rising edge. Data,
  last, and bypass must remain stable until that transfer.
- Each lane performs a synchronous table read into its output register at
  that edge. The registered result becomes valid after the edge and can be
  consumed at the next rising edge. There is one elastic output slot; capacity
  is one beat, latency is one cycle, and maximum throughput is one beat/cycle.
- If `m_valid && !m_ready`, output data, valid, and last stay stable. A full
  slot can consume its old beat and accept its replacement at the same edge.
- `bypass=1` samples an identity map with the same latency and handshake.
  It copies the u8 code, with no affine rescaling. Changing bypass afterward
  cannot alter a pending output. Identity between different affine domains
  requires matching their scales and zero points at integration time.
- `cfg_valid && cfg_ready` writes `cfg_data` at `cfg_addr` in every lane's
  private 256x8 memory. `cfg_ready = !rst && !m_valid`. A pending output
  blocks writes even at its consumption edge; readiness returns when empty.
- Configuration has priority: `cfg_valid=1` blocks all new source transfers,
  so pending output can drain. A configuration request held until ready is
  accepted when idle. A pulse while not ready is ignored. This interface has
  no write queue and no table readback.
- Program all 256 entries before LUT use. Keep the source quiescent across a
  full table update, including gaps between configuration writes. Individual
  writes are safe while idle; there is no atomic bank swap or table-complete
  flag. The controller must keep traffic stopped until the desired table is
  complete. No in-flight beat can see a table mutation.

The implementation allocates one 256x8 memory per lane (32768 table bits,
4096 bytes at 16 lanes), broadcasts writes, and uses independent synchronous
read addresses. RAM mapping, output reset/enable inference, bypass mux timing,
and actual PG2L100H resources require subsequent synthesis verification.

## Generate an affine SiLU table

The generator uses NumPy, without torch. Supply parameters for the actual
preactivation and activation-output domains:

```powershell
C:/Users/NineSun/anaconda3/python.exe generate_silu_lut.py `
  --input-scale 0.0625 --input-zero-point 128 `
  --output-scale 0.03125 --output-zero-point 16 `
  --hex artifacts/example.hex --manifest artifacts/example.json
```

For input code `q`, it computes `x = (q - input_zero_point) * input_scale`,
`y = x / (1 + exp(-x))`, and
`q_out = clip(rint(y / output_scale + output_zero_point), 0, 255)`.
Rounding is nearest with ties to even. The hex file contains 256 two-digit
bytes in address order, one per line, suitable for simulation `$readmemh`.
Hardware receives the table through configuration writes.

The JSON manifest includes supplied parameters, rounding, input/output float
ranges, negative-value counts, clipping counts, a SHA-256 over the 256 table
bytes, and maximum/mean absolute and RMS reconstruction error. Error is in
output float units against float64 SiLU evaluated on the 256 input grid
points. Separate unclipped metrics distinguish rounding error from saturation.
These metrics exclude input quantization, convolution accumulation/requantization
error, model distributions, and task accuracy. Generated tables and the example
parameters are explicitly uncalibrated.

## Run the isolated regression

```powershell
C:/Users/NineSun/anaconda3/python.exe run_tests.py
```

The runner defaults to `C:/modeltech64_10.6e/win64`; use `--modelsim-bin` to
override it. It runs independent scalar generator checks, creates two affine
SiLU tables, compiles plain Verilog without SystemVerilog mode, and simulates
LANES=1, 3, and 16, with a second independent random seed at 16 lanes.

The scoreboard models accepted public transactions and configuration writes.
It verifies every code on every lane for both tables and identity bypass,
one-cycle registered lookup, full-rate replacement, random source gaps and
sink stalls, output stability, last propagation, per-beat bypass selection,
bypass before programming, reset while pending, table retention through reset,
configuration priority over input, and rejected writes while a result is
pending or consuming. A watchdog and explicit final coverage/conservation
checks prevent an incomplete run from reporting success.

Artifacts stay under `activation/artifacts`: generated tables/manifests,
ModelSim work library/transcript/logs, and `test_results.json` with exact
commands, source hashes, versions, seeds, counters, and pass/fail status.
See `TEST_REPORT.md` for the recorded verification evidence.

## Integration still required

Each relevant Conv+SiLU boundary needs a confirmed affine preactivation domain
and output domain, calibrated scales/zero points, and matching convolution
requantization. A layer controller must drain the primitive, program or select
the correct table, and hold traffic until programming is complete. Layer,
packing, tail-lane masks, and frame/layer `last` semantics need an agreed NPU
contract. This module always transforms all lanes and only propagates `last`.
The production preprocessor's single-pulse valid convention requires an
adapter if reused; this isolated component uses ordinary held-valid ready/valid.

NPU wiring/instruction changes, reset and clock-domain control, implementation
resource/timing verification, calibrated model accuracy checks, and eventual
board validation remain separate migration work.
