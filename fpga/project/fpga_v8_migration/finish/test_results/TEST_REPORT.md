# Isolated convolution finish test report

Result: PASS

UTC: 2026-10-04T18:26:55.954685+00:00
Python: C:\Users\NineSun\anaconda3\python.exe (3.12.4)

Scope: standalone candidate raw-accumulator arithmetic. No production RTL, PDS,
board files or activation regression were changed or run.

Scalar golden: 7 unittest cases passed, including 12,000 exact rational cross-checks,
all half-boundary neighbors, unsigned full-scale multiplication and signed bias.

ModelSim: 10.6e, Verilog-2001 compilation (-vlog01compat). Six simulation runs:

| Lanes | Seed | Cycles | Accepted | Checked outputs | Lane golden checks | Busy config rejected |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 56401 | 7411 | 4686 | 4678 | 4686 | 580 |
| 1 | 20261007 | 7409 | 4714 | 4706 | 4714 | 553 |
| 3 | 56401 | 5451 | 2752 | 2744 | 8256 | 529 |
| 3 | 20261007 | 5451 | 2716 | 2708 | 8148 | 527 |
| 16 | 56401 | 4652 | 1923 | 1915 | 30768 | 566 |
| 16 | 20261007 | 4653 | 1796 | 1788 | 28736 | 612 |

Totals: 18587 inputs, 18539 checked outputs, 85308 lane golden checks, 48 intentionally discarded accepted words on reset.

Every run verifies both different programmed 256-byte tables at all 256 addresses,
and all 256 bypass codes. Tests reject configuration with product-only, sum-only,
byte-only, output-only and all-four-stage occupancy (masks 1,2,4,8,15), including
internal data with an empty LUT and the output consumption edge. They also verify
idle config priority, draining under a held config request, changing all constants
and bypass during long stalls, last alignment, signed32 extrema at scale65535,
reset at every occupied stage, and LUT retention after reset.

Each run measures 96 consecutive words at one word per clock, with four accepting
edges of input-to-output latency. Output data and last are checked on every valid
cycle, including stalls; only actual accepted inputs enter the scalar scoreboard.

Observed total stalled output cycles: 10882.
Observed config rejection with internal data and empty LUT: 248.
Observed full-scale extreme lane cases: 1642.
Observed exact half-tie lane cases: 5344.

Directed stalls with all four registers occupied: 144 cycles. Live input changes during
those stalls: scale=144, bias=144, zero point=144, bypass=81.

Each run observes the exact complete supported raw Q16 bounds:
-140737488355328 through 140737505001472. The maximum with rounding added is
140737505034240, within signed51.

Compilation reports Errors: 0, Warnings: 0. Simulation reports no errors; the
local ModelSim settings emit vsim-8891 because optimization is disabled (-novopt).
This environment warning is retained verbatim per run in results.json and logs;
no other simulation warning is accepted by the runner.

Activation source SHA256 before and after (identical):

`c9bd6eeb046f1064f39492d70467e7aacc54279d28a3692f0e39d8284f280470`

Exact commands, source/stimulus/trace hashes, per-phase counts and coverage:
[results.json](results.json). Compiler: [compile.log](compile.log).
Scalar tests: [python_tests.log](python_tests.log). Each run has its matching
`.stimulus.txt`, `.trace.txt` and `.log` retained here.

Reproduce from finish: `python run_tests.py`.

This demonstrates isolated simulation behavior. Synthesis, timing closure and
board integration remain outside this candidate's scope.
