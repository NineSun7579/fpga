# Pango coherent RX sharing candidate

This isolated Linux 6.1 driver exports the **whole 4 MiB PCI RX coherent
allocation** as a DMA-BUF, with one cooperative RKNN input lease. RKNN remains
enabled. The FPGA legacy NPU/camera interrupt DMA paths are absent; vector 1/2
handlers acknowledge Linux IRQ delivery without launching transfers. No production
source was edited and no board access, module replacement or device open occurred.

Status: source candidate compiled and linked against Debian **6.1.176 amd64**
headers, with `-Werror` and successful MODPOST including `DMA_BUF` namespace import.
This is an API/link check, **not an RK3568-loadable binary or hardware validation**.
The parent must build against the matching Rockchip 6.1.99 configuration and
`Module.symvers`, then validate attachment/import, completion and slot reuse.
There is no runtime proof-gate switch. Deployment requires the completion-fixed
FPGA image and the cooperative client contract below.

## Build and source identity

On the parent's matching target build environment:

```sh
make KDIR=/usr/src/linux-headers-6.1-rockchip
```

For a cross-build, pass the matching `ARCH=arm64 CROSS_COMPILE=...` in addition.
The module is `pango_zc.ko`, the PCI driver name is `pango_zc`, and the device node
remains `/dev/pango_pci_driver`. Default PCI ID is `0755:0755`; verify the actual
endpoint and pass read-only `vendor_id`/`device_id` load parameters if different.
Only one device and one allocation generation are supported. The old driver
must release this endpoint and node before replacement. Parent owns all rollout,
rollback and board actions. Do not load the local amd64 verification output.

`SHA256SUMS` identifies the delivery source, UAPI, Makefile and this README.
`BUILD_CHECK.txt` records the local check and its limits.

This is a new, reduced driver implementing the retained register/ABI contract;
it is not claimed to be the exact source of the previously loaded fixed binary.
Reference: `D:/race/ov56401/project/hardware_acceleration/dma_export/retained/`
(`pango_pci_driver.c` and `.h`), plus the current `host/detview/pango_dev.h`.
Historical driver binary provenance remains unresolved and is not represented
as a successful target validation of this candidate.

## FPGA completion dependency

The old FIFO-count completion blocker has newer source/simulation evidence:
`D:/race/fpga/signature_read_analysis/completion_order_fix/README.md` and
`artifacts/results.json`. The actual integrated source inspected is under
`fpga_acceleration_delivery/ddr_rgb_letterbox/integrated/source/pcie_dma/pcie_dma_ctrl/`:

* `ips2l_pcie_dma.v:337`: controller busy is
  `mwr32_req | mwr64_req | mwr_tx_busy`, covering launch and transmit drain.
* `ips2l_pcie_dma_mwr_tx_ctrl.v:111,315`: final payload acceptance is
  `tvalid && tready && tlast`; busy clears only on that event with no remaining
  request length. Final MSI follows payload acceptance.
* `ips2l_pcie_dma_tx_top.v:110`: the TX read-length wire is 11 bits, matching
  its ports. The separate controller request-length zero encoding is preserved.

Inspected SHA256s, respectively:

```text
c93c399f6b64d25957e5c5ac6616cbac0638a5a2676ed0e6211e4d319f8cc854
5bbf02fe6da800d5ba3f8269d9f106b3530c5382bcc88c1e12254a887080d608
513718054bd3537030bd1576b08ec197ce1d6d6c022c97becd2b60bd1e5c30a9
```

The retained eight passing cases cover 16, 256, 4352 and 1,228,800 bytes at
32/64-bit addresses, with stalled final payloads and multiple clock ratios.
They establish source simulation behavior, not a fresh board/image identity.
Parent reports the current integrated image has this fix; parent must verify
that identity during rollout. Never use this driver on the FIFO-completion image.
The endpoint must preserve normal PCIe posted-write/MSI ordering (no relaxed
ordering that allows MSI to overtake payload). The driver uses MSI vector 0 as
the sole transfer completion signal; no interrupt status/transaction ID is
available to distinguish unsolicited vector-0 events.

## ABI and client sequence

Existing viewer allocation/transfer ABI is preserved for its used operations:
MAP `_IOWR(0x53,2,int)`, H2F command 4, F2H command 5; UNMAP command 7 is
also implemented. Only the fixed first 20 bytes of `DmaOp` are copied; its
unused native pointer tails do not enter the kernel. TX maps at file offset 0;
RX maps at file offset 1 MiB, a selector reset to backing-buffer offset zero.
Each buffer is at most 4 MiB. UNMAP accepts selector 0/1/3 for TX/RX/both,
but returns `EBUSY` permanently for that generation after its first successful
CPU mapping. Unmapping a VMA does not reset this conservative flag. Close all
CPU mappings, DMA-BUF/importer references and the owner to free that generation.
Other historical ioctl/camera/NPU interfaces return `ENOTTY`.

The BAR1 programming sequence uses DDR address `+0x1e0`, host low/high address
`+0x110/+0x120`, total bytes `+0x200`, and command `+0x100`. Host DMA addresses
are restricted to 32 bits; command bit 16 is zero, direction F2H is bit 24,
and a 4096-byte chunk has the legacy ten-bit DW length encoding zero. Transfer
bounds, nonzero lengths, four-byte alignment and address overflow are checked.
Conventional MSI needs four allocated vectors to expose roles 0,1,2; only those
three roles have handlers. BAR resources, allocation and MSI errors fail probe.

Use `pango_zc_uapi.h` directly for the new commands:

1. Open exclusively, allocate TX and RX through the existing MAP calls with
   4 MiB each, and retain the owner's device fd through inference retirement.
2. `struct pz_export_rx ex = { .version = PZ_VERSION };`
   `int dma_fd = ioctl(owner_fd, PZ_EXPORT_RX, &ex);`
   The **ioctl return value is the fd**, with `O_RDWR|O_CLOEXEC`; negative means
   errno. Export once per allocation generation. An fd of zero is valid.
3. Reserve RX `[0x200000, 0x32c000)` for the 1,228,800-byte UINT8 NHWC
   `1x640x640x3` model input. This is a host RX byte offset, separate from FPGA
   DDR addresses. Metadata remains at RX offset zero. Viewer DMA must use disjoint
   ranges; a full 4 MiB RX write cannot coexist with a leased input slot.
4. Import the full DMA-BUF fd into RKNN using the tensor slot offset and size:
   `rknn_create_mem_from_fd(ctx, dma_fd, NULL, PZ_INPUT_BYTES, PZ_INPUT_OFFSET)`
   according to the shipped RKNN API. Bind the exact queried input attributes.
   Confirm on the target that offset import accesses the requested slot, with
   parity/pattern checks; the parent's successful offset-zero DMA-heap import
   does not by itself validate a PCI RX DMA-BUF or this nonzero offset.
5. Execute F2H with `offset_addr=PZ_INPUT_OFFSET`, `total_length=PZ_INPUT_BYTES`
   from the completed FPGA RGB888 bank. Only a successful exact-slot transfer
   records readiness. Keep the FPGA source bank stable until F2H returns.
6. BEGIN with version 1, offset/length as above, all remaining fields zero.
   It returns a nonzero token in the same struct. Only then run RKNN inference.
   BEGIN requires a live export and a successfully completed exact-slot F2H.
7. After **synchronous RKNN completion**, or independently verified async
   completion, END with the returned struct unchanged. END consumes readiness.
   Retire each run before reusing the slot. If completion is uncertain, retain
   the lease; do not assert END merely because a host deadline elapsed.
8. At shutdown, retire inference, END any completed lease, destroy RKNN imported
   tensor memory/context as required by RKNN, unmap CPU views, close DMA-BUF fd,
   and finally close the owner. No importer references may remain for reuse.

BEGIN copyout happens outside the driver lock. Failed publication rolls back
the token; `EFAULT` requires retry without using any partially copied token.
BEGIN/END use fixed-width fields with a 64-bit aligned token, matching compat
layouts. No kernel physical address or PCI DMA address is exposed to RKNN.

## Attachment, coherency and lifetime

RX backing remains `dma_alloc_coherent`. Export derives CPU page backing with
`dma_get_sgtable`, verifies page alignment/coverage, and constructs a fresh
page-granular SG list per attachment mapping. `dma_map_sgtable` maps those pages
for the **importer's device/domain**, independently of the PCI DMA address.
Only `DMA_TO_DEVICE` and `DMA_BIDIRECTIONAL` mappings are accepted. BIDIRECTIONAL
accommodates input importers that request it; the client must never bind RX as
an NPU output tensor.

Bounce mappings cannot safely persist while independent PCI DMA refills RX.
After mapping, every importer DMA page is checked against the original physical
page using the importer's IOMMU domain, or the DMA-direct inverse when there
are no custom DMA ops. A bounce translation, custom non-IOMMU backend or
unverifiable translation fails `EOPNOTSUPP`; SG teardown uses the original map
direction and matching attributes. This intentionally restricts support rather
than silently sharing a stale SWIOTLB staging copy. Target RKNN/IOMMU attachment
compatibility is still unverified; map errors must be surfaced by the parent.

`DMA_ATTR_SKIP_CPU_SYNC` avoids streaming cache maintenance through a cached
linear alias of coherent backing. CPU mappings use **only** the allocator's
`dma_mmap_coherent` alias. There is no vmap/kernel cached alias. Balanced
DMA-BUF CPU BEGIN/END tracks exclusion and uses ordering barriers; no
`dma_sync_sgtable` operates on that forbidden cached alias. A CPU writer's END
invalidates readiness. Active CPU sessions block F2H and consumer BEGIN.
Allocator VMA callbacks and private data are preserved, including ARM64's
physical-access callback. No driver VMA callbacks or private data are installed.
Allocation and mmap failures emit rate-limited device errors with errno.

The device owner and DMA-BUF pin an allocation generation; each VMA retains its
backing file, which in turn retains the owner's or DMA-BUF's generation reference.
The generation pins the allocator device and module. A second open/reallocation is
blocked until all references from the old generation retire. Releasing the
owner does not free memory still imported or mapped. A final owner release with
an outstanding consumer lease, unbalanced CPU session, interrupted DMA or DMA
timeout quarantines RAM/device/module references and disables PCI bus mastering;
**reboot is required for recovery**. Removal with allocations also quarantines
them because allocator-domain teardown is not a proven safe free point. Memory
is deliberately retained rather than assuming `pci_clear_master` drains posted
writes. Ordinary clean reference retirement frees both coherent allocations.

Lifetime basis (Linux 6.1 source audit): `mm/mmap.c:mmap_region` obtains
`get_file(file)` before calling the driver's mmap; VMA teardown calls allocator
`vm_ops->close` before `fput(vm_file)`. VMA split/copy retain file references.
`drivers/dma-buf/dma-buf.c:dma_buf_mmap_internal` invokes exporter mmap on the
DMA-BUF file; `dma_buf_mmap` sets `vm_file` to `dmabuf->file` before invoking it.
The helper verifies the expected backing file before and after allocator mmap.
Consequently close(fd) while mapped cannot invoke the final owner/export release;
allocator callbacks run while the generation remains pinned. Blocking explicit
UNMAP after any mapping prevents freeing backing RAM while VMA references exist,
without intercepting allocator open/close/access/fault semantics.

RK3568 failure audit: the preceding source returned `EOPNOTSUPP` whenever
successful `dma_mmap_coherent` installed any `vm_ops`. ARM64 may install its
physical-access callbacks, so this rejected valid mappings before the constructor
could read the FPGA signature. The source fix removes that rejection. Target
rebuild and runtime validation of this revision remain the parent's responsibility.

Transfer submission is serialized until MSI completion. A leased input range
rejects overlapping F2H writes with `EBUSY`; disjoint metadata/display reads and
H2F control writes remain possible. No handler starts an autonomous DMA.
No faultable usercopy, DMA-BUF export/final put or fd publication occurs under
the global driver mutex, avoiding the mmap-lock inversion during publication.

## Limits that remain for rollout

Leases are a **cooperative userspace protocol**, not implicit DMA fences. The
kernel cannot determine whether RKNN has finished when END is asserted, prevent
a writable legacy CPU mmap from modifying input while leased, or confine an
importer given a full-allocation fd to the intended slot. All participants must
obey slot ownership; trust the exclusive viewer/client and restrict node access.
DMA-BUF poll/reservation fences do not implement this protocol. RKNN buffer sync
calls must be balanced outside an active lease if they invoke CPU access hooks.

The local check does not prove target SG/IOMMU support, RKNN layout/offset parity,
PCI completion on the flashed board, or performance. The exact UINT8 input layout
must still match model/runtime requirements; application-copy removal does not
prove the absence of internal RKNN conversion. The one-second transfer timeout
is conservative and has no retry path after uncertain completion. An MMIO access
itself can stall in broken hardware before the completion timeout is reached.
Parent owns matching-target compilation, deployment and recovery, as requested.
