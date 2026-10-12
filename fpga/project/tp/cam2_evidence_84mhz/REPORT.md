# Cam2 independent raw capture — current 84 MHz board

Board audit began at board clock 2026-09-27T02:22:31+00:00. No FPGA programming, PDS invocation, RTL edit, SCCB access, or camera-control register write was performed. The 84 MHz identity is the supplied session context; this capture deliberately avoided M01 register reads and did not independently measure PCLK.

## Finding

The left/right discontinuity is already present in independently acquired cam2 RGB565 data, outside camview. It is therefore not introduced solely by Qt scaling or camview's side-by-side composition. Both ping and pong reproduce the same seam. The observations strongly support a raster/stream alignment problem upstream of display; this experiment does not distinguish sensor capture/FIFO/DDR writer alignment from a common PCIe DMA read-path issue.

All six raw frames have their strongest mean horizontal RGB discontinuity between columns 460 and 461 (zero-based). Mean absolute RGB difference there is 37.39–38.18 on a 0–255 scale, compared with median adjacent-column difference 2.27–2.32. This is not a 320/320 half-frame split: the measured partition is approximately 461/179 pixels.

Across all six frames, the original right edge matches the next row's left edge better (mean absolute RGB difference 1.39–2.03) than the same row's left edge (2.79–3.19). This is consistent with an offset in a continuous raster stream, including a row carry, rather than two independent display tiles merely being swapped. Natural-scene correlations are supporting evidence, not proof of the exact underlying hardware fault or correction offset. The top image strip also differs from the main body, so a fixed per-row rotation must not be assumed to completely restore frame alignment.

No left/right correction was applied. A full-frame DMA read remains susceptible to a free-running writer: tag stability does not prove the entire buffer was frozen. Nevertheless four captures have unchanged before/after tags, and all six (both banks) reproduce the same seam. This rules out a Qt-only explanation even without assuming atomic frames.

## Source/deployment audit

- Local `host/camview/main.cpp` and board `/root/ov5640/camview/main.cpp` are byte-identical: 25803 bytes; SHA-256 `0ad536bef8ad3217b8e7472193e1ce38ead5382360740a697f6aa9368b366bb2`.
- `/proc/3563/exe` resolved to `/root/ov5640/camview/camview`; both running and deployed binary SHA-256 are `e5c778b675e7d56f217ef21d02b90cf3282edb8d0e0a7b30cd771d4dce6ccbf9`.
- Deployed ELF BuildID: `1550487aefbefd2486be1aaf9a020fc6521aaf3d`; aarch64, not stripped. Source mtime 2026-09-26 08:37:22 UTC, binary mtime 08:37:39 UTC. These establish source equality and running/deployed binary equality; no reproducible rebuild was done to prove binary/source provenance.
- Active worker path reads 614400 bytes from cam2 `0x00C00000` or `0x00E00000` (lines 166–183). Active composition copies each cam2 row unchanged into the middle camera region (243–248), with RGB16 width 1920 and stride 3840. Qt later scales with KeepAspectRatio (481–483). There is no active horizontal rotation/swap in this path.
- The code after `#if 0` at line 267 is disabled and must not be mistaken for the deployed active acquisition logic. Header comments about ACK/locked buffers do not describe the active code.

## Capture procedure and result

1. Saved before screenshot and source/binary/watchdog copies.
2. Killed `run_camview.sh` first with `pkill -9 -x run_camview.sh`, then killed camview. Verified both absent.
3. Unloaded/reloaded `pango_pci_driver`; verified PCI sysfs driver symlink before any capture ioctl. No PCI remove/rescan and no FPGA reset/programming.
4. One Python process made exactly one device open for that driver load, mapped TX/RX through the established ABI, then used F2H only. No H2F calls. Read ping/pong three times, one full-frame 614400-byte DMA per frame, with 16-byte tags before/after.
5. Closed capture, unloaded/reloaded driver again before camview's new open, verified binding, restarted original watchdog and captured after screenshot.

| Frame | Tag before → after (first little-endian word) | DMA time ms |
|---|---|---:|
| ping_0 | 0x7fcb → 0x7fcd | 5.21 |
| pong_0 | 0x7fcc → 0x7fcc | 5.13 |
| ping_1 | 0x7fdb → 0x7fdb | 10.29 |
| pong_1 | 0x7fda → 0x7fdc | 4.96 |
| ping_2 | 0x7fe9 → 0x7fe9 | 9.02 |
| pong_2 | 0x7fea → 0x7fea | 4.80 |

Final verified process state: watchdog PID 4042; camview PID 4046. Latest log samples show display-loop FPS 52.224–59.880, not sensor-frame-rate measurements. After screenshot reports C1/C2/C3 OK and E1/E2/E3 zero at that moment. Cam2 split persists; cam3 remains visually corrupted as before. Board is restored to viewing with original deployed files.

## Evidence files

- `before.png`, `after.png`: complete screen screenshots (900×506), taken before stop and after restoration; independent frames are not time-synchronized with screenshots.
- `cam2_ping_0/1/2.rgb565`, `cam2_pong_0/1/2.rgb565`: unmodified little-endian RGB565, 640×480, 614400 bytes each.
- Matching `.png`: direct RGB565 decode, no pixel rearrangement.
- `capture.json`: address, byte count, tags, duration, SHA-256 for every raw capture.
- `analysis.json`: measured seam and row-wrap statistics.
- `board_main.cpp`, `local_main.cpp`, `board_camview`, `run_camview.sh`: audit snapshots.
- `session.log`: full remote command output and recovery evidence.
- `sha256.json`: evidence hashes generated before this report was added.
- Tools: `tools/cam2_evidence.py`, `tools/cam2_capture_board.py`, `tools/cam2_analyze_evidence.py`. Existing tool files were backed up to `.py.bak` before edits. Production sources were never edited.

Next investigation should trace capture/FIFO/frame-boundary alignment and validate whole-raster origin with a controlled scene or known pattern configured at initialization. Do not infer an address from camera +0xd0: no such read was used here, and 0x420D is the normal sensor initialization status supplied by the main session.
