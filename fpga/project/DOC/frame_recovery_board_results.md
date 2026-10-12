# Frame recovery hardware verification

Artifact: bitstream_frame_recovery_20260927_110349/top.sbit

SHA256: A55D465EEF2D26E4A5935C5A0232147BB5DA01A38CE03C6AE0DE8B2E63F10DCF

Programming succeeded. The viewer was restarted (PID 2524 at capture). The board remains on the recovery image; cam3 initializes at 48 MHz and cam1/2 at 84 MHz.

| Camera | PCLK MHz | VSYNC/s | successful frames/s |
|---|---:|---:|---:|
| cam1 | 84.0024 | 44.986 | 0 |
| cam2 | 84.0010 | 44.983 | 0 |
| cam3 | 48.0003 | 25.989 | 25.989 |

cam3 ping/pong temporal RGB mean absolute differences were 2.137 and 1.898. Screenshots show cam3 updating; its inspected raw frame depicts ceiling panels without the previous large horizontal colored bands. A narrow first-column discontinuity remains in the raw-image statistics and has not been accepted as normal. No test-pattern or long-duration qualification has yet been performed. Do not claim full image acceptance.

cam1/cam2 display black and produce zero successful frames. Their second banks are byte-identical across captured samples; partial first-bank changes are not valid successful frames. This is an unresolved failure, not a passing three-camera result. Root cause of rejection (short capture, overflow, SOF handling, etc.) requires further diagnosis; it is not yet established that the sensors themselves are malformed.

Evidence: tp/frame_recovery_evidence/session.log, capture.json, analysis.json, screen1.png and raw RGB565/decoded PNG files. cam3_bank0_1.png was visually inspected.

Implementation timing summary says All Constraints Met; ddrphy_sysclk slow-corner setup WNS is 1.209 ns. External camera data/HREF/VSYNC inputs remain unconstrained in the tool warnings, so timing acceptance is limited to constrained paths.
