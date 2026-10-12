# V7 board validation

User authorized programming and board validation after connecting the board.

SRAM configuration passed on 2026-10-06 13:45. `log/cfg.log` identifies one PG2L100H on USB Cable II, successful `cfg_program`, and DONE=1 on the final scan. No programmer errors were reported. Flash was not modified.

The programmed frozen `validated.sbit` is bound to the accepted V7 artifact by SHA256 `dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`. `receipt.json` retains the manifest and programmer hashes, operation stages and log paths.

This establishes configuration success only. PCIe enumeration, driver ownership, cooperative register identity, camera/motion behavior and physical RAW/DMA correctness remain pending runtime evidence. The original compile-only manifest is retained unchanged; programming is recorded separately here.

Runtime access attempt: `python project/board_ssh.py run ... --sudo` failed during SSH connection to configured RK3568 address 192.168.10.203 with an 8-second connection timeout. No remote command executed and no DMA device was opened. Local `ipconfig` showed WLAN 10.20.200.179/16 and physical Ethernet adapters disconnected. Runtime validation requires the board's reachable address/network connection; it is not certified by the JTAG DONE result.

## Retry and observed runtime fault

SSH retry succeeded at the unchanged IP. RK3568 had rebooted with PCIe probe failure and no driver/device node. Binding the unbound `3c0800000.pcie` to `rk-pcie` restored Gen2 x2 link and enumerated FPGA 0755:0755 at 0002:21:00.0. Loading the board's existing `pango_pci_driver.ko` created the device node. No viewer was running/holding the driver.

Exclusive register probe completed: COOP 0x434f4f50, CAPL 0x4341504c, both version 0x00010000; LAST_ERROR=0; RAW status=0x182 (config ready), bank state=0, accepted generation/count=0. Probe closed after successful completion.

Camera observation retained two snapshots five seconds apart. Tag changes: CAM1/2 46648 to 46873; CAM3/4 26650 to 26779; CAM6 41854 to 42056. CAM5 remained 3127 while unarmed; no ARM/CLAIM/ACK was issued. Eight actual motion records passed independent bitmap/count/bbox consistency and frame-error-bit checks. These finite observations do not certify sustained operation or coherent RAW frame ownership.

Sustained observation FAILED: the next DMA read returned kernel ETIMEDOUT; kernel reports `PCI_DMA_READ Error: Timeout waiting for MSI interrupt [g_msi.count=388, g_dma_flag=0, g_cam_flag=0, g_cam_done=0, g_ack_num=0]`. Runtime observer PID2583 retains its driver FD/mappings and submits no further operations; do not kill it/free buffers or launch another driver client before resolving the uncertain completion boundary. Runtime raw evidence is saved under `runtime/`. Board functionality is NOT fully verified; Flash remains unchanged.
