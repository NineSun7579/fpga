# CAM3/4 SRAM board validation

Candidate SHA256: `a323d6dfad78aff2a4da975bad7c317dc7f6755d56c6a667c08c694893222a3d`.
Only SRAM is authorized. Flash, RTL, generated IP, and existing board_viewer.py
are unchanged. The programmer is the unchanged tools/program_100h_motion.py.

deploy_sram.py prints timestamped stages and retains atomic partial receipts in
log/100h_motion/sram_deploy_*.json. It checks the prepared evidence immediately,
checks the fresh expected PCI identity, saves a private hash-bound full viewer
configuration, closes the exact PID/starttime/hash/window normally, verifies no
DMA/viewer ownership, unloads the driver and removes the endpoint. After SRAM
programmer success it uses the existing guarded reconnect and restarts the exact
saved binary, model, stereo file and full environment. Resume receipts use the
existing board_viewer.py start schema and can be used by its observe action.
No second DMA reader is opened during the viewer observation.

The originally supplied receipt identified PID 73357. It had already exited;
two guarded attempts refused deployment before any hardware mutation. Read-only
inspection found sole owner PID 74291/starttime 17559245, the same bcd96503...
executable, with stereo_pairs_trial.json and DET_BENCH=0. The fresh snapshot
receipt is log/100h_motion/sram_current_viewer_ca167f73dc834c289024843120539faf.json.
It verifies the original source/model manifest and adds the current stereo hash.
The capture limits remain 40,40,30,30,40,40; gating=1, texture ring=1, GPU HUD=1,
swap interval=0, idle time=0, compositor bypass=0, and no LD_PRELOAD.

Runtime acceptance requires six advancing video channels and fresh capture/frame
statistics, no read/EGL errors, preserved inference/stereo operation, and advancing
CAM1–4 motion diagnostics. Rates of 40/30 are runtime targets, not conclusions
from sensor VTS arithmetic or programmer success. CAM5/6 motion records remain
reserved. The deployment observation lasts at least 120 seconds and uses only
logs from the viewer's sole DMA process. Log evidence limits are stated in the
final result; unavailable per-record bitmap/bbox checks must not be claimed.

Local mutation-guard verification: test_deploy_sram.py passes four tests covering
snapshot hash mismatch, exact process mismatch, receipt identity mismatch and an
absent viewer with another DMA owner. Each prevents snapshot write/close/launch.

If deployment fails after PCIe quiescence, inspect the retained stages before
retrying. Reconnect and restore the saved snapshot only after a successful binding.
If candidate video fails, the authorized recovery image is the frozen motion SRAM
run project/motion_100h/run_20261003_212303/top.sbit, SHA256
e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7;
use its completed build status and the same guarded programmer/reconnect workflow.
The programmer's other six-video rollback image is not the motion recovery image.

## Actual result: SRAM succeeded, runtime rejected, recovery blocked

Program receipt:
deploy_evidence_c0l0p_o6/program/run_20261004_153806_f96f8851/receipt.json.
All six gates are true: scan, single target, DONE, program success, final scan,
final single target. Receipt SHA256:
121ef233d1eb59ba721fe68a1d5cfb0ffae6b31bb0117e1ebcb899ddfad186fc.
PCI rescan/driver/node validation succeeded. Exact viewer restart receipt:
log/100h_motion/sram_viewer_resume_42d327de70524b66a67ee62957072c77.json.

The identity-bound 120-second observation was interrupted after approximately
75 seconds when its detview disappeared. Another session launched sole DMA owner
PID 76728/starttime 17681384, executable
/userdata/linaro/detview-calibration-work/build/detview, SHA256
b728e1d8f8d041ed4f8eed429edd09aa9f7ee22cd5891f372a262cadc73c70ae,
with trial-meters stereo config, --stereo-trial-meters, --stereo-scale 0.5 and
--stereo-interval-ms 500. This differs from the saved/restored binary and configuration.
The claimed exclusive board ownership did not hold. This process was left untouched;
no driver unload or SRAM rollback was attempted while it owned DMA.

Fresh retained candidate samples: CAM1/2/5/6 weighted delivered FPS
38.004/38.066/38.010/38.052, tag advance rates about 45.03/45.02/40.38/40.38.
CAM3/4 delivered zero frames and zero tag advancement in all 15 intervals.
All six read_errors and unstable counters were zero. Motion traffic advanced
sequence_changed 123 -> 713 and last_generation 124 -> 714 with errors=0 and
disabled=0. Inference continued at roughly 6.4–10.1 completed FPS, failed=0.
These are partial runtime findings, not six-video or motion-record acceptance.
No root cause for CAM3/4 stall has been established.

Final evidence index and explicit rejected acceptance:
log/100h_motion/sram_runtime_result_42d327de70524b66a67ee62957072c77.json.
The observation, summary, pause, resume, deployment and programmer receipts are
linked there. The actual X11 screenshot (PNG and original XWD) is
log/100h_motion/sram_concurrent_owner_screen_42d327de70524b66a67ee62957072c77.png;
it shows the concurrent calibration viewer, CAM3/4 frozen with zero FPS, and four
other channels active. At final read-only verification the expected PCI endpoint,
driver and node were bound. Candidate remains in SRAM; Flash is untouched.
Recovery to the frozen motion image remains required after resolving the concurrent
viewer owner and closing its exact verified window normally.

## Current calibration recovery workflow (2026-10-04)

The user authorized normal close and exact restoration of the current calibration
viewer. `rollback_current.py` is an independent orchestrator; the original
deployment manifest and `board_viewer.py` remain unchanged. Its current-viewer
whitelist permits `/userdata/linaro/detview-calibration-work/build/detview` and
immutable `100h_performance/build_<16 hex>/build/detview` paths only. Execution
requires the full freshly inspected executable hash. It captures full argv,
environment, cwd, credentials, PID/starttime/boot, unique WM_DELETE window,
model, stereo configuration and current calibration/config file hashes in a
root-private exclusive snapshot. The old complete motion build status is copied
to the operation evidence directory and validated by programmer `--check` before
any viewer close or PCIe change. SRAM execution pins SHA256 `e3da6e1f...e96f7`.

The normal-close, free-owner, driver unload, endpoint removal, guarded SRAM
programmer, reconnect, exact restart and 120-second observation gates use the
existing helpers. No force signal, Flash operation, PDS build or EGL experiment
is performed. Existing calibration files and logs are preserved; restored stdout
uses an exclusive new log. `verify_rollback_current.py` revalidates full process
identity, file hashes, sole ownership and window before and after an XWD capture.
`test_rollback_current.py` passes five local guard checks, including no mutation
on multiple owners, exited identity, wrong executable path or fresh hash mismatch.

### Recovery completed: operation 3fb258dc1b1a492a97df74118ca68ff6

Evidence directory: `log/100h_motion/rollback_current_3fb258dc1b1a492a97df74118ca68ff6/`.
`receipt.json` reports success. The programmer receipt is
`program/run_20261004_160049_c7f3f35d/receipt.json`: SRAM SHA256 is exactly
`e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`,
all six scan/target/DONE/program/final-scan gates true, no stage errors.
PCIe/driver/node reconnect passed. Current calibration PID 77342/starttime
17771700 was normally closed and restored as PID 78680/starttime 17808325,
unchanged executable SHA256
`b728e1d8f8d041ed4f8eed429edd09aa9f7ee22cd5891f372a262cadc73c70ae`.
The full argv includes trial-meters stereo configuration, --stereo-trial-meters,
--stereo-scale 0.5 and --stereo-interval-ms 250. Full environment and calibration
file hashes passed exact verification throughout observation and screenshot.

`observe.json` verifies 121.960 seconds with the same sole DMA owner and pinned
fresh log inode; `observation.log` contains the retained fresh samples.
Each camera has 24 capture samples. Mean reported delivered FPS in CAM1–6 order:
41.736, 41.586, 25.726, 25.713, 39.628, 39.610. Mean tag advance rates:
45.027, 45.033, 25.726, 25.730, 40.385, 40.383. All unstable counters were zero;
120 six-pane samples report have=111111 and all six error counters zero.
Inference completed increased 160 -> 1340, reported completed FPS 8–12 and
failed FPS zero. Stereo computation succeeded 248 times with zero failures.
No error/timeout/EGL_BAD lines occur in the retained observation.

`metrics.json` records recovery_healthy=true and measurement limits. Rates are
arithmetic means of reported capture windows, not weighted interval totals.
`screen.png` and `screen.xwd` show the exact restored calibration window and all
six images, including CAM3/4 with nonzero capture rates. The trial overlay still
states synchronization is unconfirmed; recovery does not validate calibration
accuracy. The original 40/30 optimization remains open. No Flash, existing
calibration/config file, existing viewer script, RTL or generated IP was changed.
