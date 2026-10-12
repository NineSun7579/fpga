# Cooperative Linux transport candidate

Prepared Linux C++17 binding for the existing cooperative/RAW helpers. This is
CPU-tested source, not transport acceptance or a same-RAW board measurement.
No board device has been opened; no SSH, deployment, driver replacement, viewer
stop, FPGA load, PDS compile or place-and-route belongs to this work.

`transport.hpp` is the portable backend core and injectable syscall seam.
`linux_syscalls.hpp` supplies concrete open/flock/ioctl/mmap operations and a
worker-based bounded ioctl wait. `driver_abi.hpp` projects the exact retained
header's userspace fields and Linux `_IOWR('S', n, int)` macros. Natural 64-bit
alignment is mandatory: DMA_OPERATION is 40 bytes, data begins at 24, pointers at
24/32. Packed forward declarations would silently change the kernel copy layout.
Frozen PangoDev's DmaOp matches it; commands are MAP=0xc0045302,
H2F=0xc0045304, F2H=0xc0045305; TX mmap selector is 0, RX is 1048576.

Read-only provenance is `../driver_ownership_audit/README.md` and
`../current_viewer_binding_02/README.md`. The loaded fixed-module ELF build ID
1102cfd04acaeeea21ca4d03fe27ddbb32b7340a matches the retained fixed .ko SHA256
0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861. Retained C
b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72 and header
7bb7ee3a4cdb0ad1f7254a8ac40e39aff3a28f4ec96f8f97672e8488115b7ec1 are
source-qualified, not independently reproduced loaded-binary provenance.
The current binding snapshot records PID2740/start152164 and production main
SHA256 1fb152cf8a5c964528bd9fea2d3a84ba0cf393a9848a98a84be65921a56e2a39.
Those are historical identities, never permission to stop a process or evidence
that today's device is idle. Reference hashes bracket local final verification in
`artifacts/reference_hashes.json`; all retained inputs remain unchanged.

Construction validates plans without syscalls. `preflight()` invokes a trusted
external EvidenceProvider without device I/O; `open_checked()` requires prior
valid evidence and refreshes it before acquisition. There is no production
provider in this directory: absent evidence hard-blocks activation. A JSON
manifest or arbitrary caller booleans are not a validator. The provider must bind
physical domain, stable lock path, device identity, current driver/image receipts,
exclusive quiescent ownership, coherent mappings, H2F retirement/readback ordering
and F2H visibility/response contract. Receipt structs default entirely unproved.
This runtime gate still trusts the injected provider; it does not independently
prove its assertions. Provider methods must respect their deadlines.

The caller supplies one absolute stable lock filename for the entire physical
global controller namespace, in a trusted directory inaccessible to competing
untrusted writers. Never vary it by helper, PID, camera, image or invocation, and
never unlink it while a session can exist. Linux flock is exclusive/nonblocking
and attached to the open file description. The adapter requires a regular file,
one link, current UID and mode 0600, uses O_NOFOLLOW/O_CLOEXEC, and refuses a
second owner. An exhaustive read-only /proc scan checks character rdev fds and
filesystem-device/inode mappings before device open; inaccessible scopes fail
closed. This snapshot cannot exclude a noncooperating opener racing afterward:
external admission must exclude all legacy clients, including the viewer and
queued camera/NPU work. No driver-side exclusive-open claim is made.

Both global allocations request 4194304 bytes and both mmap calls must succeed at
that actual size. Driver EBUSY permanently quarantines the fd/lock; release could
otherwise free another client's global pages. RX partition is control [0,256),
RAW [256,614672) (614416 including reserved 16-byte tag), output
[614672,1843472) (1228800). RAW DMA copies exactly 614400 payload bytes, excluding
the reserved tag; output copies exactly 1228800. TX control [0,256) is exclusive;
only [0,16) is used. Singleton control writes zero all upper 96 bits and submit
exactly 16 bytes; reads return only the low little-endian word with zero upper96.
Allowed control addresses are the existing register tables (physical stride 4).
DDR is fixed read-only: RAW banks 0x01800000/0x01a00000, output banks
0x08000000/0x08200000 in 256MiB DDR. Invalid offsets, lengths, alignment or banks
are rejected before DMA; subtraction-based capacity checks avoid overflow.

Use `guarded_transport()` for BOTH helpers: it reuses the existing
SessionFaultTransport and its RAW STATUS bit2 contract at physical_address(0x104).
These M02 reads become valid only after externally verified endpoint loading.
The wrapper requires KnownOK STATUS, so a legacy MSI with unknown RRESP cannot
pass this gate. Read16 may report DeliveryKnownUnknownResponse after verified
retirement, ordering and CPU visibility; copy_ddr_blocking returns KnownOK only
with independently known successful response, exact bytes and stable copied data.
H2F ioctl READ means host-to-FPGA; legacy BRESP is unavailable, so verified
retirement can yield only DeliveryKnownUnknownResponse. Unproved retirement is
Uncertain, never an automatic retry. No ioctl return or MSI counter fabricates a
HardwareRetirement receipt. F2H uses legacy ioctl WRITE, which already waits for
driver MSI; a provider must additionally validate that final posted data precedes
MSI (e.g. documented same-TC non-relaxed PCIe/vendor ordering, or independently
observed fixed TLP contract), coherent CPU visibility and successful source read.
CPU atomic fences alone cannot establish this. **F2H proof is currently absent;
real activation and realboard measurement remain blocked.**

Use the same `backend.coordinator()` for CandidateRAW; it already locks complete
operations. Wrap each cooperative Candidate public operation with
`capture_host::with_exclusive_io(backend.coordinator(), ...)`. Lock order is shared
coordinator -> helper mutex -> backend io mutex. Helpers keep their own snapshots;
transport snapshot records opened/quarantined/active/error. Guard state also
requires the shared coordinator; do not concurrently call the guard directly.
The transport mutex serializes submissions across all helpers, while the shared
coordinator prevents interleaved CLAIM/COPY/ACK sequences.

Only retired, ordered, visible, successful DMA is memcpy'd from the coherent RX
mapping into the caller-owned vector. No DMA ever targets vector storage. Any
ioctl error/timeout, missing completion receipt or incomplete retirement permanently
quarantines the session. Its shared owner, fd, mappings, flock, syscalls and
provider remain globally pinned, including at C++ static teardown. Timed-out
workers remain alive with heap ioctl arguments; no EINTR restart, cancellation,
unmap, close, ACK or retry occurs. Destructor does no release even for idle sessions;
explicit `close_allowed_idle()` requires provider proof of global idle/no held
leases. Quarantined sessions have no local close/recovery API. Coordinated external
recovery must be independently designed and authorized.

Pins cannot protect process exit, exec, fatal signals or power loss. The task owner
and supervisor MUST keep the quarantined process alive (e.g. wait for an explicit
recovery signal rather than returning from main), retain its snapshot and helper
leases, and forbid ordinary service restart. No std::terminate or arbitrary
application shutdown policy is installed by this library.

Local tests: `build_local_selftest.cmd` builds MSVC C++17 /W4 /WX and runs only fake
syscalls. Linux: compile selftest.cpp and linux_lock_selftest.cpp separately with
`g++ -std=c++17 -Wall -Wextra -Werror -pthread`, then run; the latter uses only
new /tmp files, fork/flock and CPU deadline callbacks. A later authorized aarch64
compile should first validate sizes/macros against the actually qualified loaded
driver. A physical bench still requires new image/driver binding, all-user
quiescence, generation/lease recovery, H2F fully retired MSI/readback evidence,
F2H visibility/response evidence, and then a same-RAW comparison under the existing
helper pairing contract. This implementation claims none of those physical results.
