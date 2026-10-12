# Cooperative buffer ownership candidate

`fpga_v8_coop_control_axil.v` is an isolated, ASCII Verilog-2001 candidate for
a 32-bit M02 AXI-Lite control endpoint on `core_clk`. It connects the command
and status ports of the existing `cooperative_axi/fpga_v8_raw_frame_axi.v`.
It reserves two output banks and manages host transactions independently of
camera capture. No production RTL, PDS registration, DDR top, board design,
or capture manager is supplied or changed here.

## Input ownership is an external prerequisite

The existing camera/FIR images do not prove that any current DDR bank is a
stable RAW frame. This controller makes no autonomous capture-stability claim.
The external capture/lease manager must certify all of the following before
asserting `input_valid` with `input_raw_valid=1`:

- The descriptor refers to a complete, unfiltered RGB565 RAW frame with the
  format, dimensions, alignment and bounds expected by the bridge.
- The caller already owns a lease for that source bank and has marked it
  leased. Camera capture, FIR processing, DMA and other writers must leave
  that bank unchanged until the matching source-release handshake.
- Source and destination memory regions do not alias. Both configured output
  regions are exclusively owned by this controller and fit the bridge output.
- The identity rules in the generation section below hold across every
  source camera, bank, frame, reset and descriptor retry.

All descriptor fields must stay stable while `input_valid && !input_ready`.
The input is not an AXI-Lite software start register: it is a hardware lease
handoff interface supplied by an external manager.

`input_ready` requires an idle controller, an idle bridge, a FREE output bank,
and no pending source release. When both output banks are owned, it stays low:
the caller retains the descriptor/lease and decides whether to wait or drop a
new capture. There is no implicit eviction or overwrite policy.

On `input_valid && input_ready && input_raw_valid`, the combinational
`input_claim` handshake transfers responsibility for the already-held lease
to the controller. A separate claim-ready signal is unnecessary because the
manager controls `input_valid` and participates in this very handshake. The
chosen FREE output bank immediately becomes WRITING. `input_lease_token[63:0]`
is opaque; camera ID is three bits, camera bank ID is one bit.

On `input_valid && input_ready && !input_raw_valid`, `input_reject` consumes
the invalid descriptor and increments the RAW-rejection counter. It does not
claim the source lease, reserve a bank, start a bridge command, or produce a
source release. The caller retains any lease it already held.

## Bridge and source release

Connect ports directly on the common clock:

| Controller | `fpga_v8_raw_frame_axi` |
| --- | --- |
| `core_clk`, `rst_n` | `clk`, `rst_n` |
| `cmd_valid`, `cmd_ready` | `cmd_valid`, `cmd_ready` |
| `cmd_src_addr`, `cmd_dst_addr`, `cmd_frame_id` | same-named ports |
| `bridge_busy`, `bridge_done`, `bridge_error` | `busy`, `done`, `error` |
| `bridge_cmd_error` | `cmd_error` |

Command fields are registered at descriptor acceptance and held stable until
`cmd_valid && cmd_ready`. `cmd_frame_id` carries the caller's 32-bit source
sequence; generation and lease token are tracked separately. `busy` is set
when the descriptor is accepted, including time waiting for command readiness.
No second input is accepted while the operation or its source release remains
pending.

An error observed after command acceptance is latched. An in-flight error does
not cancel the bridge: WRITING and the input lease remain owned until
`bridge_done`. The existing bridge's `done` must continue to mean that all
reads, writes, final B response and pipeline data have drained. Successful
completion publishes READY; failed completion frees that output bank without
publishing a descriptor. Both create `src_release_valid` with the exact source
address, sequence, generation, camera, camera bank and lease token accepted.
The release and all metadata remain stable until `src_release_ready`.

The existing bridge rejects an invalid command with `cmd_error` and never
asserts `done` for it. This no-launch rejection is handled separately: latch
the rejection and retire only when `bridge_busy=0`. Connect `cmd_error` as
listed; omitting it would strand a rejected lease. A premature `done` before
command acceptance is ignored. There is no standalone cancellation port.

Host ACKs affect only output ownership. They neither certify RAW input nor
release a camera lease.

## Output and host ownership

The default output addresses are `0x08000000` and `0x08200000`; configure them
with `OUTPUT_BANK0_ADDR` and `OUTPUT_BANK1_ADDR`. `OUTPUT_LENGTH` defaults to
1,228,800 bytes (640 x 640 x 3 RGB888), and must match the connected bridge
geometry. Parameters are trusted integration inputs, not runtime allocations.

State encoding, also exposed through `bank0_state` and `bank1_state`:

| State | Value | Transition |
| --- | --- | --- |
| FREE | 0 | Certified lease acceptance reserves it as WRITING |
| WRITING | 1 | Drained success becomes READY; drained failure becomes FREE |
| READY | 2 | Successful oldest-ready CLAIM becomes HOST_READING |
| HOST_READING | 3 | Exact bank/sequence/generation ACK becomes FREE |

Only one host claim exists at a time. READY age is completion order, not
numeric sequence/generation order. With two banks, the oldest READY bank
is always selected; a request for the other bank fails. A bank being read by
the host is never selected for bridge output. The bridge can produce the
other bank's READY result during a host read.

The host transaction is:

1. Read `0x0c` for the oldest-ready bank hint (`0xffffffff` means none).
2. Write that bank in bit 0 to CLAIM at `0x30` and wait for its AXI-Lite B.
   Check OKAY; SLVERR leaves all ownership unchanged.
3. Read the descriptor at `0x10..0x38`. Every word refers to this one bound
   HOST_READING bank and stays unchanged until its successful ACK or reset.
4. Finish all host memory reads and DMA work for the returned output range.
5. Write the full bank, source sequence, and generation to `0x40/0x44/0x48`.
   Write bit 0 of `0x4c` and wait for B. Only OKAY frees the claimed bank.

ACK must match all three staged words, the current host claim and
HOST_READING state. Wrong bank, wrong sequence, stale generation, duplicate
ACK, ACK without CLAIM, and ACK of a READY bank return SLVERR and increment
the rejection counter. ACK bank is checked as a full 32-bit word, so bits
31:1 must be zero. A failed ACK preserves the bound descriptor. Host software
must serialize the staged ACK and doorbell writes; there is one host context.

The `0x0c` hint and STATUS are live snapshots and may change between reads.
Descriptor registers return empty values until CLAIM succeeds; they do not
expose an unclaimed READY descriptor that could switch between word reads.
An R already accepted before ACK/reset is an ordinary AXI-Lite snapshot;
software must complete its descriptor reads before releasing that bank.

## Register map

Addresses are **32-bit local M02 byte offsets**, exactly decoded. The parent
integration must translate any global window base to these local offsets.
Unaligned, unmapped or aliased addresses return SLVERR. Unmapped reads return
zero. Read-only writes also return SLVERR.

| Offset | Access | Meaning |
| --- | --- | --- |
| `0x00` | RO | Device ID, default `0x434f4f50` (COOP), parameter `DEVICE_ID` |
| `0x04` | RO | STATUS, bits defined below |
| `0x08` | RO | Version, default `0x00010000`, parameter `VERSION` |
| `0x0c` | RO | Oldest READY bank hint, otherwise `0xffffffff` |
| `0x10` | RO | Bound host bank, otherwise `0xffffffff` |
| `0x14` | RO | Bound source sequence |
| `0x18` | RO | Bound generation |
| `0x1c` | RO | Bound output byte length |
| `0x20` | RO | Bound output address |
| `0x24` | RO | Bound source camera ID, bits 2:0 |
| `0x28` | RO | Bound source camera bank ID, bit 0 |
| `0x2c` | RO | Bound source address |
| `0x30` | WO/RO | CLAIM bank bit 0; read returns bound bank or `0xffffffff` |
| `0x34` | RO | Bound lease token bits 31:0 |
| `0x38` | RO | Bound lease token bits 63:32 |
| `0x40` | RW | Staged ACK bank |
| `0x44` | RW | Staged ACK source sequence |
| `0x48` | RW | Staged ACK generation |
| `0x4c` | WO/RO | ACK doorbell bit 0; read returns zero |
| `0x50` | RO | Rejected ACK count |
| `0x54` | RO | Rejected CLAIM count |
| `0x58` | RO | Rejected uncertified RAW descriptor count |
| `0x5c` | RO | Failed bridge operation/command count |
| `0x60` | RO | Successfully completed bridge operation count |
| `0x64` | RO | Accepted source-release handshake count |
| `0x68` | RO | Accepted certified descriptor count |
| `0x6c` | RO | Last error: 0 none, 1 RAW reject, 2 bridge failure, 3 CLAIM reject, 4 ACK reject |

Unbound descriptor metadata/length/address words return zero. STATUS:

| Bits | Meaning |
| --- | --- |
| 0 | Controller operation active (queued command included) |
| 1 | Buffered command valid |
| 2 | At least one READY bank |
| 3 | Bound host claim valid |
| 4 | Source release pending |
| 5 | Bridge busy input |
| 6 | Last error is nonzero; sticky until common reset |
| 9:7 | Reserved zero |
| 11:10 | Bank 0 state |
| 13:12 | Bank 1 state |
| 31:14 | Reserved zero |

ACK staging registers apply each WSTRB byte independently. CLAIM executes
when WSTRB[0] is set, including bank 0 data; higher bytes/bits are ignored.
Doorbell executes only when WSTRB[0] and WDATA[0] are both set. A zero-strobe
write to a writable register is an OKAY no-op. Error counters and last error
have no software clear; common reset clears them, and counters wrap at 32 bits.

AW and W are captured independently in either order. Each has one holding
slot, and one B can be outstanding; the endpoint backpressures subsequent
writes while B is pending. A master holding consecutive AW/W through that
backpressure loses no beat. There is a throughput bubble after B consumption.
AR is accepted only when the R slot is available (including simultaneous R
consumption). Accepted AR produces a captured data/response pair from the
current address, held unchanged while RREADY is low. Back-to-back accepted
AR requests can replace a consumed R every cycle. AXI-Lite PROT is accepted
and ignored; there are no AXI IDs or bursts on this endpoint.

Same-clock-edge reads/CLAIM observe state before that edge's completion.
A just-completed bank is claimable on the following cycle. CLAIM or ACK of
one bank may commit on the same edge that the other bank completes.

## Generation, identity and reset contract

The controller passes through source sequence/generation without inventing
camera stability or allocating an epoch. For stale ACK rejection to hold, the
external manager must guarantee that an output bank's `(sequence,generation)`
identity is never reused while any old host ACK can still arrive. A globally
unique sequence per generation across cameras is a straightforward policy;
independent per-camera sequences that collide are insufficient because the
ACK key does not include camera ID or the opaque input token.

Reset must be common to controller, bridge and affected bus/interconnect
transactions. It invalidates all output descriptors, host claims, buffered
commands, staged ACKs and pending source releases. The external lease manager
must recover/reset its leases as part of that coordinated operation; reset
does not emit synthetic source-release handshakes. Resetting only this
controller while the bridge can continue writing would violate ownership.
After reset, the manager must choose a fresh generation before accepting new
leases. Tests reuse the same bank and sequence with a new generation and
verify that the old-generation ACK fails.

Sequence wrap and generation wrap/reuse are **unresolved external rollover
policy**, not a hardware guarantee. Rotate to a never-reused generation before
sequence identity reuse. Generation exhaustion requires a coordinated host
and capture-manager procedure that excludes all old acknowledgements. The
numeric-wrap test verifies FIFO ordering only; it does not certify identity
reuse as safe. The RTL does not detect duplicate identities, dishonest RAW
certification, a forged lease token or source writers ignoring a lease.

## Verification

Run from this directory:

```powershell
python run_tests.py
```

ModelSim defaults to `C:\modeltech64_10.6e\win64`; override `MODELSIM_BIN` if
needed. Compilation uses `vlog` without `-sv`. The runner writes only beneath
this directory. It generates input traces, runs ModelSim, and compares every
cycle's 311 public output bits with a Python two-bank lease scoreboard. The
scoreboard maintains a READY FIFO and immutable lease records, and does not
read DUT state or hierarchy. Explicit assertions also check public register
values, bank ownership and exact ACK outcomes.

The bridge is represented by its command/status contract in this suite;
final B/drain delays are represented by delaying `bridge_done`. Actual
AXI bridge/datapath verification remains in `cooperative_axi`. No camera,
DDR fabric, real host DMA, CDC, hardware timing or production routing is
validated by these controller tests.

`REPORT.md` summarizes the verified candidate. `artifacts/results.json`
records compiler/simulator commands, counters, markers and trace hashes.
Each artifact directory contains vectors, expected/actual trace and logs.
