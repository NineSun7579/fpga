# Model-specific convolution finish validation

Result: PASS

UTC: 2026-10-04T22:35:49.763684+00:00
Python: C:\Users\NineSun\anaconda3\python.exe (3.12.4)

ModelSim 10.6e, LANES=2, existing finish RTL and activation LUT unchanged.
55 actual exported tasks: 49 SiLU and 6 Clip. No prior tests, PDS synthesis,
production change or full-graph inference was run.

Compared 85795 words, 171590 physical lane bytes,
170414 real output lane bytes and 1176 masked dummy lane bytes.
Checked 361076 lane values on valid cycles, including stalls;
all 85795 output last flags match. Every expected word was accepted
and consumed exactly once in order. No X output or minimum-length comparison skip.

Current integer_reference.py expression/saturate_q16 cross-checks: 171590 lanes.
All 5113 real channel biases tested with model/achievable bounds, trace extrema,
zero raw input, all-input-zp cancellation, signed32 extrema, half-residue searches
and zero/255 rounding transition neighbors. Raw model bounds are all strictly
below 2^31; largest is 7636485.

Verified hardware constants: shared scale 51..378; signed folded bias -4387811..8149173.
Exact half ties are reachable for 3586 channels,
with 3566 selected ties in the unclamped 0..255 range.
All below/nearest/above residue selections stay within each channel's model raw bound.
Every rounding-search and 0/255 transition fixture also passes with bypass, directly
comparing requantized codes even when neighboring LUT outputs are identical.

All task tables programmed through 14080 idle accepted configuration writes.
Every task tests all 256 table codes using its actual coefficients and biases.
Trace-range random words: 7040 (128 per layer).
Output stall cycles: 94743; directed occupied-all-stage stalls: 880.

Valid words by activation: SiLU=80461, Clip=5334.
Live input changes while words were pending are measured and verified per task:
scale=143660, bias=167492, zero point=143087, bypass=72205.

All-input-zp accumulators are input_zp * signed_weight_sum, including the synthetic
zp-padded window. Accumulator*encoded_scale + folded_bias equals exported bias_q16
exactly for every real channel; no input-zp correction is applied twice.

Odd CO=3 heads use mask=1 for channels [2,3], bias=0 and accumulator=0 for the
dummy lane. The physical dummy LUT result is compared. C16 padding is explicitly
replaced with output-zp after masking; per-word bypass cannot act only on a dummy lane.

C16 fixture bytes compared: 87584 across 55 matching SHA256 pairs.
Pairs follow low-lane/even-channel order and every padded16 byte position is covered.
These hashes describe synthetic model-constant fixtures, not full-frame model outputs.

Compilation: Errors: 0, Warnings: 0. Simulation has no errors; inherited local
-novopt emits vsim-8891 only (recorded verbatim in manifest and simulation.log).

Numeric export SHA256:

`8f54e54744a0d3178337000db219b889742c54400191b35d3919d76b7204a7cd`

Specialized export model SHA256:

`dc940b82d821cd67b3735539c9b9c9011ad695178f468598db79f78a13506b71`

| Task | Activation | CO | Scale | Words | Real bytes | C16 bytes |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | silu | 16 | 85 | 589 | 1178 | 272 |
| 1 | silu | 32 | 303 | 789 | 1578 | 544 |
| 2 | silu | 64 | 286 | 1189 | 2378 | 1088 |
| 3 | silu | 64 | 378 | 1189 | 2378 | 1088 |
| 6 | silu | 32 | 223 | 789 | 1578 | 544 |
| 7 | silu | 32 | 129 | 789 | 1578 | 544 |
| 10 | silu | 64 | 193 | 1189 | 2378 | 1088 |
| 11 | silu | 128 | 120 | 1989 | 3978 | 2176 |
| 12 | silu | 128 | 159 | 1989 | 3978 | 2176 |
| 15 | silu | 64 | 153 | 1189 | 2378 | 1088 |
| 16 | silu | 64 | 82 | 1189 | 2378 | 1088 |
| 19 | silu | 128 | 217 | 1989 | 3978 | 2176 |
| 20 | silu | 256 | 61 | 3589 | 7178 | 4352 |
| 21 | silu | 256 | 106 | 3589 | 7178 | 4352 |
| 24 | silu | 128 | 104 | 1989 | 3978 | 2176 |
| 25 | silu | 128 | 66 | 1989 | 3978 | 2176 |
| 28 | silu | 256 | 135 | 3589 | 7178 | 4352 |
| 29 | silu | 128 | 128 | 1989 | 3978 | 2176 |
| 34 | silu | 256 | 97 | 3589 | 7178 | 4352 |
| 37 | silu | 128 | 212 | 1989 | 3978 | 2176 |
| 40 | silu | 64 | 91 | 1189 | 2378 | 1088 |
| 41 | silu | 64 | 95 | 1189 | 2378 | 1088 |
| 43 | silu | 128 | 279 | 1989 | 3978 | 2176 |
| 46 | silu | 64 | 233 | 1189 | 2378 | 1088 |
| 49 | silu | 32 | 123 | 789 | 1578 | 544 |
| 50 | silu | 32 | 123 | 789 | 1578 | 544 |
| 52 | silu | 64 | 247 | 1189 | 2378 | 1088 |
| 53 | silu | 64 | 77 | 1189 | 2378 | 1088 |
| 55 | silu | 128 | 176 | 1989 | 3978 | 2176 |
| 58 | silu | 64 | 149 | 1189 | 2378 | 1088 |
| 59 | silu | 64 | 134 | 1189 | 2378 | 1088 |
| 61 | silu | 128 | 222 | 1989 | 3978 | 2176 |
| 62 | silu | 128 | 64 | 1989 | 3978 | 2176 |
| 64 | silu | 256 | 157 | 3589 | 7178 | 4352 |
| 67 | silu | 128 | 71 | 1989 | 3978 | 2176 |
| 68 | silu | 128 | 72 | 1989 | 3978 | 2176 |
| 70 | silu | 256 | 178 | 3589 | 7178 | 4352 |
| 71 | silu | 64 | 79 | 1189 | 2378 | 1088 |
| 72 | silu | 64 | 259 | 1189 | 2378 | 1088 |
| 73 | clip | 64 | 170 | 1189 | 2378 | 1088 |
| 74 | silu | 64 | 65 | 1189 | 2378 | 1088 |
| 75 | silu | 64 | 260 | 1189 | 2378 | 1088 |
| 76 | clip | 64 | 202 | 1189 | 2378 | 1088 |
| 77 | silu | 64 | 51 | 1189 | 2378 | 1088 |
| 78 | silu | 64 | 169 | 1189 | 2378 | 1088 |
| 79 | clip | 64 | 253 | 1189 | 2378 | 1088 |
| 80 | silu | 64 | 75 | 1189 | 2378 | 1088 |
| 81 | silu | 64 | 201 | 1189 | 2378 | 1088 |
| 82 | clip | 3 | 248 | 589 | 797 | 272 |
| 83 | silu | 64 | 66 | 1189 | 2378 | 1088 |
| 84 | silu | 64 | 145 | 1189 | 2378 | 1088 |
| 85 | clip | 3 | 238 | 589 | 781 | 272 |
| 86 | silu | 64 | 60 | 1189 | 2378 | 1088 |
| 87 | silu | 64 | 194 | 1189 | 2378 | 1088 |
| 88 | clip | 3 | 95 | 589 | 780 | 272 |

Exact commands, provenance, constant hashes, vector/trace hashes and counts:
[manifest.json](manifest.json). Per-task audit files include every bias, raw bound,
weight sum, searched residue, mask and synthetic C16 hash. Original source
model and specialized export hashes are recorded separately.

Reproduce: `python run_validation.py` from finish/model_validation.

Acceptance is limited to model-asset integration with the isolated finish primitive.
Convolution MACs, legacy wrapping, graph execution, DMA, accuracy, timing closure
and board performance remain outside this evidence.
