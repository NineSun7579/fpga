# Isolated seven-writer DDR AXI4 arbiter

`fpga_v8_ddr_write_arbiter.v` is a standalone candidate for six camera writers
at slots m0..m5 and the cooperative preprocessing writer at m6. No integration
is installed: it is not instantiated by `cooperative_axi`, the board RTL or
any PDS project. All handwritten files and generated simulation artifacts
belong to this directory. Production `source/axi_crossbar/ddr_w_arb.v` was read
as Python bytes and remains unchanged.

## Ports and packing

Defaults are `MASTER_COUNT=7`, `ID_WIDTH=4`, `ADDR_WIDTH=32`, `DATA_WIDTH=128`.
`OWNER_WIDTH` defaults to `max(1, ceil(log2(MASTER_COUNT)))`; leave it at its
derived value. Legal parameters have positive master/ID/address widths and a
positive, byte-multiple data width. The tested configuration is the default.
All inputs and outputs share `clk`; `rst_n` is synchronous, active low.
Handshake outputs are also suppressed while `rst_n` is low.

Each master vector is flattened with slot i at `[i*FIELD_WIDTH +: FIELD_WIDTH]`;
slot m0 is least significant. For example, m6's AWID is `m_awid[27:24]` and its
128-bit W word is `m_wdata[895:768]`. Single-bit fields use `[i]`. The slave
ports `s_aw*`, `s_w*`, `s_b*` are ordinary, unflattened AXI signals.

AW carries ID, ADDR, LEN, SIZE, BURST, LOCK, CACHE, PROT, QOS and REGION.
QOS/REGION ports are always present: explicitly tie unused per-master fields
to zero, matching the existing cooperative bridge's constants. Do not leave
them disconnected. W carries DATA, byte STRB, LAST and VALID/READY. B carries
the complete downstream ID, RESP and VALID/READY. There is no WID or read port.

`busy` covers selection through B retirement, including an AW stall. `owner`
identifies that slot while busy; its idle value is unspecified for integration.
`error` is the OR of sticky `error_flags`. Unused debug outputs may be left open.

## Selection, acceptance and retirement

The arbiter starts its round-robin search at m0 after reset, selects the first
valid requester in wrapped order, and registers both its owner and **every AW
field** at that selection edge. Selection does not acknowledge the source.
The registered AW is exposed on the following cycle; its VALID and payload
stay stable until the slave accepts it. A new higher-priority request cannot
replace this descriptor. This adds one selection cycle even when AWREADY is
already high.

Only the selected master's AWREADY is driven, and only when the slave is
accepting the registered AW. The source's AW handshake and the slave's AW
handshake therefore occur at the same edge. The source must keep AWVALID and
its full descriptor stable until that edge. After acceptance it may immediately
replace its live AW fields; the arbiter continues to use its captured ID/LEN.

WVALID cannot reach the slave before AW acceptance, including the AW acceptance
cycle itself. Afterward only the owner has WREADY. W DATA/STRB/LAST pass through
without buffering, so a source must hold each W payload/VALID until acceptance.
The arbiter counts exactly `AWLEN+1` accepted beats using a nine-bit counter
(including a 256-beat burst). WLAST mismatches set a diagnostic; they do not
shorten the count or discard data. No extra W beats are accepted after that
count has completed.

Only after the complete W count are BVALID and BREADY enabled for the owner.
An early slave B is blocked from retirement, flagged, and can remain asserted
until the expected W beats finish. The full slave BID/BRESP then pass unchanged
to the owner, even on errors. Invalid owners have BVALID low; BID/BRESP are
broadcast payloads and have no meaning there. IDs are neither minted nor
rewritten. All seven writers may use the same ID because exactly one write
transaction owns the path at any time.

Ownership ends only on the owner's B handshake. The next RR start becomes
`(retired_owner+1) mod MASTER_COUNT`. Other masters' AWREADY/WREADY/BVALID stay
low throughout the transaction. There is an idle/selection bubble at handoff.

## Data availability and reset contract

**Stage the entire burst before asserting AWVALID**, or provide equivalent
upstream/DDR-glue WAIT_FOR_DATA staging that guarantees all requested beats are
available independently of further pixel acquisition. The arbiter does not
buffer a full burst. It tolerates transport W bubbles, but cannot prevent a
writer that waits for future pixels after taking ownership from blocking every
other writer. The cooperative bridge currently buffers its single packed word
before AW; a future connection must preserve that guarantee.

A selected request cannot withdraw VALID, change its pending descriptor or
reset its source independently. Reset during selection or an outstanding write
requires a **common AXI reset** of masters, arbiter and slave/glue. Arbiter-only
reset cannot cancel a request that a slave has accepted, and IDs are reused.
There is no cancellation, watchdog or automatic timeout recovery in this RTL.

## Sticky diagnostics

Flags accumulate across transactions and clear only on common reset:

| Bit | Meaning |
| --- | --- |
| 0 | Accepted WLAST differs from the final beat implied by captured AWLEN. |
| 1 | Visible response BID differs from captured AWID. |
| 2 | Visible BRESP is non-OKAY (`!= 2'b00`, including EXOKAY). |
| 3 | Slave BVALID appears before the response phase, including unsolicited idle B. |
| 4 | Selected source withdraws AWVALID or changes a captured AW field before acceptance. |

Diagnostics do not rewrite descriptors/responses, switch owner, skip expected
beats or drop a B. A missing final WLAST still finishes the arbiter's expected
count; early WLAST still requires the remaining beats. A malformed slave that
waits forever for another WLAST, omits B, or sends unsolicited extra responses
requires common reset/system recovery. Fault detection alone cannot repair its
protocol. ID checking uses the captured descriptor, even after the source has
retired and poisoned its live AW inputs.

## Actual ModelSim regression

Run from this directory in PowerShell:

```powershell
python run_tests.py
```

Python uses the standard library and the installed ModelSim executables at
`C:/modeltech64_10.6e/win64`; `MODELSIM_BIN` overrides that directory. Select a
case with `--case rr_seed_12345` (repeat the option for more cases). The runner
does not invoke PDS, synthesis, board programs or the cooperative bridge.

The SystemVerilog testbench maintains a separate RR/ownership scoreboard,
snapshots observed source AW descriptors at selection, checks the complete AW
payload, and asserts stable master/slave VALID and payload under backpressure.
It checks all controls with X-sensitive comparisons and compares every W byte,
including unstrobed bytes. A second, independent Python oracle verifies the
trace's complete descriptors, bytes, strobes, beat order, responses, repeated
RR order and reset boundaries. Hex parsing rejects X/Z; no bytes are skipped.

Three random seeds each run all seven simultaneous writers through 32
transactions apiece: lengths 1/2/16 and a final 256-beat burst, identical ID=9
for the first 16 transactions per master, then distinct IDs 1..7. Random AW/W
backpressure, source W bubbles, response delay and individual master BREADY
stalls supplement guaranteed long stalls. Source W is also offered before AW
while slave WREADY is high; the monitor requires zero forwarding/acceptance.
Live AW fields are poisoned after every source AW handshake.

Directed cases exercise m6 selected before m0 arrives during an AW stall;
wrong BID, SLVERR/DECERR, early and missing/late WLAST, and B arriving before
the complete count; plus one deliberately invalid source AW change to verify
the registered snapshot and flag 4. Too-late WLAST is offered as an illegal
extra beat, must remain blocked, and the fault source abandons it after B.
That exception applies only to deliberately malformed test stimuli.

Five common-reset phases cover stalled AW, stalled W, partially transferred
W, delayed B and stalled B. Every reset is followed by a seven-writer clean
restart; no ghost grant/response/error may survive. Artifacts retain exact
vlib/vlog/vsim commands, pass markers, logs, traces, input hashes, compared-byte
hashes, counts and cycles in `artifacts/results.json`. See `REPORT.md` for the
recorded run. Simulation proves this isolated interface contract; integration,
whole-design synthesis/timing and board behavior remain pending.
