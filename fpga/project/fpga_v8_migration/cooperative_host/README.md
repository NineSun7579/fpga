# Cooperative host protocol candidate (C++17)

This directory contains a standalone header and local tests for the **candidate**
`fpga_v8_coop_control_axil` through `cooperative_endpoint`'s full AXI128 adapter.
It does not install FPGA support, reserve live memory, or provide a Linux driver.
No production host, viewer, board, RTL or PDS files are changed.

**Do not access M02 on the current loaded design.** The old NPU endpoint was
removed; the current top ties M02 responses with no BVALID/RVALID. An ID probe
there can hang. The working new endpoint and its reserved decode must be loaded
and verified externally before this helper is used. The reservation flag is an
explicit caller attestation, never a discovery or proof of installed support.
Parent full-top integration and loading are independent prerequisites.

## Wire contract

The authoritative map is `../cooperative_control/README.md` and the physical map
is `../cooperative_endpoint/register_map.json`. Each local 4-byte register occupies
a separate 16-byte physical slot:

```
physical = 0x40010000 + 4 * local_offset
HOST_BANK   local 0x10 -> physical 0x40010040
CLAIM       local 0x30 -> physical 0x400100c0
ACK_BANK    local 0x40 -> physical 0x40010100
ACK_SEQ     local 0x44 -> physical 0x40010110
ACK_GEN     local 0x48 -> physical 0x40010120
ACK_BELL    local 0x4c -> physical 0x40010130
```

`Transport::read16/write16` transfers exactly one aligned full AXI128 beat
(LEN=0, SIZE=4; WLAST=1). Words occupy little-endian bytes 0..3. Every helper write
zeros bytes 4..15; reads require those bytes to be zero. Full 16-byte write strobes
are permitted by the adapter. Never pack staged registers into one overlapping
physical write. `kRegisters` and `--map` expose all 27 register addresses.

| Transport status | Required meaning | Helper behavior |
| --- | --- | --- |
| `KnownOK` | Transaction retired; actual AXI response was OKAY | Still verify CLAIM/ACK with hardware readback |
| `KnownRejected` | Definite rejection; requested ownership side effect did not occur | CLAIM stays Idle/Busy; ACK stays Owned/Rejected for explicit retry |
| `DeliveryKnownUnknownResponse` | Complete ordered transaction retired, but response code unavailable | Verify bound descriptor/STATUS and staged words; never label delivery as AXI OKAY |
| `Uncertain` | Partial, timeout, lost completion, or possibly outstanding work | Faulted; no retry or ACK |

A legacy ioctl return is insufficient to classify `KnownOK` if it cannot report
BRESP. Only a backend with proven complete delivery and ordered reads may report
`DeliveryKnownUnknownResponse`. If completion itself is unknown, it must report
`Uncertain`. A read with unknown RRESP still needs a complete, stable 16-byte
copy, the loaded endpoint prerequisite, and the observations checked here.

## External reservations and driver obligations

All `RuntimeReservation` flags default false. The caller must explicitly confirm
and maintain every prerequisite, backed by its controller/lease manager and
driver configuration:

- Hold an external exclusive controller/client lock across CLAIM, COPY, staged
  ACK and readback. The backend must also serialize all processes and clients
  sharing the DMA command channel, mapped RX memory, and controller staging.
  The helper's mutex serializes complete methods on **one object only**. Multiple
  helpers or drivers cannot obtain global exclusivity from it.
- Exclusively reserve output banks `0x08000000` and `0x08200000` for this
  controller. The frame is exactly 640 x 640 x 3 = 1,228,800 tightly packed RGB888
  bytes. These payloads must not alias cam5 RAW banks `0x01800000`/`0x01a00000`,
  each 614,400 bytes plus a 16-byte tag. Addresses must be aligned, banks disjoint,
  and all ranges below physical 256-MiB DDR. This narrow candidate accepts these
  exact configured addresses; programmable runtime maps require external proof.
- Already reserve all read16/write16 transport scratch buffers and a separate,
  exclusive frame RX slot. Supply the actual established `rx_capacity`, the
  exclusive `frame_rx_offset`, and `control_rx_slots_end` covering every control
  scratch slot. The frame offset must be 16-byte aligned, at/after that end, and
  `offset + align16(1228800) <= capacity`. Offset `0x400000` is only an example;
  the fake's 8-MiB capacity says nothing about the real driver. A historical
  4-MiB camera mapping cannot contain a frame starting at `0x400000`.
- Confirm a coordinated common reset and supply a fresh **nonzero**
  `Config::expected_generation`. The helper never chooses an epoch from time,
  sequence, static memory, or a repeated process-local counter. The external
  manager must exclude old ACKs across reset/rollover and prevent identity reuse.
- Certify one identity domain: cam5 (`camera == 4`, zero based), with nonzero
  unique source sequences within the generation. Multi-camera sequence collisions
  are unsafe because the ACK key lacks camera/token. The external source manager
  must pin complete RAW sources during preprocessing; current camera tags/ACKs
  alone are not source leases. The returned nonzero 64-bit token is opaque and
  is not required to equal `(generation << 32) | sequence`.

The header implements **no** allocation of driver buffers, open, ioctl, mmap,
device writes, sleeps, bus cancellation or reset. `copy_ddr_blocking` uses the
already reserved transport RX slot and copies into a caller-owned vector of
exactly 1,228,800 bytes. Its `KnownOK` + exact byte count guarantees **all DMA
transactions have retired and the complete copied bytes are stable**. No pointer
to the vector may remain in the backend after any return or exception. Partial
DMA activity must be quarantined in the external DMA mapping pending external
drain/reset, so returning or destroying an error vector cannot cause a dangling
DMA destination. Never infer these guarantees from uninspected driver claims.

## API and state flow

Include only `coop_host_protocol.hpp`; namespace `coop_host` needs C++17 and the
standard library, with no Qt, OpenCV or RKNN headers/libraries.

```cpp
// transport, configuration, reservation, and storage are supplied by the caller.
// Allocate storage BEFORE CLAIM, while allocation failure cannot strand a lease.
std::vector<std::uint8_t> storage(coop_host::kFrameBytes);
coop_host::Candidate host(transport, externally_validated_config,
                          externally_confirmed_reservation);
auto claimed = host.claim_one_poll();
if (claimed == coop_host::Result::OK) {
    auto copied = host.copy_owned(std::move(storage));
    if (copied.result == coop_host::Result::OK) {
        auto frame = std::move(*copied.frame); // Frame belongs entirely to caller.
        auto ack = host.acknowledge();        // Explicit release after complete copy.
        // Keep/use frame.bytes independently of ack; retain snapshot on errors.
        // A complete frame survives ACK, fast bank reuse, and ACK readback failure.
    }
}
```

`claim_one_poll()` does one finite poll without waiting: COOP ID `0x434f4f50`,
version `0x00010000`, no existing STATUS host claim, then READY_HINT. A definite
CLAIM rejection returns Busy without consuming stale metadata. On success it
confirms HOST_BANK at local `0x10` and STATUS bit 3, then reads the bound descriptor
`{bank,sequence,generation,length,address,camera,source_bank,source_address,token}`.
It checks expected generation, nonzero sequence/token, both banks <=1, camera 4,
exact length/addresses and physical ranges. It rereads bank/sequence/generation
and STATUS before entering Claimed to reject reset-mixed metadata.

`copy_owned(vector)` accepts only Claimed, verifies the lease before and after
DMA, and returns `CopyResult.frame` with independent bytes. Full success enters
Owned. On DMA failure it returns preserved partial bytes with `complete=false`,
enters Faulted, and never ACKs. A completed copy followed by a lease-read fault
remains `complete=true` even though the helper is Faulted. An incorrectly sized
caller vector returns InvalidBuffer, retains Claimed, and performs no DMA.

`acknowledge()` requires Owned. It verifies the held key, writes bank/sequence/
generation in three individual beats, reads each staged value, verifies the
lease again, and rings exactly one doorbell. A definite rejection preserves
Owned and permits a later **explicit** call to restage/retry. Uncertain delivery
permanently faults, with no second bell. Even KnownOK requires HOST_BANK to read
`0xffffffff` and STATUS host claim to clear before entering Idle. The former bank
may already be WRITING/READY again; FREE is not required. With delivery-only
status, an unchanged bound key after the bell proves rejection for explicit retry.

The caller controls bounded polling and scheduling. It may release FPGA ownership
before RKNN once bytes are fully owned. Externally, a complete vector can back
`cv::Mat(640,640,CV_8UC3,frame.bytes.data())`; preserve its lifetime and submit
tight UINT8 NHWC RGB with `pass_through=0` through the existing pipeline. No DMA
mapping pointer is exposed. This directory does not implement that integration.

## Failures and diagnostics

Idle has no local claim. Claimed has a verified FPGA lease without a complete
copy. Owned has a completed independent copy and a held FPGA lease. Faulted
means ownership or I/O is unsafe to advance. Faulted is terminal for this helper:
every subsequent operation returns Faulted without I/O. Invalid descriptors,
uncertain reads/writes, transport exceptions, truncated/error DMA, changed lease
keys, or inconsistent post-ACK observations do not generate cleanup traffic.

`snapshot()` reports the state, first fault, requested bank, possible claim,
partial/validated held descriptor, and stable-copy completion. It has no device
effects. Keep returned complete frames for diagnostics/inference if appropriate.
There is no destructor ACK, fake source release, local reset, or catch-and-release
after DMA failure. A possibly freed ACK can still yield Faulted on failed readback;
its previously owned vector is preserved. Reconstructing a helper is not recovery.
Drain outstanding bus/DMA work or perform an externally coordinated common reset
of affected controller, bridge, transactions and source lease manager, then use a
fresh generation/reservation. Old host operations must not survive that reset.

## Local verification

```
python run_coop_host_tests.py
```

The runner prefers available g++ (`-std=c++17 -O2 -pthread -Wall -Wextra -Werror
-pedantic`); on this Windows workspace it uses the installed MSVC C++17 compiler
with `/O2 /EHsc /W4 /WX`. Set `COOP_HOST_CXX` to a g++ path, or
`COOP_HOST_VCVARS` for another MSVC installation. `MODELSIM_BIN` selects ModelSim.
All generated artifacts remain under this directory.

The independent fake models a two-bank completion FIFO, frozen producer records,
full staged ACK keys and mutable RX/DDR storage. Tests cover ownership, byte
stability after immediate ACK/reuse, external reservation/bounds failures with
zero I/O, stale or mixed descriptors, partial/error DMA, missing responses,
explicit rejected-ACK retry, uncertain writes without retry, descriptor freeze
while another bank completes, and concurrent method serialization. All control
writes are inspected for exact 16-byte size, physical stride and zero upper bytes.

The runner reads the sibling endpoint JSON once, compares every register address,
and replays a clean C++ fixture through its independent Python model and existing
ModelSim public-transaction testbench in a **local** work directory. It neither
modifies sibling artifacts nor waits for parent integration. Absent ModelSim is
reported as unavailable; it is never presented as a pass. SHA256 source/dependency
pins, compiler identity, exact commands, stdout, counters and artifact hashes are
recorded in `artifacts/results.json`. See `VALIDATION.md` for the recorded run.
The sibling harness replays the addresses and low words using its seeded upper-lane
stimulus; the C++ fake separately asserts zero upper bytes on every helper write.

These are host contract tests and isolated endpoint/controller RTL tests. They
do not test physical DDR, real PCIe DMA, driver allocation/completion guarantees,
camera stability, loaded bitstream support, full-top routing or live RKNN parity.
