# Same-format RGA copy into an owned CPU snapshot

This isolated unit copies one full packed RGB565640x480 DMA-BUF into a private
`/dev/dma_heap/system` destination using persistent RGA FD imports and synchronous
`imcopy(src,dst,1)`, then copies614400 bytes into ordinary owned CPU memory. Both
images use `RK_FORMAT_RGB_565`, width stride640 and height480; there is no color
conversion, scaling, cropping, offset or interpretation of physical addresses.
The retained official SDK declarations are included directly and linked with
the actual target `librga`. Local compilation cannot certify hardware support.

This is a future copy component, not a viewer patch or FPGA acceleration claim.
The live viewer already writes its preprocessed RKNN input with one full memcpy;
the separate single-copy RKNN probe removes overhead in the older benchmark and
does not add its gain to live-viewer results. None of that work is changed here.

Target experiment `dd71e4cc135c4be7a62a1d198bbd3e8a` subsequently passed12
changing full-frame checks and100 paired copies with actual RGA2 Enhanced
(API1.10.1). Mean RGA-to-owned-snapshot cost was1.253847ms, versus0.317750ms
cached CPU copy; all bytes matched. The parent retained runtime/header/build
receipts and restored HDMI. This verifies heap buffers for those source bytes;
no PCIe buffer was imported and no live inference gain was measured.

## Reusable API and ownership

```cpp
#include "same_format_copy.h"

// Caller owns the original exported slot FD and its exporter/producer lease.
// The exporter generation must remain pinned for copier's whole lifetime.
rga_copy::SameFormatCopy copier(externalSlotFd, 0x96000);

// Each invocation holds that source slot stable until the entire call returns.
std::vector<uint8_t> pixels;
const auto stages = copier.copy(pixels); // swaps a new owned snapshot only on success

// For a caller-owned preallocated QByteArray or vector, exact size is mandatory:
// QByteArray pixels(614400, Qt::Uninitialized);
// auto stages = copier.copy(pixels.data(), size_t(pixels.size()));
// Publish pixels only after this call succeeds. Never use fromRawData on a heap map.
```

One object imports one fixed source slot and owns one destination. For six fixed
camera/slot FDs, keep six separate objects. Objects are noncopyable and are not
thread-safe; serialize each camera's calls. A different exported FD/generation
requires destroying/recreating its object while the parent controls the leases.
The caller must keep the exporter generation valid until the imports are released,
and prevent producer DMA or other writes to a source until the complete `copy()`
call ends. A duplicate FD pins the DMA-BUF file reference, not the driver's slot
lease, memory-reconfiguration contract or content generation.

Construction validates the declared length and the FD's DMA-BUF SEEK_END size
as exactly0x96000. It resets the size-query offset to0. A slab FD containing
multiple slots, padded/short/long export or unsupported size query is declined;
there is no guessed exporter ABI or suballocation offset. Source FD is duplicated
with CLOEXEC, so the helper never closes the caller's descriptor. RGA imports the
duplicate directly; the source is neither mmap'd nor CPU-sync'd by this helper.
Coherent exporter DMA visibility, completed producer work and source leasing are
caller preconditions. The unready DMA exporter/driver is not used or inspected.

Destination allocation uses the official `linux/dma-heap.h` UAPI, O_RDWR|CLOEXEC,
heap_flags0 and MAP_SHARED. The actual page size is checked and recorded; this
fixed packed614400-byte buffer must already be page-aligned or is rejected. This
works with4KiB pages and refuses silent padding/suballocations. Standard `system`
heap is chosen for a CPU cache-mapped destination; neither its name nor successful
mmap proves the installed kernel's cache policy. There is no uncached heap option
or private cache flag. Actual import, copy, byte parity and cache behavior remain
target capabilities. No allocation limit beyond this fixed size is inferred.

Both imports persist across frames. `imcheck` validates the full rectangles and
same-format images once. Per frame the sequence is:

```text
caller: producer complete, source leased and stable
helper: imcopy(src,dst,1) succeeds (synchronous completion)
        destination DMA_BUF START_READ
        full614400-byte memcpy into caller-owned CPU snapshot
        destination DMA_BUF END_READ succeeds
caller: publish snapshot / release or reuse source slot
```

DMA-BUF CPU sync provides cache coherence, not device completion. The RAII CPU
guard attempts END_READ during exception cleanup; a failed END_READ prevents
successful return. Device/sync errors poison the object to prevent a later frame
from treating incomplete work as valid. With the raw pointer overload, an error
may leave copied bytes in the caller's buffer: discard it and never publish it.
The vector overload leaves the previous vector intact on failure. An imcopy error
or failed synchronization requires parent-controlled recovery of the lease and
device state; this API does not promise producer-slot reuse after a failed call.
Destruction releases both RGA handles before unmapping/closing owned buffers and
the duplicated source FD. The caller's original descriptor stays caller-owned.

Measured wall/thread CPU stages are RGA call, START_READ, snapshot memcpy,
END_READ, combined CPU access/snapshot and total. They include the real device
wait and cache-sync syscalls. Vector allocation and final swap lie outside those
internal timings; the probe preallocates its owned snapshots. A GUI/inference
consumer owns its snapshot independently of future DMA-heap or source reuse.

## Heap-only correctness and paired cost probe

`probe.cpp` allocates its source from the same system heap, fills it under
START/END_WRITE, and calls the actual hardware copy on every frame. Four patterns
with three changing frames each test12 full frames: all65536 RGB565 word values
are repeated across the full307200 pixels, zero/FF checkerboards, changing byte
ramps and moving word splits. Every output byte is compared exactly with its
generated source; no conversion calibration or fitted correction is allowed.
CPU snapshot canaries and unchanged source bytes are also checked.

After correctness, default4 rounds×25 frames compare an ordinary system-heap
CPU-to-owned-snapshot copy against RGA-to-system-heap plus CPU-to-owned-snapshot.
Both copies include relevant START/END_READ and memcpy costs, both finish before
byte comparisons, and round order alternates AB/BA. Three warmups per round also
use changing full frames. Source fill/sync, source/output validation, allocation,
import and setup are outside each measured copy interval. Source is already
CPU-written and warmed, which favors this CPU calibration; it represents neither
an uncached PCIe BAR read nor live camera/inference throughput. No extra throughput
ratio is presented as a viewer/FPGA/RGA acceleration result.

Default112 paired/warmup RGA calls plus12 correctness calls are bounded by an
8-second in-probe budget and10-second runner timeout. Excess time or any missing
byte/completion evidence fails with partial logs retained. Unexpected capability
is a failure, not a virtual-buffer fallback. This probe opens only the system
heap and RGA through librga; it does not open an exported PCIe FD, camera or NPU.

## Parent target commands (after its NPU work finishes)

The parent must hold its existing shared board lock throughout building/running;
`--board-exclusive` records that assertion, and this unit does not invent a second
lock protocol. The runner must run locally on the AArch64 target. It has no SSH.
Ship this directory intact; `--sourcepath` defaults to the runner's own directory.

```sh
# Build only: immutable source/header snapshot; no device operation.
python3 run_target.py --phase build --board-exclusive --out receipts/build_01

# One serialized snapshot + build + quick hardware experiment in a fresh directory.
python3 run_target.py --phase experiment --board-exclusive --out receipts/experiment_01
```

Matching installed headers default to `/usr/include/rga`; use `--headers-root`
only for the parent's actual matching SDK. Compile commands link `-lrga -ldl`
with GNU C++17 and `-MD` dependency receipts, matching the SDK's GNU statement
expression macros. No SDK structs or symbols are recreated.
The runner records actual compiler/cc1plus hashes, copied RGA header hashes,
compiler dependencies including Linux DMA UAPI, actual page size, AArch64 ELF
identity, executable and linked-library SHA256, and runtime querystring/version
plus resolved librga identity. It requires fresh output directories and never
overwrites evidence. Build-only reports leave hardware capability unverified.
Failure logs survive and make no performance claim. The experiment checks exact
pattern coverage and every paired completion, returning cached-heap cost values.

## Local validation

Local checks use existing privately extracted cross-tools and retained RGA
headers under sibling `rga/local_evidence/`, read-only. Compile-only host syntax
and AArch64 object compilation exercise the actual signatures including
importbuffer_fd, wrapbuffer_handle, imcheck, imcopy and querystring. Undefined
device symbols in the object are expected until the parent links its real librga.
No fake hardware runtime, global installation, network access or board execution
is needed. Results are retained in `local_evidence/receipt.json`; target tests and
all PCIe exporter/live-viewer integration remain pending.
