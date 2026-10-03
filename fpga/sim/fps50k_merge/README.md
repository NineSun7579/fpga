# CAM5/6 true 40-fps work

User authorized CAM5 and CAM6 capture optimization to >=40 unique complete
frames/s on 2026-10-03. Only connected PGL50H is being built/programmed; no
100H builds or IP changes. Preserve accepted033106 gray-edge repair and full
640x480 raw image. Do not count repeated lines/images as fresh sensor frames.

Accepted rollback bit: bitstream_final_50k_20261003_033106,
SHA256 99e4a240962915e80c3d9c045a7787e219e346e494f20f9f2478b3605627a384.

First experiment changes only cam2_merge frame-tail timing: wait 6250 output
clocks (100us at62.5MHz) before a64-clock VS pulse. Sensor registers, clocks,
constraints and IP are unchanged. equal_guard.log and phase_guard.log verify
two640x480 source frames per camera with pixel identity, no overflow, no
repeated/black B lines, and exact merged geometry. They model source timing;
they do not measure hardware PCLK.

Receiver tests in ../fps50k_receiver reproduce half-rate CAM6 with real
splitter/CDC/complete camera wrappers and controlled DDR completion latency.
Shared SOF occurs while CAM6 is still writing but CAM5 already finished;
100us drain fixes the modeled case. This is a verified mechanism, not yet
the board root cause. Actual board acceptance is pending.

First guard build: bitstream_final_50k_20261003_102411. Launch metadata:
log/50k_fps_guard_launch.json. Full production build is running through
project/tools/build_50k_final.ps1. Source inputs must remain immutable while
it runs. Upon completion, execute project/tools/flash_50k_fps_guard.py; this
requires complete build status and reuses source/physical/STA/bit hash gates,
PGL50H-only chain check, complete frame capture, diagnostics and X11 screenshot.
Parent must visually review captured images and assess frame rates afterward.

Separate isolated candidates (not active production build):

- ../fps50k_sensor: VTS705->520; exposure ceiling684->499; gray-edge/window
  settings unchanged. Observed29.8fps cadence would scale to40.4fps only if
  timing scales with VTS. Both sensor instances pass complete SCCB bus checks
  twice in normal and color-bar modes. Hardware rate/quality remains untested.
- ../fps50k_real_rows: wait for both real lines before starting an uninterrupted
 1280-pixel row; never synthesize missing B rows. phase5us test passes exact
 pixels. 40-fps/VTS520 stimulus is tested separately. No production edits yet.

Plan after guard acceptance: confirm whether both DDR tag rates become~30fps,
then evaluate real-row merge and VTS520 candidate, full build/STA/physical audit,
programming, sustained complete tagged frames and actual screen review.
If guard does not fix half-rate, investigate input timing instead of assuming
shared initialization implies equal actual sensor clocks.
