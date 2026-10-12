# Four-master DDR write arbiter simulation

Validates `source/axi_crossbar/ddr_w_arb.v` after the CAM4 extension to four
masters (cam1..cam4). Adapted from `sim/cam3_arb_test/tb.sv`.

Run from the project directory (ModelSim SE-64 10.6e at
`C:\modeltech64_10.6e\win64`):

```powershell
$ms='C:\modeltech64_10.6e\win64'
Push-Location sim/cam4_arb_test
& "$ms\vlib" work; & "$ms\vlog" -quiet -work work ../../source/axi_crossbar/ddr_w_arb.v tb.sv
& "$ms\vsim" -c -do "run -all; quit -f" work.tb +MODE=0
& "$ms\vsim" -c -do "run -all; quit -f" work.tb +MODE=1
& "$ms\vsim" -c -do "run -all; quit -f" work.tb +MODE=2
Pop-Location
```

## Results (2026-09-27, four masters)

| Mode | W backpressure | Cycles | AW / W / B total | W stall | B stall | Result |
|---|---|---:|---|---:|---:|---|
| 0 | Deterministic (2 of each 5 cycles blocked) | 1517 | 96 / 432 / 96 | 265 | 100 | PASS |
| 1 | Pseudorandom LFSR, seed 0x13579bdf | 2763 | 96 / 432 / 96 | 1512 | 99 | PASS |
| 2 | AWREADY held low, later request arrives | — | — | — | — | AW_STABILITY_PASS |

Each of the four masters registers `AW=24 W=108 B=24 max_grant_gap=4`. A grant
gap of 4 means all three other masters are served before the same master again,
i.e. strict round-robin over four requesters.

Scoreboard checks (all passing): AW field routing, W data/strb/last with
per-master/per-transaction/per-beat encoding, ready/valid routing, B ID and
response routing (all four BRESP values exercised), single outstanding
ownership, W payload stability while stalled, and strict round-robin order.

## AW-stability note

`sim/cam3_arb_test/README.md` documents that the earlier combinational grant
design FAILED mode 2: an arriving higher-priority request changed the slave AW
payload while AWVALID was asserted and AWREADY was low. The current RTL latches
the winning master (`sel`/`sel_valid`) until AWREADY accepts it, so mode 2 now
reports `AW_STABILITY_PASS`.

These tests instantiate the arbiter alone with behavioral masters/slave, not the
complete glue or DDR IP. No PDS or hardware actions are involved.
