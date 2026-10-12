# Isolated owned RAW host helper

`capture_host_protocol.hpp` provides pure C++17 `capture_host::CandidateRAW`.
It includes the **unchanged** cooperative host header and reuses its exact
`Transport`, `Beat`, `IoStatus` and `DmaResult` types. It implements explicit
fresh-generation ARM, a host input-frame lease CLAIM, an owned RAW payload
copy, and exact RAW ACK. It does not provide a device/driver backend, allocate
RX mappings, change a loaded image, or reset hardware. `host_api.json` records
the integration API; the authoritative register map remains the preserved
`../capture_endpoint/register_map.json`.

All new files and generated outputs stay in this directory. Previous host,
capture-control, router, AXI128 endpoint, tests and artifacts are audited
before/after without modification or rerunning their suites. No PDS, IP,
production source, SSH, driver or physical board action is performed.

## Prerequisites before any I/O

The constructor checks every `RuntimeReservation` flag, which defaults false.
The parent/backend must establish and maintain the facts for the helper's
whole lifetime: exclusive controller client, shared complete-operation
coordinator, authoritative backend transport mutex, fixed validated source/
output DDR layout, disjoint exclusive RAW/output RX slots, reserved control
buffers, functional capture endpoint with reserved global decode, coordinated
reset/lease recovery, validated selected unfiltered RGB565 stream and one
camera identity domain. These flags attest external work; they allocate or
discover nothing. The currently loaded M02 image is not authorized by this
helper and may tie that endpoint off. Use only the functional new candidate
after parent deployment/decode/stream validation.

`Config` fixes source bases `0x01800000/0x01a00000`, output bases
`0x08000000/0x08200000`, integration camera ID 4, 640x480 RGB565 and 614400
payload bytes. This identity does not assert a physical camera format or a
camera-to-50K path. The parent must validate the incoming stream, actual
DDR capacity and source/output/other-client layout. `ddr_limit` must agree
with that validation and manager bounds; it cannot exceed `0x10000000`.
Source regions include their separate 16-byte tag in bounds checks. The
helper exposes no software changes to geometry or source/output addresses.

The RX layout must provide the actual externally measured `rx_capacity`,
the aligned end of **all** `read16` scratch slots, an exclusive aligned RAW
slot and a separate exclusive aligned output slot. Both frame slots start
after scratch, cannot overlap, and must fit capacity using checked bounds.
The RAW slot reserves either **614400** payload bytes or **614416** bytes
including an optional tag reservation. Output reserves **1228800** bytes.
`copy_owned` always requests exactly 614400 RAW payload bytes; it does not
read the tag, borrow scratch for it, or widen a transfer. The real manager's
successful publication already depends on good tag retirement. A future
tag reader must provide its own correctly sized transfer and ownership
contract. Existing unrelated 4 MiB driver slots/camera layouts are not
proof of a valid combined RX reservation.

The local test reservation is scratch `[0,4096)`, RAW
`[4096,618496)`, output `[618496,1847296)`. It supplies capacity 1847296
explicitly. Reserving the optional tag moves output start to 618512 and
requires capacity 1847312. These are fake-test offsets, not a live binding.
Parent output `coop_host::Config.frame_rx_offset` must equal the RAW config's
`output_rx_offset`; capacities, scratch range, banks and generation must
agree. The RAW constructor cannot inspect another helper's private config.
The existing output helper has a fixed expected generation: a later epoch
requires a new matching output helper only after the external quiescent
epoch barrier. Reconstructing it is not uncertain-transfer recovery.

## Shared operation and backend serialization

The constructor takes a **caller-supplied `std::mutex&`**. Every RAW public
operation, including snapshots, acquires it across all register reads,
metadata writes, readbacks and blocking DMA. All callers using the same
hardware/session must use that same coordinator; independent object mutexes
cannot serialize RAW and output transactions. An exclusive process/session
ownership policy must also exclude other programs and kernel clients.

The unchanged cooperative helper acquires only its own internal mutex.
Wrap its complete operation using `capture_host::with_exclusive_io`:

```cpp
std::mutex operation_coordinator; // One shared instance for this hardware session.
capture_host::CandidateRAW raw(transport, raw_config, proven_reservations,
                               operation_coordinator);
coop_host::Candidate output(transport, output_config, proven_output_reservations);

const auto armed = raw.arm(externally_authorized_arm_request);
// Check Result::OK before polling; schedule bounded retries in the caller.
const auto raw_claim = raw.claim_one_poll();
const auto output_claim = capture_host::with_exclusive_io(
    operation_coordinator, [&] { return output.claim_one_poll(); });
```

Apply the wrapper to every output copy/ACK/snapshot and any other control
user. **Do not wrap RAW calls**: they already take the nonrecursive mutex;
wrapping them would deadlock. Keep the coordinator and transport alive
longer than both helpers. The lock order is coordinator, then existing
output-helper mutex if applicable, then backend transport mutex. Backend
callbacks must not reenter a helper or acquire those locks in reverse.

The backend mutex remains authoritative for actual transport mappings,
read16 scratch, DMA submissions/retirement and quarantined pending activity.
The coordinator provides whole-protocol-operation exclusion; a backend
that locks each low-level call alone cannot prevent interleaved metadata.
Disjoint RAW/output RX slots remain necessary even with serialization,
especially after uncertain or pending DMA. The caller may schedule RAW and
output work from different threads; their complete helper operations serialize.
The helper promises no parallel DMA execution.

## Explicit ARM

`ArmRequest` requires a nonzero generation, an attestation that an external
persistent allocator allocated that fresh value, and an attestation that
**all host, cooperative and DMA work is quiescent**. These authorizations
default false. There is no auto-generation, constructor I/O, auto-ARM,
global-reset simulation, polling loop or sleep. The same generation is
rejected before staging; the manager also rejects zero/current epochs but
cannot remember older epochs through reset. Allocation persistence,
rollover/exhaustion, common reset and old-ACK exclusion remain external.

ARM reads CAPL ID/version/status, bank states, accepted generation and
accept/reject counts. It returns Busy without writing if any host descriptor,
pending operation, manager bank or engine work prevents config readiness.
It does not wait behind leases that the same client must release. It stages
generation at local `0x10c` (**physical `0x40010430`**), verifies staging,
then writes the ARM doorbell at `0x110` (**`0x40010440`**). Acceptance must
be observed as the new generation at `0x170`, armed/config_ok STATUS, and
an increment of accepted-config count `0x174` without a rejection increase.
This applies even when transport reports KnownOK; hardware's real registered
acknowledgement is reflected in the returned B and readback counters.

KnownRejected on ARM returns Busy without guessing success. For a fully
retired ordered transfer with unknown BRESP, changed counters and unchanged
old generation can prove rejection; otherwise the helper faults. There is
one attempt per call and no automatic doorbell repeat. After successful ARM
the helper remains Idle with its accepted generation, ready to poll sources.
An already-owned RAW lease blocks ARM. Parent quiescence attestation must
also exclude output/helper ownership that this object cannot inspect.

## CLAIM, coherent descriptor and owned bytes

The actual STATUS at `0x104` supplies **bit 4 manager host_valid** and
**bit 10 offered bank**. `0x160` is publication count, not a bank hint;
`0x178` is accepted-release count. RAW CLAIM at `0x114` receives the selected
full 32-bit bank word. The helper checks accepted-claim and rejected-claim
counters together with bound-bank/STATUS readback. A definite rejection
returns Busy. A retired unknown response requires ordered observations that
prove either exact acceptance or rejection; ambiguous observations fault.

After acceptance it snapshots `0x118..0x134`: bank, sequence, generation,
length, address, camera and both token words. Sequence must be nonzero,
generation must match the helper's confirmed epoch, length/address/camera
must match fixed config, and the **full 64-bit token** must match this actual
manager's `{generation,sequence}` contract. The cooperative helper treats
its forwarded token as opaque; this RAW helper checks the concrete manager
contract it is paired with. It rereads all descriptor fields, both token
words, status and accepted generation to confirm coherence. A final valid
offer remains claimable after the manager disarms at sequence exhaustion.
Protocol faults or generation changes fault the client.

`copy_owned` accepts a caller vector of **exactly 614400 bytes**. It verifies
the held identity before and after `Transport::copy_ddr_blocking`, using the
reserved RAW RX offset. Only KnownOK with exact byte count and unchanged
vector size certifies all DMA retired and a complete stable copy. The
returned vector owns its storage; it never aliases the transport RX mapping.
A complete copy stays available even if the post-copy lease readback fails.
Partial/error copies remain available diagnostically with `complete=false`
and must not feed processing. A backend must never retain the vector pointer,
including on an exception/error; quarantine outstanding DMA in its externally
reserved mapping, as required by the immutable Transport contract.

No ACK occurs in copying or destruction. After a successful copy the state
is Owned; the host can explicitly ACK and retain the owned bytes even when
the source bank is later overwritten. The source bank itself is freed only
after **both** host and cooperative consumers have successfully released it.
Host release alone may leave it HELD. Output-bank release is a separate
operation on the cooperative helper. Legacy boolean notifications do not
release a source lease.

## Six-word RAW ACK and uncertainty

`acknowledge()` verifies the bound lease, stages all six complete words at
`0x138..0x14c` (bank, sequence, generation, token low/high, camera), verifies
every staging readback, verifies the lease again, then rings `0x150`.
Readback must show no bound bank/STATUS host bit, an incremented
accepted-release count `0x178`, and unchanged bad-ACK count `0x158`.
The helper does not require the bank still be FREE: cooperative work or
new capture may already affect its live state.

KnownRejected leaves the valid Owned lease for an **explicit caller retry**.
A retired unknown response can also prove rejection when the exact bound
identity survives, release count is unchanged and bad-ACK count increments.
Uncertain control/DMA, exceptions, incomplete DMA, changed metadata, failed
staging checks or ambiguous post-doorbell observations enter permanent
Faulted state. No subsequent method retries a bell or claims recovery.
Constructing another helper is not recovery from pending DMA or an uncertain
claim/release. External coordinated bus/DMA/lease/reset recovery is required.

`DeliveryKnownUnknownResponse` is valid only when the backend proves the
singleton retired and later reads are ordered after it. It is not a timeout
or partial-transfer status. A legacy ioctl's success alone may not establish
this promise; parent backend binding must prove it. Snapshot retains claim/
ARM/release uncertainty and partial lease diagnostics. There is no reset or
cancel API and the destructor does no I/O.

## Pairing and verification

`same_source(OwnedRawFrame, coop_host::OwnedFrame)` checks both complete
owned payloads and exact source bank/address, sequence, generation, camera
and token. The vectors remain valid after each hardware ACK. This supplies
identity pairing for future RAW-to-FPGA-NHWC comparison; it does not implement
conversion or certify bit-exact output pixels. Parent integration must match
the bridge geometry and compare those actual buffers separately.

Run `python run_capture_host_tests.py`. On this workspace it compiles using
MSVC 19.44 with `/std:c++17 /O2 /EHsc /W4 /WX`. Set `CAPTURE_HOST_VCVARS` to
override the VS environment file and `MODELSIM_BIN` to override ModelSim.
The C++ fake exercises bounds/reservations, complete/partial DMA storage,
rejection/uncertainty, exact token/camera/epoch, shared operation locking,
consumer order, source reuse and separate output helper calls. Its fake
pixels are deterministic test data, not actual camera or FPGA conversion.

The clean C++ register/event fixture is first checked against the unchanged
capture-control Python ownership oracle, then replayed through a uniquely
named local copy of the preserved SV harness and the actual endpoint/router/
capture controller/manager/cooperative controller. Expected transactions
come from host intent and planned source events, never DUT metadata. The
replay checks public accepted bus transactions and ownership states. DMA
records check reservation and owned identity; RTL replay injects source
publication contracts and does not instantiate camera/DMA/datapath or compare
DDR pixels. Upper write bytes in the replay are randomized by that existing
harness, strengthening the same-low-word transaction check.

`VALIDATION.md`, `host_api.json` and `artifacts/results.json` contain the API,
measured counts, exact commands, hashes and evidence. This is isolated host
protocol/control-chain evidence only. Functional deployment, physical source,
real driver error propagation, persistent allocator, real RX capacity, DDR
content/geometry and whole cooperative acceptance remain parent integration.
