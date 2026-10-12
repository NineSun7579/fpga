# Verified cooperative controller candidate

Status: PASS in ModelSim 10.6e, compiled as Verilog-2001 without `-sv`.
This is an isolated reviewable controller, not capture or DDR integration.

Files:

- `fpga_v8_coop_control_axil.v`: unique synthesizable controller/AXI-Lite module.
- `tb_fpga_v8_coop_control_axil.v`: public-port vector driver and output trace.
- `run_tests.py`: independent lease-record/two-bank FIFO scoreboard, directed
  stimuli, randomized ownership operations and per-cycle comparisons.
- `README.md`: lease prerequisite, bridge wiring, registers, host protocol,
  common-reset contract and unresolved external identity rollover policy.
- `artifacts/results.json`: machine-readable validation evidence and RTL hash.

Command: `python run_tests.py` from this directory.

| Case | Compared cycles | Coverage |
| --- | ---: | --- |
| directed | 1,153 | Protocol, ownership, reset and concurrent events |
| random_11 | 14,293 | 180 frames with varied stalls/errors/host retention |
| random_29 | 14,454 | 180 independent randomized frames |
| random_83 | 14,609 | 180 independent randomized frames |
| parameterized | 1,153 | Directed suite with output addresses `0x08400000` / `0x08800000`, length 4,096 |
| Total | 45,662 | 311 public output bits compared on every cycle; 540 randomized frames |

Verified behavior:

- Caller-certified RAW acceptance implicitly claims an existing source lease;
  uncertified RAW rejection neither reserves output nor starts/claims/releases.
- Immediate WRITING reservation and busy at descriptor acceptance; registered
  command fields stable through bridge readiness stalls; premature done ignored.
- Delayed final drain prevents premature READY/release; successful and failed
  operations release the exact source metadata through backpressure.
- Transient in-flight errors remain latched until done. The existing bridge's
  no-done `cmd_error` rejection retires at bridge idle.
- Two independent output states, no overwrite of HOST_READING or READY;
  both-READY and HOST_READING-plus-READY backpressure rather than drop/evict.
- Oldest-ready CLAIM, one host context, all descriptor words bound to that
  claim while the other bank completes; independent numeric-wrap ordering.
- Exact ACK success; wrong bank/sequence/generation, duplicate, no-claim and
  READY-only ACK rejection retain ownership and increment rejection counts.
- All 16 ACK byte-strobe patterns, byte updates on every staged ACK field,
  zero-strobe command no-op, AW-first/W-first/simultaneous writes and gaps.
- B backpressure with following AW/W held continuously, captured R stability,
  blocked next AR, consecutive R consumption/AR acceptance and exact decode.
- Same-edge completion/CLAIM and completion/ACK, including a premature CLAIM
  that must not bind a bank becoming READY on that same edge.
- Coordinated reset during claims, partial AW/W, queued command, active bridge,
  pending B/R and source release; valid post-reset operation and stale ACK
  rejection when the external manager supplies a fresh generation.

All test outputs and ModelSim work libraries are inside `cooperative_control`.
The new module names were checked against existing Verilog modules using a
byte-level scan before creation. RTL/testbench are ASCII. No production source,
project/PDS registration, board files, DDR top or test outside this directory
was edited or executed.

Integration boundary: the RAW-valid bit trusts an external manager. Stable RAW
capture leases, exclusive output ranges, correct output geometry, global ACK
identity uniqueness, fresh reset generation, rollover handling and common
bridge/bus reset remain required external guarantees. These tests model the
existing bridge's status contract and do not certify camera capture or DDR
behavior. See README for the exact contract.
