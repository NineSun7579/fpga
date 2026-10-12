# Local validation receipt

Scope: only this new directory was written. No SSH, board/device open, real device
ioctl or mmap, deployment, driver change, viewer stop, PDS/PnR or live test.

Passed on Windows x64: MSVC 19.44.35222, C++17, /O2 /EHsc /W4 /WX, using
build_local_selftest.cmd. Portable fake-syscall tests passed.

Passed in existing Ubuntu-24.04 WSL: g++ C++17, -Wall -Wextra -Werror -pthread.
Both selftest.cpp and linux_lock_selftest.cpp built and ran successfully. The
Linux test exercised only /tmp regular files and CPU callbacks. No packages were
installed. Static assertions validated Linux ioctl macro values, mmap selector,
64-bit natural struct layout, and all three existing Transport method signatures.
This is x86_64 Linux verification; aarch64 compile/loaded-driver ABI check remains
a separately authorized next binding step.

Assertions cover:

- default/absent provider refuses before any syscall; constructor is inert;
- existing owner refuses before device open; second owner refuses at lock;
- actual 4MiB TX/RX allocation requests and map sizes; EBUSY quarantine without release;
- control singleton 16-byte transfer, low32 little endian and upper96 zero;
- disjoint prefix/RAW-tag/output reservations; alignment/overflow/bounds rejection;
- RAW request exactly 614400 versus reserved slot 614416, output exactly 1228800;
- null DMA vector pointers and stable owned vector after immediate RX overwrite;
- unknown F2H response cannot return KnownOK or copy bytes; STATUS guard stops ACK;
- ioctl timeout, missing retirement, missing visibility, or short completion cause
  permanent active quarantine, no ACK/retry/ioctl release and no destructor close/unmap;
- cross-process real flock refusal, owner-release reacquisition, 0600 and NOFOLLOW;
- bounded CPU worker success, expired deadline with zero calls, timeout with retained
  callback completing safely later.

Exact shared contract remains `IoStatus { KnownOK, KnownRejected,
DeliveryKnownUnknownResponse, Uncertain }` and `DmaResult { IoStatus status =
Uncertain; size_t bytes = 0; }`. Signatures compile against the unchanged helper:
`IoStatus read16(uint32_t, Beat&)`, `IoStatus write16(uint32_t, const Beat&)`, and
`DmaResult copy_ddr_blocking(uint32_t, uint64_t, vector<uint8_t>&)`.

`artifacts/reference_hashes.json` stores actual SHA256 before/after final verification
for retained driver C/header/fixed ELF, both helper headers, STATUS decorator,
current_viewer_binding_02 frozen/current inputs and PangoDev. These hashes bracket
verification after implementation, not a retroactive preimplementation timestamp.
No reference was patched. Hindsight was unavailable (connection refused).

Pending physical conditions: current externally verified device/image identity,
all-user quiescence and global queued-work retirement, actual loaded ABI binding,
fresh generation/lease coordination, H2F fully retired MSI with ordered readback,
and provider-backed F2H posted-write visibility and response-success evidence.
There is no real provider implementation or board receipt here. No transport
acceptance, same-RAW measurement, FPGA image qualification or deployment is claimed.
