# Cooperative AXI128 endpoint candidate

This directory supplies an isolated full AXI4 128-bit control endpoint and a
ModelSim regression against the **unchanged** 32-bit
`../cooperative_control/fpga_v8_coop_control_axil.v`. The endpoint is ASCII
Verilog-2001. It is not registered in a PDS project or connected to production
RTL. The default cooperative core's direct AXI-Lite interface remains intact.

The existing PCIe H2F/F2H transport uses 16-byte DMA transactions. Splitting
one such transfer into four neighboring local writes would access read-only
registers and corrupt CLAIM/ACK semantics. This endpoint maps one physical
16-byte slot to exactly one local 32-bit register.

## Physical register map and integration prerequisite

`register_map.json` is the machine-readable host map. The proposed global
window is **M02 `0x40010000..0x40010fff`**, end-exclusive `0x40011000`.
The parent must first recover the existing NPU decode, then explicitly reserve
this exact window with no overlap before accepting the global address map.
No reservation or production decode change is made by this candidate.
Pass the global addresses unchanged into this endpoint. Preserve all seven
AXI ID bits, including crossbar routing bits `010`; do not insert a general
128-to-32 AXI-Lite splitting adapter ahead of it.

```
physical_address = BASE_ADDR + 4 * local_32bit_byte_offset
local_offset     = (physical_address - BASE_ADDR) >> 2
```

Every local offset divisible by four has a 16-byte-aligned physical slot.
The range covers local offsets `0x000..0x3fc`; unused local offsets are left
for the real controller to reject with SLVERR. The endpoint does not know
which registers are implemented or which are writable.

| Register | Local offset | Global physical address |
| --- | --- | --- |
| DEVICE_ID | `0x00` | `0x40010000` |
| STATUS | `0x04` | `0x40010010` |
| READY_HINT | `0x0c` | `0x40010030` |
| Bound descriptor, 11 words | `0x10..0x38` | `0x40010040..0x400100e0`, stride 16 |
| CLAIM | `0x30` | `0x400100c0` |
| ACK bank | `0x40` | `0x40010100` |
| ACK source sequence | `0x44` | `0x40010110` |
| ACK generation | `0x48` | `0x40010120` |
| ACK doorbell | `0x4c` | `0x40010130` |
| Rejected ACK count | `0x50` | `0x40010140` |
| Rejected CLAIM count | `0x54` | `0x40010150` |
| Last error | `0x6c` | `0x400101b0` |

For each control access, submit one 16-byte DMA beat: `LEN=0`, `SIZE=4`,
`BURST=INCR(1)` or `FIXED(0)`. Encode the value little-endian in the first
four bytes. Writes forward only `WDATA[31:0]` and `WSTRB[3:0]`; the upper
96 bits and 12 strobes are ignored even when all 16 strobes are asserted.
Reads return the low 32-bit register value and 96 zero bits. The controller
still implements byte strobes in that one low word.

## Transaction behavior

AW and W are independent. One W holding slot accepts the first beat before
AW. AW captures the full ID, address, LEN, SIZE, BURST, LOCK and PROT;
subsequent input changes cannot change that request. No controller AW or W
is presented until both full AW and the singleton W with valid WLAST have
been captured and validated. The local AW and W handshakes then proceed
independently through arbitrary backpressure, in either order. The endpoint
waits for the actual local B, propagates its BRESP and original full ID, and
holds them until the full B is consumed. No next AW or W is accepted while
that full write is pending. LOCK is ignored and no EXOKAY is synthesized;
PROT is forwarded, and CACHE/QOS/REGION are ignored.

Unsupported LEN/SIZE/BURST, misalignment, an out-of-window beat or a bad
singleton WLAST causes SLVERR with no local write. Rejected writes drain
exactly `AWLEN+1` W handshakes before producing B. An early or missing WLAST
is remembered but never changes that count. Nine-bit counters represent
256 beats without wrapping. A pending following AW/W cannot enter the
rejected transaction or replace its metadata. Sixteen-byte alignment and
the full-beat window check also prohibit a valid 4 KiB crossing.

AR snapshots its ID, address, PROT and validation/count information. A valid
singleton launches one local read and captures the actual local data/RRESP.
The full R is a snapshot held unchanged under RREADY backpressure, with
RLAST=1. Unsupported reads emit exactly `ARLEN+1` zero-data SLVERR beats,
all with the original ID and RLAST only on the final beat, and emit no local
AR. A following AR remains blocked through final R consumption. Read and
write paths have one pending request each and can operate concurrently
against the real controller.

There is no local cancellation or timeout. A missing W beat, local response,
or downstream readiness can stall indefinitely. Use a common clock and
active-low reset for endpoint, controller, bridge and affected upstream
bus/interconnect transactions. The external lease manager and host must
participate in reset recovery; an endpoint-only reset cannot cancel a live
controller side effect or a bridge memory write. Reset discards held bus
transactions and controller ownership together; it emits no synthetic
lease release. Use a fresh generation after coordinated reset.

Static configuration requires positive ID_WIDTH, a 16-byte-aligned BASE_ADDR,
a positive WINDOW_BYTES divisible by 16, and a 33-bit end calculation no
larger than `0x100000000`. Invalid configurations reject all transactions.
The runner validates the published default JSON addresses before simulation;
the parent must validate any changed parameters and corresponding decode/map.

## Host confirmation and external RAW leases

The host reads READY_HINT, writes CLAIM, verifies its outcome, reads all 11
bound descriptor words, finishes output-data DMA, stages bank/sequence/
generation in three separate 16-byte writes, then writes the ACK doorbell.
All descriptor words refer to that one host claim while the other output
bank may complete. ACK only releases the output bank with an exact matching
key; the source-camera lease is released by the controller's separate
source-release handshake following bridge completion.

The current host driver may not propagate AXI BRESP through the DMA ioctl.
Treat ioctl success as transport completion, not proof that CLAIM or ACK
succeeded. Until BRESP propagation is proven, the serialized host client must
read controller status and rejection counters. After CLAIM, verify STATUS
bit 3, the expected bound bank and descriptor, and no increase in the CLAIM
rejection count. After ACK, verify STATUS bit 3 is clear, HOST_BANK is
`0xffffffff`, and the ACK rejection count did not increase. A freed bank may
already be reserved by a new producer, so its current bank state need not
still be FREE when software checks. A rejected ACK leaves the bound bank and
metadata intact, increments rejected-ACK count, and sets LAST_ERROR=4.
Serialize all staged ACK and doorbell accesses; there is one host context.

The external manager must already own and certify a complete, correctly
aligned and bounded RAW RGB565 source frame matching the bridge geometry.
It must exclude camera/FIR/DMA writes until the matching source release,
reserve nonoverlapping output regions, and prevent sequence/generation reuse
while stale host acknowledgements can arrive. Input descriptors transfer an
existing lease; neither this endpoint nor the controller claims that a camera
buffer is stable. Tests supply certified descriptors independently and model
bridge completion. They do not supply or certify actual camera/DDR frames.

## Reproduction and evidence

Run `python run_tests.py` from this directory. ModelSim defaults to
`C:\modeltech64_10.6e\win64`; set `MODELSIM_BIN` to override it. Every generated
file is beneath `artifacts/`. The endpoint and existing controller compile
without `-sv`; only the testbench uses SystemVerilog. No PDS, SSH, production
source, IP, DDR-adapter or capture-lease files are changed or invoked.

The independent Python oracle generates host/producer intent and expected
bus/register/bank outcomes before simulation. It uses immutable producer
records and a READY FIFO, never DUT hierarchy or emitted DUT metadata.
Every accepted full/local transaction, source command/release and final bank
state is compared by operation and channel. The stimulus recipe alone
generates the pseudo-random upper 96 write bits. The SV monitor checks X/Z
on all public bus/controller outputs even while VALID is low and during
reset, response/address/data stability under stalls, admission boundaries,
and that a local side effect cannot precede validated AW/W/WLAST.

See `REPORT.md` and `artifacts/results.json` for measured coverage, commands
and full-file hashes. This is endpoint/controller candidate evidence only.
Global decode, actual PCIe DMA/ioctl errors, DDR adapter/datapath, exact frame
contents, camera leases, CDC, hardware synthesis/timing and whole cooperative
acceptance remain outside this regression.
