# PCIe H2F retirement evidence

The frozen logic issues controller MSI before full AXI B retirement. A successful
ioctl driven by that MSI cannot justify `DeliveryKnownUnknownResponse` for H2F
control writes. The isolated candidate repairs that completion boundary under
coordinated reset, but is **not a general transport acceptance**: inherited W
backpressure loss and PCIe 4KB crossing defects remain.

## Frozen provenance and simulation qualification

Both captured inputs under `whole_candidate/inputs` and actual
`motion_100h/source` match these hashes before and after the regression:

| Input | SHA-256 |
| --- | --- |
| `source/pcie_dma/pcie_fifo.v` | `c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027` |
| `source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v` | `0ff0f5c28650e8eb91da5bc39a26c6498874cafe0b51ccfa1847872c3cbacc53` |

Official captured `pcie_rx_fifo` and `pcie_tx_fifo` models and standard installed
Pango DRM36K/GRS simulation models are used. The real cooperative AXI128
endpoint and cooperative control are compiled unchanged. All input/model
identities are recorded in `artifacts/hashes_before.json` and
`artifacts/hashes_after.json`.

ModelSim 10.6e rejects the exact frozen byte streams because of forward
declarations. `artifacts/baseline/direct_frozen_compile.log` preserves this
failure. The simulated baseline uses **declaration-only normalization**, with
84 FIFO and 83 controller declarations hoisted, declaration-assignment wires
converted to the same continuous assignment, and two existing implicit nets
declared explicitly. No conditions, arithmetic, procedural body or controller
MSI logic changes. `artifacts/compatibility.json` records this qualification and
hashes. Thus this is the actual frozen *logic*, with a disclosed compiler
compatibility transformation; it is not an exact-byte successful compile.

The external PCIe wrapper is the only stubbed production module. It retains
the real controller, sends actual BAR1 descriptor writes, models request grants
and fetched host data with one-clock RAM read latency. `fpga_rx_done` is always
produced by the FIFO, never injected. Controller inputs reproduce the actual
`ips2l_pcie_dma.v:337-338` wiring, `~fpga_tx_done` and `~fpga_rx_done`.

The AXI route/memory responders are test infrastructure. Control writes pass
through the actual AXI128 endpoint and control. PCIe/core clocks have 16 ns /
10 ns periods. An AXI response gate holds the actual endpoint B for 23 core
cycles and propagates READY consistently, so the measured retirement is the
FIFO-side `BVALID && BREADY`, not internal local AXI-Lite completion.

## Measured failure and candidate result

The actual producer interface publishes bank0 READY before CLAIM. The test
then independently delays local control AW and W acceptance. All times below
are from operation 1 of the final regression:

| Event | Frozen logic | Retirement candidate |
| --- | ---: | ---: |
| Full AXI AW accepted | 1.075 us | 1.075 us |
| Full AXI W accepted | 1.095 us | 1.095 us |
| Control CLAIM changes bank0 to HOST_READING | 1.495 us | 1.495 us |
| Real endpoint full BVALID | 1.505 us | 1.505 us |
| Full B accepted by FIFO | 1.735 us | 1.735 us |
| Controller `o_fpga_msi` | **1.064 us** | **1.816 us** |

Frozen MSI precedes even AW acceptance and CLAIM execution; it precedes final
B by 671 ns. `pcie_fifo.v:197-203` tests FIFO empty immediately after source
word-count completion. This can observe the read-domain empty flag before the
write becomes visible across the asynchronous FIFO, or after final prefetch
while W/B are pending. Either path has no B-retirement condition.

The unchanged controller turns the rising RX-done edge into `chunk_done` and
MSI (`ips2l_pcie_dma_controller.v:719,942-953,992-1006`). The outer actual DMA
wrapper latches that pulse as an MSI request (`ips2l_pcie_dma.v:112-127`).

Nine consecutive 16-byte control transfers cover CLAIM, ACK bank/sequence/
generation setup, matching ACK, rejected CLAIM, rejected ACK, full AW stall,
local AW/W stalls and a post-reset transfer. Each command produces exactly
one expected full AW, W, local AW, local W, B and MSI. Physical addressing is
`0x40010000 + 4 * local_offset`, preserving the 16-byte register stride.
Candidate MSI occurs 81–95 ns after the accepted ID-zero B, including SLVERR
responses. Frozen MSI occurs before B for every one of those writes.

## Streaming and negative fixtures

| Transfer | Accepted W beats | Full B responses | Actual PCIe chunks | Golden result |
| --- | ---: | ---: | ---: | --- |
| 4,092 bytes | 256 | 16 | 1 | Every byte; last STRB `0fff` |
| 4,100 bytes | 257 | 17 | 2 | Every byte; last STRB `000f` |
| 1,228,800 bytes | 76,800 | 4,800 | 300 | Every byte and every strobe |

The independent Python oracle checks every W byte, STRB, LAST, AW address and
length, response count and PCIe chunk request against host intent. Candidate
completion follows the final B in every aligned streaming case. Intermediate
chunk completion remains immediate and does not consume a retirement credit.

The frozen controller's actual `CHUNK_SIZE_MAX` is **4096**, despite 4092-byte
comments. An actual 4092-byte *intermediate* chunk cannot be requested through
its unchanged BAR1/controller interface. No chunk-size force or modified
controller is used to invent that coverage. The 4092-byte singleton tests the
partial final strobe; the 4100-byte and full payload tests exercise actual
intermediate chunks.

The suite intentionally preserves these failures:

- **Post-AW W stall:** legacy singleton prefetch pops the sole FIFO word and
  drops WVALID before WREADY returns. Frozen logic issues MSI and then times
  out in the W state. Candidate times out without MSI. A coordinated reset
  then permits an exact fresh transaction; no CPU-only cleanup is simulated.
- **Wrong BID:** a full B handshake with BID 1 cannot retire the FIFO's ID-zero
  transaction. Frozen logic still issues early MSI. Candidate remains pending
  without MSI, then recovers only through coordinated reset.
- **Pending final B reset:** the candidate produces no MSI for the abandoned
  transaction, clears both handshake domains, and cannot reuse that epoch's
  completion for the next command.
- **Host address +4:** the frozen controller requests two 4096-byte chunks for
  an 8192-byte transfer, crossing PCIe 4KB boundaries at `0x01000004` and
  `0x01001004`. Its computed `chunk_boundary_limit` is not used. The permissive
  fetch stub delivers those requests solely to expose/record the error; their
  successful golden byte comparison is **not** acceptance of legal PCIe DMA.

## Candidate API and contract

`artifacts/fpga_v8_pcie_fifo_retired.v` is the concrete uniquely named candidate.
Its parameters and external ports are byte-identical to the original except
for the module name. It can replace a `pcie_fifo` instantiation using the same
named ports and parameters. Do not compile the simulation `pango_pcie_top` stub
into a production project. `artifacts/candidate.diff` is the reviewable delta;
`retirement_insert.vh` is the narrowly scoped handshake source.

The core-clock credit toggles only in `S_BRESP_WAIT` when `beats_remain == 0`
and `BVALID && BREADY && BID == 0`. Two flops synchronize that persistent
toggle into PCIe clock. Final full-RX completion requires a new, unconsumed
credit and FIFO empty. The PCIe consumer updates its seen value only when
asserting final completion. Completion stays high through controller edge
detection; the credit cannot authorize the next command. Intermediate chunks
retain the original behavior and never consume credit. BRESP error still
retires, since the host cannot observe BRESP through this API.

The generated candidate preserves the entire original TX, AXI write engine,
AXI read engine and F2H suffix byte-for-byte. The runner asserts that invariant
and exact parameter/port equality. New handshake resets assert in both clock
domains and release through two local clock flops. Its OR-combined epoch reset
does **not** solve an independently reset legacy AXI transaction: the entire
PCIe/controller/FIFO and AXI fabric/endpoint must be coordinated. Actual frozen
`top.v:398` derives AXI reset from DDR initialization separately from PCIe
reset. A CPU restart or independent PCIe reset cannot be accepted as recovery.

After integration and separate platform validation, an H2F return driven by
candidate MSI can qualify as `DeliveryKnownUnknownResponse`. A register
readback must still distinguish accepted CLAIM/ACK from rejection. Before
this repair, an early readback could observe the old state while the earlier
write remains pending; it must not manufacture delivery-known status.

F2H is unchanged and only statically audited here. Frozen FIFO TX-done counts
words popped into the PCIe path, and controller completion derives from its
edge. Memory-write TLP attributes are zero (`ips2l_pcie_dma_mwr_tx_ctrl.v:208`,
relaxed ordering disabled), but this is not proof that the final posted write
has reached host memory before MSI. PCIe hard-IP transmission/ordering, MSI
grant, Linux driver ioctl behavior, root-complex coherence and hardware CDC
validation remain outside this regression.

## Evidence

`artifacts/results.json` contains machine-checked outcomes. Both implementations
have `mode_0.trace` through `mode_4.trace` and compiler/simulation logs. Input
hash invariance is checked after all tests. Two complete final runs produced
identical ten traces, results JSON and candidate RTL bytes;
`artifacts/replay_evidence.json` records their hashes and the successful scan
for external collisions of the candidate module name. No production source/IP/PDS edits,
PDS execution, SSH or board operation occurred.
