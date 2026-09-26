# Pango PCIe driver fix (2026-09-26)

This directory contains the RK3568 driver source for the FPGA camera DMA path. The tested module is `pango_pci_driver_fixed_20260926.ko`; `pango_pci_driver_baseline.ko` remains available for comparison.

## Changes

- Capture `g_msi.count` before writing `TOTAL_LENGTH` and `CMD` in both host DMA ioctl paths. A completion MSI that arrives immediately after the command can then satisfy the wait.
- Do not clear the shared DMA ownership flag on an idle or MSI timeout. Clearing it while an FPGA transfer remains active can allow a second descriptor to overlap the first. A real missing MSI still needs device recovery.
- Copy user DMA arguments before acquiring the spinlock. On invalid user arguments, release DMA ownership and the ioctl semaphore. Also release the semaphore when the completion wait is interrupted.

## Build and deployment

Build in an isolated directory against the running board's `6.1-rockchip` headers:

```sh
make -C /usr/src/linux-headers-6.1-rockchip M=/path/to/driver modules
```

The deployed module has `vermagic=6.1.99 SMP mod_unload aarch64` and SHA-1 `5e458c94ca0cab1652db6a6a70f4bdc6b4eaa97a`. The source file SHA-256 is `b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72`. The isolated rebuild passed; its byte hash differs because the build path is embedded in the module. Preserve the running module when an exact binary rollback or comparison is needed.

Stop `detview` and wait for its device handles to close before unloading the driver. Verify `lspci -nnk` shows device `0755:0755` with BAR0 8 KiB, BAR1 4 KiB, BAR2 4 KiB before loading this BAR1 driver. A temporary FPGA bitstream exposed only BAR0 64 KiB; with that layout the driver could not probe and starting `detview` caused a kernel Oops. After FPGA reprogramming, verify PCIe enumeration and the driver binding before starting acquisition.

## Validation

The module built against the board headers, loaded, bound to `0002:21:00.0`, and registered three MSI handlers. The YOLO-capable `/root/npu/detview/detview --model crop640` acquired frames at about 32 fps during the initial check. After the final FPGA configuration and restart, the running process remained active, DMA MSI counts increased, and the current boot had no DMA timeout or kernel Oops in `dmesg`. The user separately reported that long-duration observation no longer reproduced the intermittent image pause. The duration and visual result are user observations; they were not captured by an automated test.

Protocol details and RTL mapping are in `fpga/DOC/FPGA_RK3568_传输协议_v1.md`. The driver ABI is in `pango_pci_driver.h` and `fpga/host/detview/pango_dev.h`.
