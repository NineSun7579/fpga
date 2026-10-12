# Affine arithmetic verification

Result: **PASS**. Executed with `C:/Users/NineSun/anaconda3/python.exe
run_tests.py` and ModelSim SE-64 10.6e binaries at
`C:/modeltech64_10.6e/win64`. Logs record 2026-10-05.

All created sources and artifacts are under `project/fpga_v8_migration/affine`.
Workspace/project AGENTS were read and the module name was checked for
duplicates before implementation. Production directories and project source
registration were not edited. Both new Verilog files were verified as ASCII.

The module defaults to 16 byte lanes (128 bits per input), uses unsigned 32-bit
Q16 scale ratios, and preserves signed centered operands before one final
round/saturation. The regression explicitly checks the negative contribution
example `(127-128) + (64-64) + 100 = 99`; clamping either input before addition
would incorrectly produce 100. A registered output captures the computation
and last at acceptance, preserving them as live constants change during stalls.

| LANES | Cycles | Accepted | Consumed | Reset-discarded | Stalled output cycles | Last consumed | Consume + replace |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 5,288 | 2,868 | 2,853 | 15 | 1,922 | 362 | 2,483 |
| 1 | 6,248 | 3,773 | 3,757 | 16 | 1,998 | 323 | 3,402 |
| 4 | 5,481 | 3,028 | 3,015 | 13 | 1,990 | 357 | 2,666 |

Accepted equals consumed plus reset-discarded in every run. The TB checks
ready/valid cycle timing and data/last for every valid word, including repeated
checks during stalls. It also checks asynchronous clearing before the next
rising edge and synchronous observations during reset. Each run uses 5,000
deterministic random cycles plus directed cases; the base seed is `0xA8816`
and the per-scenario random seed is the base plus LANES.

Coverage includes negative operands, different domains, both saturations,
positive and negative half ties and adjacent Q16 values near zero, upper-bound
ties, all 256 byte codes in four domains, unsigned scale bit 31, maximum scales,
large opposite-sign cancellation with tiny remainders, zero scales, both forms
of requantization, source/sink stalls, last, reset while occupied, changing
constants while stalled and new constants on the next accepted word.
For LANES=16, accepted arithmetic covers 33,758 lanes with a negative operand,
15,631 lower saturations, 15,764 upper saturations, 1,265 half ties, and 14,493
unsaturated results. Constants changed on 1,918 stalled output cycles.
These arithmetic counts describe accepted words, including words later reset.

Seven Python unit tests passed. The integer oracle's signed rounding and output
saturation were independently compared against exact `Fraction` arithmetic on
5,000 random lane cases. ModelSim compilation used
`-vlog01compat -pedanticerrors -lint`: all three compiles had zero errors and
zero warnings. Simulations had zero errors; the installed ModelSim configuration
reports its inherited disabled-optimization warning (`vsim-8891`).

Reproduce from this directory:

```
& C:/Users/NineSun/anaconda3/python.exe run_tests.py
```

Machine-readable counts and source SHA-256 values are in
`artifacts/results.json`; Python, compile and simulation logs and cycle vectors
are retained in `artifacts/`. The runner requires the TB's explicit PASS marker,
rejects failures even when the simulator returns zero, and cross-checks Python
and TB transaction counts.

This is an isolated simulation result. The component is not integrated. No PDS,
FPGA synthesis, timing closure, resource measurement or board run was performed;
there is no speedup claim.
