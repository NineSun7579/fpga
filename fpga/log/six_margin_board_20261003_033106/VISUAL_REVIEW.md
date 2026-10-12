Observed normal-image margin candidate result, 2026-10-03 03:56:43.

Actual programmed 50K image SHA256:
99e4a240962915e80c3d9c045a7787e219e346e494f20f9f2478b3605627a384

The full build completed with preserved input hashes and physical audit.
Final STA has 112 summary rows, zero failing endpoints, minimum slack 0.104 ns.
Programming scan identified only PGL50H; flash completed with done bit 1.
No vendor or JTAG processes remain active at the post-runner completion check.

The 30-second acceptance passed all six streams. CAM5/6 measured
29.8017/14.9008 fps with no unchanged intervals. Each captured RGB565 frame
contains exactly 614400 bytes / 307200 pixels at 640x480. Across 81 diagnostic
samples spanning 41.61 seconds, input counts remain 307200, short counts
remain 38791/29125, overflow is clear, and no new fault bits appeared.
Existing DMA-abort sticky bits remain set and unchanged; these are not claimed
to be cleared by this experiment.

The baseline's column 638 A534 counts were 388/353 (CAM5/6); column 639
8410 counts were 368/365. Candidate counts are zero for both values throughout
columns 632..639 in both frames. Candidate columns 638/639 now have the same
dark-scene distributions as neighboring columns, dominated by 0020, with
scene-dependent values near the light. Full histograms are in
normal_frame_metrics.json; exact baseline paths and hashes are recorded there.

Read and visually inspected rk3568_normal_screen.png, cam5.png, and cam6.png,
and compared cam5.png with the original normal 023911 cam5.png. Both candidate
views show the same monitor and surrounding scene, retain the nominal field
of view, and have no visible right gray border or obvious main-frame tearing.
The actual X11 screenshot also shows CAM5/6 without the previous gray border.
This is a static captured-scene review; it does not prove all lighting or
motion cases or identify the precise physical origin of the earlier artifact.

Camview was restored. The candidate remains programmed. The normal 023911
rollback remains intact. No 100H inputs, vendor IP, physical constraints, or
capture/merge RTL were edited. Parent final visual review is pending and
objective_complete remains false; no goal was closed automatically.
