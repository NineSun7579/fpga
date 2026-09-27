# 48 MHz initialization deployment results

The new bitstream was programmed successfully using flash_cam3_init48.tcl. Driver binding succeeded and camview was restarted (PID 4320 at verification time). The board remains on this new initialization configuration; it was not restored to 84 MHz for cam3.

| Camera | PCLK MHz | VSYNC/s | completion counter/s |
|---|---:|---:|---:|
| cam1 | 84.0023 | 44.98 | 2.666 |
| cam2 | 84.0015 | 44.97 | 2.665 |
| cam3 | 48.0006 | 25.98 | 2.664 |

The approximately three-second window contains only eight completion increments. These are not proven successful frames.

Raw captures from both banks show very little temporal change: cam3 mean absolute RGB differences are 0.049 and 0.043. After restarting camview, screenshots do change, but screen1.png shows severe stripes, dark/stale regions and discontinuities across the displayed cameras. Neither observation establishes valid real-time output. Image acceptance FAILED.

The old cam2 seam at column 461 cannot be usefully compared under the new globally corrupted state. Largest column differences now occur at 152 and 256 in the two banks; these maxima alone do not establish a new stream offset.

Evidence: tp/init48_evidence/capture.json, analysis.json, session.log, raw RGB565 files and screen0.png/screen1.png.

## Source investigation, not yet a measured hardware diagnosis

axi_dma_write.v aborts after 24-bit watchdog expiry without W progress. It fills only the remaining beats of an accepted burst, waits for W/B obligations, drops the unissued transaction tail, and emits the same data_in_last retirement pulse as normal completion. ov5640_ddr_w_ctrl.v treats dma_done in DATA as frame_done without an error qualifier, increments frame counters and publishes a normal tag. Thus incomplete frame commands can be reported as frames.

ddr_w_arb.v holds the shared owner through B; a source that cannot supply its accepted burst can block the other sources until watchdog recovery. Capture FIFO overflow and residual packing state can propagate missing pixels and frame offsets. The precise initial trigger is unresolved.

The configured AXI clock is approximately 131.25 MHz. A 2^24-cycle timeout is approximately 127.8 ms; three serial timeouts give approximately 2.608 cycles/s, compatible with eight counted retirements in a three-second sample but not proof of actual watchdog activity.

Next repair should distinguish successful completion from abort, suppress publication of invalid frames, and recover packing/FIFO alignment only after outstanding AXI obligations have retired. Verify this with injected short frames and three-source backpressure before another hardware build. Do not simply swap cam2 image halves or reduce timeout to inflate completion rates.
