# FPGA DMA to RK3568 hardware copy: unmeasured candidate

The exact RGA RGB565-to-RGB888 preprocessing experiment was slower than CPU.
A same-format RGB565 copy from the FPGA's coherent RX allocation is a different
experiment: current paired diagnostics measure6.3ms CPU per frame in the
uncached pixel copy. Heap-only hardware copy cost is measured below; no PCIe
hardware copy cost or live gain has been measured.

The current loaded driver matches Build ID
`1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`, module SHA256
`0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`.
Retained driver source and header SHA256 are
`b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72`
and `7bb7ee3a4cdb0ad1f7254a8ac40e39aff3a28f4ec96f8f97672e8488115b7ec1`.
Complete source/object/compiler attribution to the loaded module remains missing.

Read-only inspection in `driver_build_prerequisites_readonly.json` now confirms
that `/usr/src/linux-headers-6.1-rockchip` includes generated6.1.99 release and
configuration headers, Module.symvers, modpost and fixdep. CONFIG_DMA_SHARED_BUFFER
and DMA heaps are enabled. The conventional `/lib/modules/6.1.99/build` link is
absent, so compilation must bind the actual header root explicitly. Current
driver source/header were downloaded into `dma_export/retained` and matched the
above pins. This establishes available build prerequisites, not module build,
kernel symbol compatibility, safe lifecycle or hardware import success. A
private exporter candidate is being prepared without replacing the loaded module.
`dma_export/recovery/pango_pci_driver.original.ko` now retains the exact current
217,872-byte module. The read-only privileged capture rechecked both its full
SHA256 and the loaded sysfs Build ID before transfer; the downloaded bytes
matched the same SHA256. This is retained recovery material, not a tested
module reload or approval to skip lifecycle/import validation.

The distinct `pango_dma_candidate` module now compiles in private target build
`3ffc96a5052c414ba81224a97f6159cd`; its frozen source, generated header inputs,
582 compiler dependency hashes, tool hashes and command files are retained.
This rewrite is under independent review. Export/lease commands still return
EOPNOTSUPP because drain and blocking-importer completion proofs are missing.
29 model cases and actual shared-C policy execution pass; these checks do not
execute kernel lifetime callbacks or DMA devices. No module switch occurred.

RGA heap-only same-format experiment `dd71e4cc135c4be7a62a1d198bbd3e8a`
has now passed12 changing complete frames and100 alternating-order paired
copies on the target. Its persistent FD-import helper takes exactly one614400-
byte RGB565640x480 source object, performs synchronous imcopy, brackets the
destination CPU access and copies into ordinary owned CPU memory. Full cost
averaged1.253847ms; cached CPU copy averaged0.317750ms. This is not a transfer
from the PCIe coherent allocation; importer compatibility and safe source leases
for that exporter remain pending. `rga_copy/same_format_copy.h` contains the
reusable helper, and the retained target receipt binds actual SDK/runtime bytes.

Independent review of the first compiled candidate found reachable usercopy/
mmap lock inversion and a64-bit allocation mask inconsistent with its32-bit
command encoder. Dormant export paths also need coherent-allocation alias and
bounce-buffer constraints plus dma-buf core lock ordering fixes. The compiled
prototype is therefore excluded from deployment; revision is in progress while
the original module remains loaded. Source-only model checks and compilation
were insufficient to detect these defects. MSI completion attribution/drain and
post-error recovery remain unverified even after these source fixes.

Repaired candidate build `61732b056e0a4cc0af87a7d0378d4fbc` succeeded against
the same582 kernel dependencies, with26 artifacts checked after download.
Follow-up review found the five prior source issues addressed.37 model checks
and both executed C harnesses pass after explicit unused-parameter annotations.
Export and importer-backend readiness remain false; mapping/synchronization
return EOPNOTSUPP. Module SHA256 is
`3b60a6619bf036c83c86435867149a0ae8528bd45f178c484077d2c4d4eaa3dd`.
No module was loaded. The attempted PCIe simulation subtask was rejected by
automatic tool review before execution and supplies no completion evidence.

Read-only sysfs/config capture `dma_export/backend_hints_readonly.json` identifies
the active RGA2 device as `fdeb0000.rk_rga`, with no external IOMMU group or
`dma-coherent` property exposed there. CONFIG_SWIOTLB is enabled. These hints
do not prove that a particular attachment uses bounce buffers or direct DMA,
and do not authorize streaming cache maintenance on coherent-page aliases.
Backend admission requires actual mapping and synchronization evidence.

The minimally compatible export is one dma-buf view per camera, backed by the
existing4MiB RX allocation. Slot starts are `camera * 0x97000`; exported pixel
length is `0x96000` (150 pages). The next16bytes of commit metadata and shared
metadata scratch `0x3ff000` stay private. Each slot is page aligned. A single
4MiB FD would require verified RGA byte offsets, which the inspected buffer
structure does not expose. Moving slots to make a single image is out of scope.

This needs a separate fixed-width export ioctl, initialized output FD=-1 and
checked return fields. Preserve old MAP/H2F/F2H/UNMAP ABI; the old dispatcher may
return success for unknown commands. Obtain backing pages via `dma_get_sgtable`
on the original allocation/device. Map a bounded slot SG view for the actual
RGA attachment device only through an audited coherent-allocation backend.
Generic streaming mapping/cache maintenance on coherent-page aliases is not
accepted; persistent bouncing mappings also require protection against stale
copyback after slot refill. Current backend admits no mapping. PCIe DMA addresses
cannot be reinterpreted as CPU or RGA physical addresses.

Lifetime is a required part of the driver change. Outstanding exports must pin
the allocation generation and exporter module. UNMAP must reject live exports;
close must defer RX freeing. Another open/release currently resets or frees
global state, so exclusive ownership must cover those operations. Device
removal and outstanding PCIe transactions also require quiescence. Reference
counting an FD alone does not solve these issues.

The current application serializes F2H, verifies the commit tag, unlocks DMA,
then copies. Exactly one worker owns each camera slot; shutdown joins workers
before closing `PangoDev`. A synchronous experiment can import a persistent
pixel FD, perform an identical-format RGA copy to cacheable DMA-heap memory,
sync CPU access, and copy cached bytes into the existing detached QByteArray.
This retains all existing image/snapshot ownership and full-frame input.
Removing that last cached copy would need explicit shared buffer lifetime;
`QByteArray::fromRawData` alone would be unsafe.

PCIe completion must precede RGA access; RGA completion must precede CPU access
or reusing that camera slot. DMA-BUF cache-sync calls are not completion fences.
Shutdown order is worker join, RGA import release, export FD close, mappings
release, driver close. Old `read_img`/`read_npu` paths share RX and must be
proven inactive or non-overlapping in this mode. NPU RAW routing stays intact.

Before any module switch: freeze complete build inputs, compile against matching
generated6.1.99 kernel headers/configuration/Module.symvers, verify exported
symbols and lifecycle checks, and retain the exact current module for recovery.
Acceptance needs actual coherent-slot import, exhaustive byte equality, six-slot
isolation and lifetime checks, copy+sync costs under six-worker load, then
matched120-second successful-inference/new-video measurements. No driver or
FPGA changes were made during this assessment.
