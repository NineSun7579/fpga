# Offline Pango PCIe dma-buf candidate

This directory is an independent ASCII driver rewrite for review and later
compilation. It is **not deployable evidence**. No SSH, target build, hardware
access, loaded-module replacement, viewer change, or FPGA/IP/RTL change was
performed. The parent owns compilation, any module switch/recovery, and restoring
the usual session when the viewer closes.

`PANGO_EXPORT_PROVEN` is fixed to **0** in the source. A well-formed export or
lease command returns `EOPNOTSUPP`; there is no runtime switch. The dormant
export/lease implementation and enabled-branch specification tests are provided
for audit. Do not lift this gate merely because the offline tests or a kernel
build pass. Verified drain, importer, mapping, and blocking completion evidence
are missing. Unsafe legacy IRQ-launched RX paths have been removed. In addition,
`pango_import_backend_ready()` permanently returns false, and backend map/sync
callbacks permanently return unsupported. Changing the export gate alone cannot
enable importer mapping or leases. There is no compiler/runtime backend override.

## Frozen provenance

The source of register/legacy ABI behavior is the untouched retained pair:

| Input | SHA256 |
| --- | --- |
| `../retained/pango_pci_driver.c` | `b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72` |
| `../retained/pango_pci_driver.h` | `7bb7ee3a4cdb0ad1f7254a8ac40e39aff3a28f4ec96f8f97672e8488115b7ec1` |

Pins agree with `../../DMA_COPY_DESIGN.md`. The loaded module's recorded Build ID
is `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`; its recorded SHA256 is
`0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`.
Exact original source/object/compiler attribution is unavailable. This rewrite
does not claim to rebuild or match that object. The retained GBK/UTF-8 bytes were
only read and hashed, never decoded for rewriting or edited.

The parent verified generated Linux 6.1.99 headers, configuration, tools and
Module.symvers at `/usr/src/linux-headers-6.1-rockchip`, with shared DMA buffers
enabled. Only four selected API headers and the kernel Makefile are retained
locally. `local-validation.json` records their full SHA256 pins. They establish
declarations; they are not a complete local kernel build tree. Bind the actual
header root explicitly for the parent's later build:

```sh
make KDIR=/usr/src/linux-headers-6.1-rockchip
```

This subagent ran no target build. The parent reports that the earlier private
candidate (build identifier prefix `3ffc96...`) compiled against Linux 6.1.99 with
GCC 12.2, with only a kernel-compiler warning, and that its shared C harness and
29 model tests ran in local WSL. Those receipts describe **older bytes**. They
are not validation of this audit revision, whose full kernel build and symbol
review remain pending. The source uses the 6.1 `class_create(THIS_MODULE, ...)`
API and `MODULE_IMPORT_NS(DMA_BUF)`.

The parent's independent audit (`ses_ef691...`, reported SHA prefix `0a6b0f66`)
identified usercopy/mmap lock inversion, 64-bit allocation with a 32-bit command,
unsafe streaming maintenance of coherent page aliases, persistent bidirectional
bounce copyback, and core-export lock ordering. This revision addresses all five.
The upstream DMA-BUF registry/debugfs/reservation lock cycle motivates unlocked
publication; the local selected vendor headers cannot prove the complete vendor
implementation's lock graph. Prior local manifest/report bytes are stored by
content hash in `archive/`. Parent build/audit receipts remain parent-owned and
are not rewritten or represented as newly verified full SHA256 identifiers here.

## Compatibility scope

This preserves the retained native `DMA_OPERATION` layout: five unsigned 32-bit
fields at offsets 0/4/8/12/16 followed by `DMA_DATA`'s two native pointers. On
arm64 that means data offset 24 and total size 40; on a 32-bit ABI, offset 20 and
size 28. The driver consumes only the first 20 bytes and never dereferences the
unused pointers. The four command encodings retain **sizeof(int) = 4**, even
though the pointed-to argument is larger:

| Command | Encoded command | Operation |
| --- | --- | --- |
| `PCI_MAP_ADDR_CMD` | `0xc0045302` | `cmd=0` allocates TX; `cmd=1` allocates RX; bytes from `total_length`, page rounded |
| `PCI_DMA_READ_CMD` | `0xc0045304` | synchronous host TX to FPGA (H2F) |
| `PCI_DMA_WRITE_CMD` | `0xc0045305` | synchronous FPGA to host RX (F2H) |
| `PCI_UMAP_ADDR_CMD` | `0xc0045307` | `cmd=0` TX, `cmd=1` RX, `cmd=3` both |

MAP rejects zero or more than 4 MiB, duplicate allocations, invalid direction,
and in-flight or pending handoffs. Copies use `offset_addr`, `ddr3_addr`, and `total_length`;
`current_len` and `cmd` do not override the ioctl's direction. Copies must be
nonempty, within the allocation, and DWORD aligned including the FPGA address.
The FPGA address range must not overflow 32 bits. The frozen 10-bit DWORD TLP
encoding and register order are retained; 4096 bytes encodes length zero in that
field, as in the source. Completion remains MSI vector 0, pending hardware proof.
Probe requests only a 32-bit streaming/coherent DMA mask. The entire allocation
and each H2F/F2H host address interval are checked against 2^32 before use;
overflows return `EOVERFLOW` before any register write. CMD bit16 remains zero
for the verified 32-bit address mode; the high host register is always cleared.

There is one open **file description**, shared by any dup/fork of that description.
Process state changes use one mutex. A second independent open returns `EBUSY` before
resetting any state. File/VMA lifetime and outstanding exports prevent a new
allocation owner until the previous generation is actually gone.

The ioctl dispatcher copies a single immutable request union before acquiring
that mutex. MAP/H2F/F2H consume the 20-byte prefix; UNMAP copies only the 4-byte
cmd field at its legacy offset. No helper performs input usercopy. Output usercopy
and `dma_buf_export`/`dma_buf_put` likewise run unlocked. mmap and VMA callbacks
enter from mmap_lock to driver lock; no ioctl can enter user fault handling in
the reverse order. An in-flight syscall holds the normal file-description pin.

Legacy mmap remains coherent allocation mmap: selector byte offset 0 for TX and
0x100000 for RX, bounded from the beginning of the chosen allocation. The driver
checks the untrusted page offset before any shift, resets it to zero for the DMA
API, pins initial/forked VMAs and the module/device, and rejects UNMAP while any
VMA is alive. VMA `vm_file` also holds the file description open. Private mappings
are unsupported. Custom DMA mmap implementations returning `vm_ops` are rejected;
the target coherent mmap implementation still needs review. Legacy RX mmap
continues exposing the original allocation, including existing metadata, by ABI.
Only the new dma-buf views exclude metadata. Legacy writable CPU mappings remain
possible for compatibility; a cooperative export client must never write RX.
New legacy mappings are rejected during any pending export, pending BEGIN, or
live GPU lease. Existing VMAs and forks remain pinned; this does not revoke CPU
access to already mapped pages or turn writable legacy mmap into a GPU fence.

This is a narrow four-command candidate, **not a full replacement of the old
driver**. Old config/read/write/performance/GPIO/PWM/automatic camera/NPU ioctls,
MSI-wait ioctls, file read/write/seek, and unknown commands are unsupported. The
ioctl dispatcher returns `ENOTTY`, never false success. MSI vectors 1/2 are
acknowledged without programming `read_img` or `read_npu`; no IRQ path can touch
RX. Normal four-command polling is the intended compatibility scope. The source
does not alter FPGA NPU RAW routing. Parent application review must establish
that unsupported operations are not required before any deployment proposal.

PCI IDs are not guessed from an unrelated source. Both `vendor_id` and `device_id`
module parameters default to zero; module initialization refuses missing/invalid
IDs. The parent must independently verify them before any later load. The node
name is preserved as `pango_pci_driver`; three MSI vectors and a valid memory BAR1
of at least 0x204 bytes are required. Probe failure unwinds resources in reverse
order. The candidate does not modify upstream bridge PCIe tuning.

## Exact v1 export and lease ABI

`pango_dma_uapi.h` is the authoritative shared header. Both argument structs
are fixed-width and 48 bytes with `__aligned_u64` for equal native/compat layout.
The full encoded command must match; another size/direction returns `ENOTTY`.

`PANGO_EXPORT_SLOT_V1 = 0xc0305320` takes fields in this byte order:

| Offset | Field | Caller initializes | Successful result |
| --- | --- | --- | --- |
| 0 | u32 version | 1 | 1 |
| 4 | u32 slot | 0..5 | unchanged |
| 8 | u32 flags | 0 | 0 |
| 12 | s32 fd | **-1** | new CLOEXEC dma-buf FD |
| 16 | u32 offset | 0 | `slot * 0x97000` |
| 20 | u32 length | 0 | **0x96000** |
| 24 | aligned u64 generation | 0 | nonzero session ID |
| 32 | u32 reserved[4] | all zero | all zero |

Export requires an existing exactly 4 MiB RX allocation, 4 KiB pages, one live
owner, and no active DMA. At most one dma-buf object exists per slot; duplicate
FDs/importer references to that object are permitted. Separate slot objects pin
the same allocation generation. Six camera views are 150 pages each, starting
at 0, 0x97000, 0x12e000, 0x1c5000, 0x25c000, and 0x2f3000. Each ends before its
16-byte commit tag; the entire tail page and scratch at 0x3ff000 remain private
to the legacy mapping. No arbitrary offset/size or 4 MiB dma-buf is supported.

An FD is reserved without installation. Under the driver lock, export reserves
the unique slot and pins the generation. `dma_buf_export` runs unlocked, then
the driver revalidates device/owner state. Copyout also runs unlocked while that
pending reservation blocks all PCI copies, UNMAP, new CPU mappings, and competing
exports/BEGIN/END. State is revalidated again before publishing the slot and
installing the FD. Removal or failed core export/copyout rolls the reservation
back; every `dma_buf_put` and FD release runs outside the driver mutex. The
release callback distinguishes a reserved object from a published one and drops
exactly its generation reference. No unreported FD or leaked export pin is left.
On failure the caller must ignore all output fields; a partially copied
output can contain a number that was never installed. Initialize a fresh request
for each retry. The helper checks all returned fields and CLOEXEC; the old
dispatcher's unknown-command success with unchanged fd=-1 is rejected as EPROTO.

`PANGO_SLOT_BEGIN_V1 = 0xc0305321` and
`PANGO_SLOT_END_V1 = 0x40305322` use this layout:

| Offset | Field | BEGIN | END |
| --- | --- | --- | --- |
| 0 | u32 version | 1 | 1 |
| 4 | u32 slot | exported slot | same |
| 8 | aligned u64 generation | export result | same |
| 16 | aligned u64 token | input 0; checked nonzero result | exact result token |
| 24 | u32 flags | 0 | 0 |
| 28 | u32 reserved[5] | all zero | all zero |

The staged BEGIN path requires completed PCIe DMA and the slot's export object,
then asks the audited backend to hand off the slot. This candidate's backend
returns unsupported, so BEGIN never claims coherence. With a future audited
backend, BEGIN reserves the lease and adds a generation pin under the mutex,
copies out unlocked, then revalidates and commits or rolls back under the mutex.
Its pending state blocks all DMA, UNMAP, new CPU/importer mappings and other slot
transactions. Removal or last-export release during delivery prevents commit.
A failed copyout rolls the lease back; no GPU work may start before the ioctl
returns success with checked output. Failed backend rollback quarantines the
generation. END verifies owner/generation/token and releases the lease only on
successful backend handback; unsupported handback retains the lease. Tokens are never
reused, even after rollback; wrap is rejected. F2H rejects with `EBUSY` if its
byte range intersects any leased pixel range. Neighbor slots, commit tags, and
scratch are non-overlapping; H2F uses independent TX. UNMAP rejects either
buffer while any export, VMA, lease, pending transaction, or transfer exists. An FD close does not
release a lease. An explicit END can recover a lease whose last FD was closed,
provided the owner still proves GPU completion.

Byte zero of each exported FD is byte zero of that camera's pixels. The returned
`offset` identifies the original legacy RX allocation position; it is **not** an
offset to apply to the RGA import. Import the bounded FD at offset zero.

## Importer mapping and completion contract

The dormant builder owns `dma_get_sgtable`'s original page SG, obtained from the actual
PCI allocation device and allocation bytes. Extraction fails closed if SG entries
lack pages, have nonzero offsets or non-page lengths, or do not cover exactly the
allocation. The slot builder slices allocation SG order into a new 150-page
SG; it does not assume contiguity across original entries. Original SG DMA
addresses are not used, nor is a PCIe DMA address cast into a CPU/physical/RGA
address. The mapping skeleton passes fresh bounded SG storage and the **actual
attachment device** to a backend boundary, preserving `orig_nents` for free.
That backend always returns `EOPNOTSUPP`; no streaming DMA mapping is performed.
Map failure frees sliced storage without recording a mapping. Attach also fails
before allocating importer state when the backend is absent. There are no
generic streaming map/unmap or cache-sync calls in the candidate.

Pages exposed by `dma_get_sgtable` do not authorize streaming cache maintenance
of aliases of `dma_alloc_coherent` memory. Attributes zero can touch the wrong CPU
alias; blindly adding `DMA_ATTR_SKIP_CPU_SYNC` does not prove coherence, IOMMU
access, or bounce safety. A future backend must explicitly audit the actual
allocator, architecture/cache aliases, RGA device DMA path, and no-bounce behavior.
If a bounce mapping is required, it must instead define map/unmap/handoff lifetime
inside each lease before any PCI producer refill, including import failure and
crash paths. Persistent TO_DEVICE bounce storage may otherwise remain stale;
persistent BIDIRECTIONAL storage can copy old pixels over newer PCIe data on
later unmap. END alone does not solve those hazards.

The source direction guard admits only `DMA_TO_DEVICE`; `DMA_BIDIRECTIONAL` and
`DMA_FROM_DEVICE` always return unsupported, even in a hypothetical backend.
If the actual RGA importer requires bidirectional mappings, this candidate must
decline it until a separately audited implementation exists. Nonzero importer
mapping attributes, CPU dma-buf mmap/vmap and full/partial CPU access remain
unsupported. These callbacks return `EOPNOTSUPP`, never synthetic coherence or
completion. The existing coherent legacy RX mapping provides the original CPU
view. No successful RGA import or cache coherency is claimed by this revision.

The trusted client protocol is:

1. Keep one worker per camera and serialize F2H/tag checks for that camera.
2. Complete F2H successfully, verify the commit tag, then perform checked BEGIN.
3. Submit this exported FD **only as an RGA source**, using a verified blocking
   same-format copy. Wait for successful RGA completion before checked END.
4. Sync/access the separate destination DMA-heap buffer for CPU use as required
   by that allocator; keep existing detached image/snapshot ownership.
5. Stop/join workers, finish all GPU work, end leases, release RGA imports, close
   export FDs, munmap legacy mappings, and finally close the device description.

`pango_dma_client.h` supplies checked request helpers, not an RGA implementation.
The kernel cannot infer that a caller's END means RGA completed, stop an importer
from using an FD outside a lease or revoke writable legacy mappings. BIDIRECTIONAL
import is rejected. There is no implicit reservation
fence inserted by this exporter. Cache sync, dma-buf unmap, and FD close are not
completion proofs. Async or uncooperative users are outside this contract. On an
ambiguous RGA error keep the lease, stop further work, and retain resources;
owner close then quarantines. A source-code gate change requires parent audit of
the actual blocking RGA API, including crash/cancel behavior and allocation pins.

## Release, faults, and removal

Generation references independently pin `get_device(PCI device)` and
`THIS_MODULE`; dma-buf core also pins the exporter module. A normal file close
holds the ioctl mutex, waits for any remaining transfer completion and drops the
owning reference. Both RX and TX remain alive until all generation refs are gone.
Only that final put frees coherent memory, using the original allocation device,
and permits another open. A closing file cannot reset/free another owner's state.
All input usercopy happens before locking. Failed output delivery clears the
pending transaction under lock and drops its independent pin; core/file releases
remain outside the lock. Pending reservations also conservatively quarantine on
an unexpected owner release, although a real syscall's file pin defers release.

A submitted DMA timeout/signal has no proven abort/drain. The driver disables bus
mastering, consults Transactions Pending only for containment, and **permanently
quarantines** the entire generation. A late MSI does not undo quarantine. Owner
death during any lease does the same, even when all FDs later close. Device remove
marks dead before waking/waiting for ioctl work, rejects further copy/export/map,
clears bus mastering before BAR/IRQ teardown, and quarantines every existing
allocation even if idle. `get_device` alone does not preserve an IOMMU DMA domain
after removal, so the candidate does not free through a potentially torn-down
domain later. Existing RGA mappings retain RAM but successful GPU completion on
removal is not claimed.

Quarantine intentionally leaks one generation/module/device pin and blocks
reopen/unload. Reboot is the documented recovery boundary; there is no reset,
force-free, or module-unload workaround. Surprise removal, power loss, MSI0
transaction attribution, and all posted PCIe writes still require actual hardware
evidence. The export gate stays off because these cannot be proven offline.

## Local validation and freeze

```sh
python validate_offline.py --wsl Ubuntu-24.04
python freeze_candidate.py --check
```

The first command hashes the retained inputs, checks selected exact API
declarations, runs **37** deterministic lifecycle/SG specification tests, and
compiles/executes the shared policy and extracted driver event harnesses using
local WSL GCC. Both C harnesses pass for this revision. The shared policy covers
complete 32-bit intervals, slot overlap and pending-aware UNMAP. The event harness
extracts unchanged candidate function/struct bytes into temporary headers and
records their SHA256s. It executes the actual ioctl, allocation, transfer, export,
lease, mmap and release decisions with mocked kernel events. Assertions reject
usercopy, core publication, FD installation and core put while driverlocked;
user faults call mmap callbacks, and core/copyout hooks contend against pending
reservations or inject removal/last-export close. Both direction/address boundary
checks, delivery rollback and unsupported backend/direction guards are covered.

Model checks cover independent opens, close/syscall and close/export orderings,
VMA forks and bounds, duplicated FDs/importer refs, unmap blocking, every slot's
overlap/tag/scratch boundaries, failed export/BEGIN copyout, attach/map failures,
original versus merged SG counts, lease tokens, timeout/late completion, owner
death, device removal, pending export/BEGIN phases, and complete DMA address
intervals. Enabled transaction tests explicitly use a **hypothetical** audited
backend/proof in the model or mock translation unit; production gate/backend
source bytes are unchanged. Their mapping/cache model is a specification, not
evidence that a coherent allocation can be streamed to RGA.

These tests do not run Linux kernel locking, KASAN/lockdep, PCIe, cache
maintenance, IOMMU/SWIOTLB, RGA, or display/inference load. In particular, prove
that attachment mappings do not retain stale bounce buffers and that page aliases
of coherent memory are valid for the actual RGA DMA API. Any unresolved path must
continue returning unsupported rather than guessing. Parent acceptance still
needs a **fresh** full matching build for the revised bytes, module symbol review, runtime lifecycle/fault tests,
full-frame byte equality, all-six-slot isolation, and matched performance trials.

`freeze_candidate.py --freeze` creates the source/report input manifest for this
handoff; it never compiles or deploys. `--check` rehashes each named candidate and
retained input and immutable archived local evidence. `--archive-existing` saves
the previous manifest/report by content hash without changing parent receipts.
The manifest requires passing local evidence bound to the current input bytes.
Generated `__pycache__` files are excluded. Regenerating the
validation report or changing any source requires a deliberate new freeze.
