# CAM5/CAM6 repair and hardware evidence

Final acceptance remains pending the sensor-window experiment. This record distinguishes verified behavior from proposed causes.

The 50K build flow now loads its physical PCF before standalone placement/routing. Exact GPIO locations, electrical properties and dedicated HSST placement are audited, and all placements are checked again after installing timing constraints. The earlier 222104 artifact had incorrect system-clock and SFP control pins and is marked invalid for hardware use.

The production transmitter retains pixel pairing and FIFO read semantics, while adding a lookahead output stage. A redundant control immediately before payload becomes a D-ending guard. Dedicated configured skip pairs occur earlier in redundant blanking, leaving intact controls for receiver phase acquisition. Full-frame regressions compare pixel identity/order against receiver files matching the burned 100H source archive. Hardware success establishes the effect of this transmitter change; the specific physical PCS deletion event has not been measured.

| Artifact | Verified hardware behavior | Remaining limit |
| --- | --- | --- |
| 010300, original TX with sensor bars | CAM5 updates; CAM6 stays invalid; bar boundaries drift 56 pixels | Failed frame and image acceptance |
| 015705, guarded TX with sensor bars | CAM5 29.81fps, CAM6 14.91fps; both 307200 pixels, stable short counts; both 480-row patterns identical with zero edge drift | Bars validate transport/layout, not normal ISP scene borders |
| 023911, guarded TX with normal acquisition | CAM5 29.79fps, CAM6 14.89fps; all six streams update; 81 diagnostics over 41.53 seconds show complete input frames and stable short counts | Two rightmost gray columns remain in normal raw images |
| 033106, horizontal sensor context adjustment | Two-sensor SCCB sequences and final register values verified; hardware build in progress | Programming, complete-frame checks and actual image review pending |

The active sensor-window candidate changes 3811 to 10, 3801 to 80, and 3805 to BF. It expands surrounding input context and adds an ISP horizontal offset while retaining nominal 640x480 output and central view. Output pixels are not cropped, painted or duplicated to conceal the gray edge. Its effective hardware mapping still requires visual review.

Normal-mode acceptance uses one PCIe DMA owner for frame capture and aligned diagnostic reads. A separate simultaneous diagnostic process was removed because available driver sources use shared global DMA buffers. Before/during/after samples and fresh DDR tags jointly establish frame continuity; old unchanged sticky fault snapshots are not interpreted as new failures.

Actual RK3568 X11 screenshots, original XWD files, RGB565 frames, decoded PNGs, hashes, build audits and board reports are retained. Ambient darkness is expected and does not constitute a brightness defect. The viewer is restored after acceptance capture.

Evidence:

- `log/six_colorbar_board_20261003`: failed original-TX colorbar baseline.
- `log/six_guard_board_20261003`: successful guarded-TX colorbar acceptance and real RK screenshot.
- `log/six_normal_guard_board_20261003`: normal acquisition, complete-frame interval and unresolved edge baseline.
- `log/six_margin_board_20261003_033106`: active sensor-window experiment evidence destination.
- `log/cam56_acceptance_checklist_20261003.md`: objective-to-evidence checklist.
- `log/six_repair_20261002.md`: detailed build, programming and verification record.

The most recent verified programmed normal artifact before the active experiment is 023911, SHA256 1df94407f27a81bfa963be9c0e7f89a3d44ef6ac295680d26aafb66884fdcf5e. Successful colorbar rollback artifact 015705 has SHA256 8b2efca59e7a428d25e6ea14b072f0796d68ebe6af6b3b49da82088c4375fe57. The active runner records any subsequent actual programmed hash separately.

Only the connected 50K is being built/programmed. The 100H receiver and vendor IP remain unchanged. Final goal closure requires complete fresh frames and visually normal CAM5/CAM6 images in the real RK3568 display.
