# Candidate convolution finish pipeline

`fpga_v8_conv_finish.v` is an isolated Verilog-2001 candidate. It instantiates the
existing read-only `../activation/fpga_v8_activation_lut.v`; compile both files.
No production source, PDS source list or board flow is connected to this module.

`LANES` defaults to 16. Lane 0 occupies the least significant 32-bit input/bias
slice and the least significant 8-bit output slice. Interpret each `s_data` and
`folded_bias_q16` slice as signed32. `scale_q16` is a shared unsigned16 value and
`preactivation_zero_point` is unsigned8. At `s_valid && s_ready`, all constants,
input data, `s_last` and `bypass` belong to that word and are sampled together.
Input data and last must hold while a valid offer waits; constants may change,
and the accepted values determine the result.

For each lane, compute without intermediate wrapping:

```
raw_q16 = accumulator * scale_q16 + folded_bias_q16 + zero_point * 65536
code = clamp(floor((raw_q16 + 32768) / 65536), 0, 255)
output = bypass ? code : activation_table[code]
```

The multiplier has explicitly signed 32-bit and positive 17-bit operands and a
49-bit result. Products, bias addition, zero-point addition and rounding use
signed 51-bit values. The complete supported range is far inside signed51:
minimum raw is -140737488355328; maximum raw plus rounding is 140737505034240.
Half ties round toward positive infinity. Bypass skips only the LUT lookup;
requantization and clamping still apply.

Three independent elastic stages hold product/constants, Q16 sum and clamped
bytes. The reused LUT supplies the fourth register. All stages can stall; a
blocked output holds data and last. With no stalls, input edge N produces a valid
output after edge N+3, consumable at edge N+4, at one word per clock.

`rst` is synchronous and active high, matching the LUT. It empties all stages,
discards pending words and blocks input/configuration while asserted. It retains
the LUT contents. Program every address before non-bypass use after startup.

Configuration uses `cfg_valid`, `cfg_ready`, `cfg_addr[7:0]`, `cfg_data[7:0]`.
A write occurs only on `cfg_valid && cfg_ready`. Readiness requires all three
wrapper stages and the LUT output to be empty. A request deasserts `s_ready`
immediately and has priority when idle. Pending words keep draining while the
request waits; the LUT receives only the gated, accepted configuration request.
The last output's consumption edge remains busy; the following edge can write.
Holding `cfg_valid` high permits one write per idle clock, with source blocked.

This follows the proposed raw-accumulator formula in `../integer_reference.py`,
with a shared multiplier constrained to unsigned16. Bias is already folded; do
not subtract the input zero point again. It does not reproduce legacy convolution
RAM truncation or wrapping.

Run `python run_tests.py` from this directory. The independent scalar golden has
no NumPy/ONNX or production-model dependency. The runner compiles only this RTL,
its testbench and the reused LUT. It tests LANES 1, 3 and 16 with two deterministic
seeds, two different complete tables, exhaustive table/bypass address coverage,
rounding neighbors, full-scale extremes, random traffic and control corner cases.
All generated simulation files and evidence stay under `test_results/`.
See `test_results/TEST_REPORT.md` and `test_results/results.json` after a passing run.
