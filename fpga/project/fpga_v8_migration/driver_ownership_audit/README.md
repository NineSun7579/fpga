# Read-only driver ownership audit

Evidence was collected without opening `/dev/pango_pci_driver`, issuing ioctls, mapping memory, touching FPGA registers, or changing kernel/device state. The collection scripts use the existing `project/board_ssh.py` connection only for read-only `/proc`, sysfs, modinfo, hashes, and plausible source/module paths.

## Board identity and ownership

`board_evidence.json` contains two snapshots three seconds apart. Both are on boot `d167174d-777b-4f93-bc1d-ea01ffc83a9a`, kernel `6.1.99` aarch64. The sole observed `/dev/pango_pci_driver` owner is PID **149510**, starttime ticks **25632731**, executable `/userdata/detview-hdmifull/detview-hdmifull`, SHA-256 `496acc4ffe4efe12d04629d8864b4bf4596d500d2980ee6ca7598aeb2a8685ae`. It holds fd 16 and two shared mappings, each **4,194,304 bytes**, offsets zero. The same owner and mappings persisted in both snapshots. This is the externally changed latest viewer identity; no historical PID was used as a stop condition.

The module is live with refcount 2. `/sys/module/pango_pci_driver/srcversion` and `version` do not exist; `initstate=live`. `modinfo pango_pci_driver` cannot resolve a module filename because it is not in the module search index. The module's sysfs ELF build-id note is `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`; the existing board file `pango_pci_driver_fixed_20260926.ko` has the same build ID, SHA-256 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`, 217872 bytes, and vermagic `6.1.99 SMP mod_unload aarch64`. This qualifies that disk candidate as the loaded-binary match by build ID; it does not prove that retained source is byte-identical to that binary.

The baseline and `max1`/`max4` disk candidates have build ID `2c7d51342cfb0617636ef45eaf4717da86aa8592` and are not the loaded build. Their distinct hashes are retained in `board_evidence.json` and `local_input_hashes.json`.

## Source and loaded-binary findings

The retained source is hashed as `b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72`; retained header is `7bb7ee3a4cdb0ad1f7254a8ac40e39aff3a28f4ec96f8f97672e8488115b7ec1`. The two known migration source copies are separately hashed. The migration copies match retained header and differ from retained C mainly in timeout/error cleanup edits; exact diffs are saved as `diff_AI_NPU.txt` and `diff_AI_car_pro_npu.txt`. No source path or DWARF source record for the fixed loaded build was available on the board. The fixed ELF has no usable source line table in this audit. Therefore source findings below are qualified as retained-source behavior, with loaded-binary corroboration only where the disassembly proves the same operation.

The fixed loaded-build disassembly confirms the relevant global behavior: `pango_cdev_open` clears the global state counters; `pango_cdev_release` frees both global coherent buffers and clears their pointers; `pango_cdev_mmap` checks requested size against global allocation sizes and calls coherent mapping; `pango_irq_handler0/1/2` share one atomic DMA state and queue camera/NPU work. Exact output is in `003_pango_pci_driver_fixed_20260926_disassembly.txt`; ELF metadata/source breadcrumbs are in `board_evidence.json`.

## Global DMA ownership and completion constraints

In retained source, `dma_info.addr_r` and `dma_info.addr_w`, allocation sizes, `dma_operation`, MSI counters, DMA state, camera/NPU queues, and completion counters are global (`pango_pci_driver.h:231-275`, `pango_pci_driver.c:35-44,364-366`). The map command rejects an already allocated TX or RX global buffer with `-EBUSY` (`pango_pci_driver.c:462-512`); no `-EEXIST` path exists in the retained or migration sources. Existing host code maps two 4 MiB windows (`project/host/detview/pango_dev.h:30-40`). Thus the currently live viewer already occupies the global allocation/mapping namespace; another 4 MiB pair cannot be reserved concurrently through this ABI.

`release` unconditionally frees whichever global buffers exist (`pango_pci_driver.c:998-1010`), regardless of which file allocated them. `open` resets global completion and queue state (`979-995`). This means a benchmark cannot safely overlap the viewer, and all current users must be quiesced at a documented boundary before any reservation attempt. Mappings observed in `/proc/<pid>/maps` prove mappings only; they do not prove allocator ownership or safe reuse.

DMA completion is one global `g_dma_flag` with values 1 ordinary, 2 camera, 3 NPU, and global wait queues/counters (`35-44`, `1165-1207`). IRQ0 atomically clears the state and increments either `g_msi.count`, `g_cam_done`, or `g_npu_done`; camera/NPU IRQs either start work or increment global pending counters (`1210-1254`). Ordinary DMA waits use 120 ms in the retained source, camera/NPU idle waits use 800 ms/120 ms in the retained and migration variants, and MSI waits use 120 ms; camera image completion is 1000 ms and NPU completion is configured as 6000 ms despite the “60s” comment (`546-680`, `777-797`, `824-865`). Timeout paths in the retained source return after `up()` without consistently clearing `g_dma_flag` or quarantining a possibly active engine. The migration diff records the exact timeout/cleanup changes; loaded-binary disassembly confirms the global state machine but does not by itself establish every timeout literal.

Offset arithmetic is unchecked: DMA bus address is formed by adding user `offset_addr` to the global DMA address (`587-590`, `655-657`), while camera and NPU paths add configured offsets (`1108-1123`, `1141-1157`). There is no visible `offset + length <= allocation` check. `mmap` bounds only compare requested mapping size to the global allocation size (`375-407`). The RX mapping changes `vma->vm_pgoff` to zero before mapping (`398-402`), which is an ABI implementation detail to preserve or explicitly revalidate; this audit does not label it a coherent-DMA offset bug without the kernel mapping contract and runtime source provenance.

## Backend prerequisites

Supported by evidence:

1. Establish a quiesced boundary where every current `/dev/pango_pci_driver` fd is closed and no DMA/camera/NPU operation can be pending; the present viewer must be included because it owns the sole observed fd and two 4 MiB mappings.
2. Reserve both global TX/RX allocations as one exclusive session, verify allocation lengths against the planned windows, and reject any second session using the driver’s observed `EBUSY` behavior.
3. Serialize all DMA submissions and completion waits through one backend owner. Treat timeout as a quarantine condition until hardware idle/completion is independently established; do not reuse or free buffers after an ambiguous timeout.
4. Add checked arithmetic for `offset_addr + total_length` against the allocated side and a defined policy for camera/NPU queued work before benchmark ownership begins.

Unproven and requiring a later authorized validation: whether the fixed binary’s source is exactly retained or the fixed migration source; whether the H2F MSI retirement RTL fix is present in the loaded FPGA bitstream; and whether an actual quiesced benchmark window can be obtained from all users. The H2F MSI retirement issue remains a separate RTL-agent item.
