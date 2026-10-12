# Isolated uint8 affine arithmetic

`fpga_v8_affine_add.v` implements unsigned-byte affine residual addition in
Verilog-2001. The default `LANES=16` uses paired 128-bit A/B words. Lane zero is
the least significant byte. This directory is an isolated candidate for the
three residual Adds in the YOLOv8 model; it is not integrated into production.

For each lane the exact operation is:

```
sum = (qA - zp_a)*scale_a + (qB - zp_b)*scale_b + zp_out*65536
rounded = floor((sum + 32768)/65536)
qOut = min(255, max(0, rounded))
```

Input/output zero points are unsigned bytes. The unsigned 32-bit Q16 constants
`scale_a` and `scale_b` express input-scale/output-scale ratios. Their full
range is supported, including bit 31. Codes below an input zero point retain
their negative contribution: operands are never clamped. Ties round toward
positive infinity, including signed negative half ties, before output saturation.

Signed offsets use 9 bits (-255..255). Each unsigned scale is zero-extended to
a signed 33-bit value; products use 42 signed bits. The sum, output bias and
rounding use 43 signed bits. At the extrema, both products together have
magnitude at most `2*255*(2^32-1)`, so this width cannot overflow. An arithmetic
right shift implements signed floor division.

The interface uses `clk` and asynchronous active-low `rst_n`; `s_data_a`,
`s_data_b`, `s_valid`, `s_ready`, `s_last`; live constants `scale_a`, `scale_b`,
`zp_a`, `zp_b`, `zp_out`; and `m_data`, `m_valid`, `m_ready`, `m_last`.
An input pair is accepted only at a rising edge with `s_valid && s_ready`.
All arithmetic and `last` use the constants at that edge; the result is stored
in one output register, which also acts as the per-word constants snapshot.
Subsequent changes to the constants cannot alter an accepted word. A stalled
input uses the constants at its eventual acceptance, rather than when first
offered. Keep A/B/last stable while an offered input stalls.

The output becomes valid immediately after the accepting edge. It remains
stable until consumed at a later rising edge with `m_valid && m_ready`.
Consumption and replacement may occur at the same edge. `s_ready` is low during
reset and whenever a valid output is stalled. Reset discards a pending word and
clears output data, valid and last. There is no runtime configuration table.

For requantization, set `scale_b=0` (B may contain anything), or hold every B
lane at `zp_b` so that its centered contribution is zero. Set `scale_a` to the
source/destination scale ratio and select the source and destination zero points.

Run from this directory in PowerShell:

```
& C:/Users/NineSun/anaconda3/python.exe run_tests.py
```

The runner defaults to `C:/modeltech64_10.6e/win64`; `--modelsim-bin` or
`MODELSIM_BIN` overrides it. It runs seven Python golden tests, compiles RTL/TB
with `vlog -vlog01compat -pedanticerrors -lint`, and verifies lane counts 16, 1
and 4. An independent exact
rational check validates the integer oracle over 5,000 random lane cases.
Directed and random cycle vectors check negative operands, different domains,
full-width scales, cancellation, saturation, half ties and neighbors, all uint8
codes, requantization, backpressure, last, occupied reset and changing constants.
Every cycle checks ready/valid and every valid word checks data/last, including
through stalls. Test failures are detected even if ModelSim exits successfully.
Artifacts, libraries, logs and machine-readable results stay in `artifacts/`.

No PDS or board run is performed. Resource use, timing closure and any system
speedup are unmeasured; the combinational multiplier path needs separate
implementation assessment before integration.
