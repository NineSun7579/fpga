# Burst credit hardware results: throughput restored, images not accepted

Programmed artifact: bitstream_frame_recovery_20260927_123854/top.sbit

SHA256: 9A7C8EF581D1286938A26C744B87B029967C815DE5E834E450817A54787E3371

Timing summary: All Constraints Met for constrained paths. Slow setup WNS: cam3 9.187 ns at the corrected 48 MHz constraint; ddrphy_sysclk 1.183 ns. External camera input timing remains subject to the previously documented unconstrained-input limitation.

About twenty seconds of register sampling gives cam1/cam2 successful publication rates of 44.995/s, cam3 25.754/s, with zero retained faults and no increments of overflow or short counters on all three cameras. However image acceptance FAILED: screen1.png and the raw decoded images show severe horizontal stripe corruption on cam1/cam2. cam3 displays the ceiling scene and updates without the large stripe pattern.

Offset +30, labeled offered pixels by the diagnostic script, is anomalous on cam1 (1290240) and cam2 (1025980 through 1089537); cam3 reads 307200. These numbers require mapping/wiring/input-valid verification and are not yet accepted as true input pixel counts. The prior diagnostic image gave 307200 on all three cameras.

Ping/pong temporal RGB differences: cam1 2.430/2.522, cam2 18.316/13.281, cam3 1.868/1.869. Differences show changed bytes but do not certify correct live frames; the visible stripe corruption overrides frame-rate-only acceptance.

Evidence: tp/burst_credit_evidence/registers.json, capture.json, analysis.json, session.log, screen0.png, screen1.png and raw RGB565/PNG files. camview restarted (PID 2572 at capture). The board remains on this build during further investigation; cam1/cam2 are NOT fixed.

Continue investigating the anomalous +30 values together with actual pixel-valid, packing and stored-credit wiring. Preserve 84/84/48 MHz and valid-frame error handling. Do not describe the 45/45/26 counter result alone as task completion.

## Read-only repeat after sustained operation

Evidence: tp/credit_readonly_repeat/registers.json and summary.json. Over 30.314144 seconds, cam1 and cam2 each publish 1365 frames (45.0285/s); cam3 publishes 780 (25.7306/s). The corresponding VSYNC deltas match. All retained fault and rejection counters remain zero. cam1 offered count remains exactly 1290240 in all 61 samples; cam2 ranges from 1028123 to 1064978; cam3 remains exactly 307200. Thus the anomaly persists well after startup and does not depend on raw-frame DMA reads in this repeat (register reads only).

No FPGA programming, register writes or SCCB changes were performed. Driver was reloaded for the single diagnostic open; viewer and watchdog were restored (PIDs 3164 and 3160). Counter evidence still does not certify images. Existing capture.json also identifies three raw samples whose tags changed during host reads; exclude those from stable-sample comparisons. Unchanged tags alone do not establish buffer ownership or image correctness.
