# Three-master DDR write arbiter simulation

Run from the project directory:

```powershell
python sim/cam3_arb_test/run.py
```

Uses ModelSim SE-64 10.6e at `C:\modeltech64_10.6e\win64`. The Python runner discovers ports using bytes regex, generates `tb.sv` using bytes replacement, and compiles the production `source/axi_crossbar/ddr_w_arb.v` directly. All generated files and logs reside in this directory. The runner verifies the RTL bytes remain unchanged.

## Normal throughput: PASS

Both modes hold downstream AWREADY high, representing the specified immediate AW acceptance behavior. All three masters assert AW requests together and keep requesting until each has submitted 24 transactions. Requests and W payloads remain stable until accepted. Bursts vary from 1 to 8 beats; each master transfers 108 beats total. W data encodes master, transaction and beat. Scoreboarding checks AW fields, W data/strb/last, ready/valid routing, B ID/response routing, transaction counts, single outstanding ownership, W stability during stalls, and strict round-robin order. B is delayed 3–8 cycles after the last W beat; master BREADY also applies periodic backpressure. All four BRESP values are exercised as routing data.

| Mode | W backpressure | Cycles | AW / W / B total | W stall cycles | B stall cycles |
|---|---|---:|---|---:|---:|
| 0 | Deterministic, 2 of each 5 cycles blocked | 1119 | 72 / 324 / 72 | 195 | 60 |
| 1 | Pseudorandom LFSR, seed 0x13579bdf | 2021 | 72 / 324 / 72 | 1083 | 74 |

Each mode prints all three masters with `AW=24 W=108 B=24 max_grant_gap=3`. The gap is measured in global AW grant positions; a gap of 3 means the other two masters receive their grants before the same master is granted again. Actual evidence is retained in `mode0.log`, `mode1.log` and the corresponding transcripts.

## Separate AW backpressure diagnostic: FAIL

Mode 2 resets the arbiter (round-robin preference m0), holds AWREADY low and initially requests only m2. The slave presents ID `a`, address `10200000`. Before any handshake, m0 starts requesting while m2 continues to hold its original request stable. The slave payload changes to ID `0`, address `10000000` while AWVALID remains asserted and AWREADY remains low. `mode2.log` records `AW_STABILITY_FAIL` at 56 ns.

The combinational grants in production RTL lines 119–132 are recomputed from currently asserted requests; selection is only locked upon AW acceptance at lines 167–172. Thus an arriving higher-priority request can change the selected AW during a stall. This violates AW payload stability under backpressure. It is independent of the passing immediate-acceptance throughput tests; no production RTL fix was made.

The runner returns success when both throughput tests pass and the separate diagnostic reproduces this known failure. `summary.txt` explicitly labels the AW stability result as FAIL; process success must not be interpreted as all protocol checks passing.

Compilation: 0 errors, 0 warnings. Simulations: 0 ModelSim errors; each has the inherited `-novopt` performance warning (vsim-8891). These tests instantiate the arbiter alone with behavioral masters/slave, not the complete glue or DDR IP. No PDS or hardware actions are involved.
