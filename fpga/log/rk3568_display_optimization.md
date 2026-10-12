# RK3568 display optimization, 2026-10-03

Six full 640x480 RGB565 frames, default swap interval 1, desktop compositor retained. The connected 50K bitstream is unchanged.

The user authorized prioritizing this benchmark over detview validation. detview was found owning the same DMA device and stopped. One DMA owner is required for meaningful measurements. Earlier zero-upload results were invalid because the grabber was blocked in driver initialization during conflicting board tasks.

| Candidate | Upload events/s | CPU paint ms | Camera upload calls ms |
|---|---:|---:|---:|
| HUD cache/format/scissor, latest-frame mailbox, uploads before draws | 20.000 | 26.715 | 8.646 |
| Three texture slots per camera | 20.001 | 26.878 | 8.762 |
| Static vertex buffer, one texture slot | 19.998 | 27.050 | 8.732 |
| Filter state cached, draw timing | 19.908 | 27.839 | 9.237 |
| Camera upload before framebuffer clear | 20.000 | 17.616 | 6.260 |
| Same, Qt update idle time 0, exclusive rerun | 20.000 | 17.602 | 6.298 |
| Upload before clear, desktop compositor temporarily off | 25.543 | 18.369 | 4.797 |
| Qt PartialUpdateBlend, default desktop compositor | 20.002 | 7.124 | 6.258 |
| PartialUpdateBlend with swap-driven repaint | 20.001 | 7.173 | 6.278 |

These are averages of logged windows from separate 35-second runs, not a physical scanout measurement. An unrelated compiler was still present during the draw-timing run. No measured upload-rate improvement has been demonstrated.

Actual X11 screenshot `camview_fps_audit_20261003/vbo_screen.png` was read and reviewed: all six panes and labels are visible, with no obvious right-edge gray strip or displaced rows. This is a static visual check.

Stage timing (35 seconds): paint 26.585 ms, camera upload calls 8.592 ms. Logged setup is approximately 17 ms, camera draw calls 0.35 ms, HUD 0.5 ms. Setup includes viewport, clear, and vertex-buffer binding. This suggests a window-buffer wait but does not prove which GL call stalls. A follow-up moves clear after camera uploads to test overlap.

The separate candidate lives at `/root/ov5640/camview_display_optimized/`. The formal startup script has not been replaced. Texture rings remain an optional experiment; one slot is used for subsequent tests.

The `uploadfirstidle0` run is invalid: another detview UI validation stopped camview during measurement. Following the user's priority decision, the identified validator PID 23535 and its launcher PID 23500 were stopped with SIGSTOP, and detview PID 23539 was terminated. These paused validation processes require an explicit coordinated resume later; resuming them while camview runs can recreate the device conflict. The exclusive rerun is `idle0exclusive`.

Exclusive rerun successful complete-frame read rates, from sums of frames divided by sums of seconds: CAM1 44.995, CAM2 45.022, CAM3 25.748, CAM4 25.768, CAM5 40.384, CAM6 40.373 fps. All recorded unstable counters were zero. CPU draw stage now includes clear/wait and averages 10.461 ms, setup 0.062 ms, HUD 0.653 ms. Actual `uploadfirst_screen.png` was reviewed: complete six-pane layout and readable HUD, no obvious gray edge or shifted rows.

The `uploadfirstbypass` run is also invalid: camview was stopped by a concurrent board task and detview PID 24104 appeared. Window bypass effectiveness therefore remains unmeasured. Desktop compositor off was a separate valid comparison; the measurement tool restored its original `true` setting in finally. Its screenshot was reviewed and the six panes remain visible; it does not establish physical output fps.

PartialUpdateBlend moved framebuffer waiting outside paintGL, so the lower paint time is not an equivalent total-render-cost measurement. Upload fps remains 20. This mode is opt-in (`CAMVIEW_OFFSCREEN_DRAW=1`), not the default. A swap-driven repaint is a further opt-in diagnostic (`CAMVIEW_SWAP_DRIVEN=1`).

Final state: restarted the candidate with one texture slot, default NoPartialUpdate, default Qt scheduling, swap interval 1; compositing restored. X11 pause/resume test passed: all six upload rates reached zero while paused and the finally block resumed playback. Formal startup was not changed. The requested 40-fps display target remains unmet; next work needs detailed EGL swap/window-buffer timing and an alternative presentation path, rather than more HUD or vertex micro-optimizations.
