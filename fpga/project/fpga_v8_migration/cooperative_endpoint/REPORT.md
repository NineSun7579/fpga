# Isolated endpoint regression report

Status: **PASS**, ModelSim 10.6e, `python run_tests.py`.

The run completed 419 operations over 11,893 clock cycles. All 3,803 public
trace events matched the independent Python oracle, including 419 final bank
states, 1,230 full W handshakes, 881 full R handshakes, 72 full B responses,
42 actual controller B handshakes and 318 actual controller R handshakes.
Partial reset scenarios intentionally omit the abandoned replies. Local AW
arrived before local W on 20 writes and W before AW on 15 writes; both orders
and simultaneous channels ran through periodic independent backpressure.

The initial byte-level scan examined 9,756 existing RTL files and found no
conflicting declaration. The runner rescans module declarations as bytes
and verifies that each new module name has exactly one definition.

| Coverage | Verified behavior |
| --- | --- |
| Real 16-byte H2F register writes | All strobes asserted with pseudo-random upper 96 bits; exactly one low-word local write |
| Register addressing | Identity/version/status/hint, all 11 descriptor words, ACK slots and counters; RO/unimplemented local SLVERR propagated |
| Ownership | Real bank0 CLAIM, immutable descriptor while bank1 writes/completes, matched ACK frees only bank0, then bank1 CLAIM/ACK |
| Rejection counters | Wrong bank ACK and stale generation ACK yield exactly two rejects while both banks remain owned; wrong/duplicate CLAIM yields exactly three rejects |
| Snapshot | A live STATUS response remains frozen with full R stalled across bank1 completion |
| Invalid writes | Misalignment/window/alias, SIZE 0/1/2/3/5/7, unsupported BURST, singleton missing LAST, 2/3/16/17/256 promised beats with correct/early/missing LAST |
| Invalid reads | Same validation classes; exact 2/3/16/17/256 zero SLVERR beats, original ID, exact final LAST, no local AR |
| Pending metadata | Next AW/W remains asserted throughout valid B backpressure and invalid 256-beat draining; next AR remains asserted throughout 256 error R beats |
| IDs and PROT | All 128 seven-bit IDs returned intact, including `010xxxx`; PROT forwarded, LOCK ignored |
| Concurrency | Actual independent controller read and write; actual controller B and R held for 80 cycles without timeout |
| Reset | Pre-AW W, full B, local B, local R, full R, local AW waiting for W, partial invalid 256-beat drain, full AW waiting for W |
| Fresh generation | Same bank/sequence after reset with changed generation rejects the stale ACK, then accepts the matching ACK |
| Strict protocol checks | No X/Z outputs including reset/idle, stable full/local outputs under stalls, no local write before validation, no B before exact promised drain, no new AW/AR while prior response is pending |

The full existing controller file is byte-for-byte invariant before and
after the run. Its SHA-256 is:

```
fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae
```

The tested endpoint SHA-256 is:

```
5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e
```

`artifacts/results.json` contains complete controller before/after hashes,
endpoint/testbench/trace hashes, tool commands, module scan and event counts.
`expected.trace` is generated from planned host/producer transactions before
ModelSim runs; `actual.trace` records public handshakes only. Comparison is
per operation/channel so legal AW/W timing does not constrain the oracle.
`comparison.txt` and `tool_*.log` retain the comparison and compiler/simulator
evidence. The endpoint/controller compile as Verilog-2001; the TB is SV.

All authored and generated files stay under this new directory. There is no
production M02 decode reservation, PDS/IP edit, hardware deployment, or change
to the default cooperative core. This report does not establish whole
cooperative acceptance. Global NPU decode recovery/window reservation, host
ioctl BRESP behavior and output DMA, actual DDR/bridge/frame data, external
camera leases and hardware timing require their own integration evidence.
