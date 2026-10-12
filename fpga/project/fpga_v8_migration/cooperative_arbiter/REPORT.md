# Seven-master DDR write arbiter evidence

Actual ModelSim SE-64 10.6e regression completed on 2026-10-05 with
`python run_tests.py` in this directory. All six cases passed their explicit
simulator completion markers and independent Python trace checks.

| Case | Retired B | Accepted W beats | Compared W bytes | Cycles | Final error flags |
| --- | ---: | ---: | ---: | ---: | ---: |
| RR seed 12345 | 224 | 3,129 | 50,064 | 14,670 | 0 |
| RR seed 67891 | 224 | 3,129 | 50,064 | 14,664 | 0 |
| RR seed 314159 | 224 | 3,129 | 50,064 | 14,571 | 0 |
| Late contender | 2 | 2 | 32 | 101 | 0 |
| Protocol faults | 7 | 112 | 1,792 | 485 | 31 (expected) |
| Common reset | 35 | 593 | 9,488 | 2,629 | 0 |
| Total | **716** | **10,094** | **161,504** | **47,120** | |

Every W byte, including unstrobed lanes, was checked by the X-sensitive HDL
scoreboard and again by Python. No X/Z bytes are filtered. Each main seed
verified 32 writes per each of seven simultaneously requesting writers, exact
`m0,m1,...,m6` repeated RR order, lengths 1/2/16/256, ID=9 shared by all writers
for the first 16 writes, then distinct IDs 1..7. It also checked the complete
65-bit AW payload including QOS/REGION and deliberately poisoned every live
source AW field after its handshake.

Coverage across the six cases included 4,665 AW stall cycles, 9,401 W stall
cycles and 5,768 response-phase B stall cycles. Each main seed also saw over
900 source W bubble cycles. Upstream WVALID was offered with slave WREADY high
before AW acceptance; the monitor required no W forwarding or upstream READY.
Per-master READY/BVALID checks required no nonowner handshake leakage.

The directed late-arrival case held m6's descriptor during AW backpressure
while m0 became valid, then retired m6 before m0. The protocol-fault case
retired all seven transactions despite wrong BID, non-OKAY BRESP, early WLAST,
missing/too-late WLAST and early B. Wrong BID/BRESP reached the owner unchanged.
An extra beat carrying a too-late WLAST was offered but never accepted. One
selected source illegally changed its pending AWID/address: the original
snapshot remained stable and flag 4 joined the other expected sticky flags.
The final clean m6 write verified continued arbitration after those errors.

The reset case exercised five common-reset phases: AW stalled, W stalled,
partial W, delayed B and B stalled. Each was followed by seven clean retired
writes. Four accepted AW transactions were cancelled only by common reset;
the fifth phase reset an unaccepted selection. The 9,488-byte count includes
33 W beats observed before those resets in addition to 560 restarted beats.
No ghost response, grant or error survived a reset.

## Reproducible files

- `fpga_v8_ddr_write_arbiter.v`: uniquely named RTL, packed seven-master ports.
- `tb_fpga_v8_ddr_write_arbiter.sv`: stimulus, independent selection/retirement
  scoreboard, stability checks, byte comparisons and reset/error cases.
- `run_tests.py`: actual vlib/vlog/vsim runner and independent Python oracle.
- `README.md`: packing, handshake, full-burst staging, diagnostic and reset
  contracts; integration is still absent.
- `artifacts/results.json`: aggregate pass status, exact commands, seeds,
  SHA-256 hashes, per-case metrics and independent byte/trace hashes.
- `artifacts/<case>/`: `run.do`, `vlib.log`, `vlog.log`, `console.log`,
  `transcript.log`, `trace.csv` and isolated ModelSim work library.

Verified input SHA-256 values for this run:

| File | SHA-256 |
| --- | --- |
| RTL | `c0982b49617f416f96d3b338df822c5ce0e0701aa8425f766da85f00a8ffc969` |
| Testbench | `6d63c852e0b6535380be42446a04552d69b5ee973ac98efac691f59bf3ba2e21` |
| Runner | `ed013db51c2fbc4dfc06c29c01a5794510c2dc2e92a05db332d88fe2f28185bc` |
| Read-only legacy `source/axi_crossbar/ddr_w_arb.v` | `b2401c87315d544a7ab85859b7c66d4a7c5822818f32e0f7b42a3f17e35ef10d` |

The legacy hash matched before and after the regression. A Python byte scan of
production source and migration RTL found this candidate module declaration
only in this directory. No production/cooperative_axi/board/PDS files were
edited, and no PDS process was launched. The simulator's inherited `-novopt`
warning was informational; there were no compile/simulation errors.

This proves the isolated arbiter behavior for its default seven-master,
4-bit-ID, 128-bit-data configuration. No installed owner wiring, DDR glue
integration, whole-design synthesis, timing closure, board throughput or
cooperative speedup is established. Future integration must enforce the
full-burst-before-AW staging and common-reset contracts in `README.md`.
