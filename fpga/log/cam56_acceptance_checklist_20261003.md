CAM5/CAM6 hardware acceptance checklist

Objective: repair both channels and verify normal images using the actual RK3568 six-channel display. Dark ambient lighting is expected. Sensor colorbars are authorized for diagnosis. Current priority is the connected 50K board; no 100H build or programming is scheduled.

Required evidence before goal completion:

- Build: exact bit hash, unchanged input manifest, physical pin/electrical audit, preserved timing constraints, zero failing setup/hold/recovery/removal summaries. Build success alone does not establish camera correctness.
- Programming: scan identifies PGL50H; same audited bit reaches 100%, done=1 and Program success. Close the completion window separately from determining programming success.
- Continuous updates: CAM5 and CAM6 publish changing valid DDR frame tags throughout the monitoring interval; neither stays FFFFFFFF or freezes.
- Frame completeness: each channel reports 307200 input pixels per frame; short-frame counters do not increase; reject overflow or ongoing DMA abort evidence. Old sticky fault snapshots need separate interpretation from new events.
- Image geometry: inspect both RGB565 captures and the real X11 screenshot. Stationary colorbars must have straight, continuous vertical boundaries and correct row layout, without diagonal drift, tearing or missing strips. Yellow-edge analysis supports this check but does not validate the entire palette or all image content.
- Actual display: retain RK3568 X11 root-window XWD, PNG and metadata, with camview running. A stitched raw-frame image alone does not satisfy this requirement.
- Final state: retain the verified board artifact and document whether sensor colorbars remain enabled or normal acquisition has been restored. If normal acquisition is restored, repeat continuity/full-frame checks and capture its actual display.

Baseline 010300: physical/STA gates pass and successful PGL50H programming; CAM5 updates at 29.78fps, CAM6 remains FFFFFFFF/0fps; CAM5 yellow bar drifts from x80 to x24 across 480 rows. Therefore hardware acceptance FAIL. Evidence: log/six_colorbar_board_20261003/report.json, board.jsonl, colorbar_edge_audit.json, rk3568_colorbar_screen.png and original XWD.

Candidate 015705: guard plus dedicated skip opportunities, keeping sensor colorbars. Durable owner is project/tools/finish_guard_015705.py; persistent state log/six_guard_015705_handoff.json. Expected acceptance evidence directory log/six_guard_board_20261003. Pending evidence is not a pass.

Physical CTC deletion remains unproven. Isolated symbol insertion/deletion regressions demonstrate candidate compatibility under the modeled transformations; they do not substitute for the hardware requirements above.

Verified intermediate result 015705: both sensor bars publish continuously (CAM5 29.81fps, CAM6 14.91fps), both counts 307200, short counters stable, 480 identical bar rows and zero edge span. Actual RK3568 guard screenshot inspected; no diagonal drift. Successful bit SHA256 8b2efca59e7a428d25e6ea14b072f0796d68ebe6af6b3b49da82088c4375fe57.

Normal-mode result 023911: bit SHA256 1df94407f27a81bfa963be9c0e7f89a3d44ef6ac295680d26aafb66884fdcf5e. All six channels update; CAM5 29.79fps, CAM6 14.89fps; 81 diagnostic samples spanning 41.53 seconds report 307200 input pixels, unchanged short counts and no overflow. Actual normal X11 screenshots and both raw-derived PNGs inspected. Dark real scenes have no previous diagonal drift, but two bright gray columns at the right edge remain in raw pixels. Therefore final image-quality acceptance remains OPEN despite passing continuity and counts.

Active 033106 experiment: three sensor-window register changes add horizontal ISP context while retaining nominal output dimensions/view. Candidate register map and both-sensor SCCB sequences verified. Postrunner retains columns 632..639 histograms and A534/8410 occurrence counts for both baseline and candidate; parent must inspect actual raw-derived images and the real X11 screen. A changed histogram alone cannot prove valid scene content. Do not crop, paint or repeat edge pixels to pass this check. Preserve full-size captures and keep dark ambient lighting out of the defect criteria.
