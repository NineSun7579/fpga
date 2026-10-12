# 100H motion detection acceptance checklist

Goal: implement local CAM1–4 block motion detection and region metadata on
PG2L100H, simulate it, build and program the candidate, and inspect RK3568
screenshots and live display behavior.

| Requirement | Concrete evidence | Current acceptance |
|---|---|---|
| Four local full-resolution passive detector taps | Candidate top/ov5640_top, detector and adapter; exact mapped histories | Four local histories mapped; no CAM5/6 detector instances |
| 16x12 block bitmap, change counts and inclusive bbox | Core regression, four-camera regression, ten-word 320-bit ABI | Pass: 10-phase simulation and accepted live audit; CAM1/2 changed blocks 5/9; bitmap/count/bbox consistent |
| Atomic region output over PCIe | Register and full AXI128 bridge regression; freeze/generation ABI | Pass: simulations and 123 valid advancing live records per local camera |
| Robust frames and stream recovery | Threshold, last sample, short frame, tail, overflow and reset tests | Core/adapter and actual packed-width caller regressions pass |
| Source integrity and protected vendor IP | Baseline hashes, isolated PDS path audit, input manifest | Pass: final programmer validates locked input/route/report/bit provenance; simulation_input_binding.json binds regression RTL; current four files independently rehashed |
| Actual four local BRAM histories with old-data reads | Mapped ADF dump, primitive parameters, connectivity, resource review bound to hashes | Pass: resource_review.json accepted for current four-camera synthesis/map; arithmetic/publication limits retained separately |
| Resources, unchanged pins and PHY | Final mapping/PnR reports, pin and HSST placement audit | Pass: route complete; 112 pins, dedicated PHY connections and HSST placement match baseline |
| Complete final timing | Setup, hold, recovery, removal and pulse-width rows for both corners, exact routed ADF | Pass: both corners all checks positive; minimum slow setup 0.022ns; full report hash verified |
| Candidate bit from audited route | Bit/ADF/report hashes and same-route bit generation | Pass: run212303 top.sbit e3da6e1f…; programmer --check validated |
| Autonomous verified programming | Single PG2L100H JTAG identification and successful hash-bound programming receipt | Pass: SRAM receipt program/run_20261003_232438_0d8973c0; post-operation single target and DONE=1 |
| RK3568 candidate viewer | Isolated optimized target build, ABI test and binary SHA256 | Pass: target build, ABI, running hash and visible X11 window; PID38085 in observation |
| Six normal live images | Candidate screenshot, comparison with retained baseline, 120-second capture/display observation | Pass with dark-scene limit: six live channels; same-scene baseline comparison reproduces CAM3 darkness; motion_four_visual_review.md |
| Real four-camera movement metadata | CAM1–4 advancing sequences, valid comparisons, bitmap/count/bbox consistency and changed regions; CAM5/6 reserved zero | Pass: motion_four_live_audit.json accepted; CAM1/2 movement observed, CAM3/4 valid static results; reserved zeros verified in RTL/regression/map |
| Recovery path retained | Immutable baseline bit, original viewer launch settings and programming/reconnect tools | Pass: baseline SRAM rollback exercised for same-scene comparison; candidate reprogrammed run_20261003_233610_c8c9d9dd; detview restored PID42262, receipt current_viewer_restore_e023736cc5604fa09c1a447335b9311e.json |

Completion requires all pending rows to have direct evidence. A passing manifest,
unit test or target build alone does not establish board operation or display
correctness. Screenshots establish visible content; live observation establishes
capture/update continuity. Metadata is the latest source result, not a DDR frame
tag or proof of physical scan-out without tearing.
