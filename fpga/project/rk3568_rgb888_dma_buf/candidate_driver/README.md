# Isolated 8 MiB RX candidate

Copied from `baseline_1791563289001003700/driver`. This candidate exports an
8 MiB RX DMA-BUF; allocate RX with PZ_MAP selector 1, length 0x800000, then map
8 MiB at the unchanged character-device mmap selector 0x100000. That selector
is not a byte offset within RX. DMA-BUF mmap starts at offset zero.

All ioctl numbers, structure sizes and version 1 stay unchanged. Legacy smaller
PZ_MAP allocations and per-allocation transfer/mmap bounds remain supported;
DMA-BUF export now requires exactly 8 MiB. Old 4 MiB export clients and old BEGIN
offsets require updates. No runtime layout switch is provided. The existing MAP
cap was 4 MiB, not 1 MiB; 0x100000 is only the RX mmap selector. TX's allocation
cap also becomes 8 MiB through the shared constant.

Six camera buffers occupy [0, 6*0x97000) = [0, 0x38a000). Scratch at 0x3ff000
must remain within its existing page below 4 MiB. The input reservation is
[0x400000, 0x52c000), length 1228800. BEGIN/END accept exactly that reservation.
The producer must first complete one contiguous F2H operation at 0x400000 of
either 1228800 bytes or MVP 921600 bytes. Any overlapping subsequent RX write
invalidates readiness. A 921600-byte producer authorizes a consumer to read only
those bytes; it does not initialize the remaining reservation tail.

For MVP 640x480 RGB888, F2H reads converted DDR base + 153600 (rows 80..559 of
640x640 RGB888) into RX offset 0x400000, length 921600. Bind RKNN to DMA-BUF
offset 0x400000, size 921600. BEGIN still reserves 1228800 bytes. Do not bind at
0x425800: importer offset alignment is not assumed. Actual RKNN tensor layout,
stride and offset acceptance still require target validation; use layout-aware
rectangle copying if the importer cannot consume this contiguous crop.

Use one shared userspace mutex for all six capture threads, display/TX DMA and
the producer/consumer sequence: lock, F2H input, BEGIN, synchronous RKNN run and
completion, END, unlock. While BEGIN's token exists, both H2F and F2H return
EBUSY even for disjoint buffers. Display may pause for the roughly 40 ms NPU run.
The kernel mutex serializes individual ioctls but does not reserve the gap
between F2H and BEGIN. END is the client's assertion of consumer completion;
the driver cannot prove NPU completion and installs no implicit fence.

Allocator and transfer address checks retain the 32-bit PCI DMA ceiling.
Exporter/importer SG page count and complete original-page verification now
cover all 8 MiB (2048 pages at 4 KiB). Bounce mappings remain rejected. VMA/file
pinning, permanent UNMAP exclusion after mmap and uncertain-lifetime quarantine
are retained. A larger contiguous coherent allocation may fail with ENOMEM.

Run local arithmetic/source contract checks with `python test_bounds_contract.py`.
They do not prove kernel execution, DMA completion, importer correctness or
hardware safety. No board or FPGA build was performed.

For a later authorized local Linux/WSL ARM64 module build, supply the configured,
prepared build tree and matching Module.symvers for the target kernel:

```sh
KDIR=/path/to/rk3568/kernel CROSS_COMPILE=aarch64-linux-gnu- sh build_arm64.sh
```

The baseline `pango_zc.mod.c` is generated metadata, not source evidence of a
successful build of this candidate; Kbuild regenerates it. No module is installed
or loaded by this script. Windows make/clang alone are insufficient to build
against the RK3568 kernel.
