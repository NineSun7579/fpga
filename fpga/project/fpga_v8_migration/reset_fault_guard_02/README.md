# Reset guard 02

Replaces the original guard's competing asynchronous set/clear priorities and
state-dependent asynchronous branch with single-reset event witness flip-flops
and persistent free_clk supervisor state. Runtime button reset no longer clears
fault or session authority: a fault requires FPGA reconfiguration.

`run_tests.py` passed nine ModelSim scenarios: short PERST, DDR-init, link,
AXI-reset, PCIe-reset and button pulses between free_clk edges; independent AXI
and PCIe clock stops; combined stopped clocks and a short reset pulse. Every
scenario verifies closed admission, persistent fault, button refusal and both
domain fault readbacks. This does not certify physical pulse width, CDC or
hard-IP retirement.

Actual PDS compile and synthesis passed in `synthesis_02/`. The XML report
`artifacts/structure_checks.json` records **no_clock=0, loops=0, latchs=0,
latch_loops=0, unexpandable_clocks=0**. Resources: 40 LUT, 59 FF, zero RAM.
All three declared clock roots are recognized. Input/output delay gaps remain
unscored; component synthesis is not whole-design routed timing signoff.

`synthesis_01/` retains a rejected hand-authored project-format attempt. The
successful run uses a byte-transformed existing PDS project template; its exact
provenance and source hash are retained. No previous RTL, project, route result,
hard IP, clocks or production deployment was changed.

Remaining integration: register the uniquely named
`fpga_v8_reset_fault_guard_02` module and replace only the old guard instance type
in a fresh whole candidate. The API and parameter names match. Recheck whole
elaboration, reset/CDC behavior, setup/hold/recovery/removal and camera/motion
preservation. The previous candidate still has seven setup failures requiring
separate path-directed corrections. No bitstream or board acceptance is claimed.
