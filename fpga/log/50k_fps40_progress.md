# CAM5/6 capture optimization

## Verified completion

The105717 candidate is programmed and CAM5/6 capture>=40fps is verified.
Current bit SHA256:
0cd5ad2d133b030eeb3e65f4acf968ed121f057a65ae9a0320b9d099b514695b.

Board acceptance30.3515s: both committed frame sequence rates40.393338fps;
all six camera freshness checks pass.81 diagnostic samples per camera show
307200 input pixels, no overflow and zero short-count delta. Both saved raw
frames contain614400bytes; all final8 columns have zero A534/8410 edge
signature. Visually reviewed CAM5/6 native640x480 PNGs and actual1920x1080
RK3568 X11 screenshot: full scene retained; no obvious gray edge or row
misalignment. Expected dark-scene noise remains visible.

Viewer successful full-new-frame reads over~75s with all six workers active:
CAM5:3038 frames/75.191s=40.403772fps;
CAM6:3038 frames/75.215s=40.390879fps.
Both unstable-frame totals0. CAM1/2~45fps; CAM3/4~25.74fps.
GPU new-frame upload median~20fps; display40fps is not achieved or claimed.

Evidence: log/six_fps40_board_20261003_105717/{report.json,
diagnostic_interval.json,normal_frame_metrics.json,viewer_fps.json,
viewer_runtime.txt,cam5.png,cam6.png,rk3568_normal_screen.png}.

Candidate viewer remains running in /root/ov5640/camview_fps_candidate;
formal launcher unchanged. Tested rollback102411 bit remains available.
No100H build/programming or production IP/constraint changes performed.

The entries below record the preceding preparation state.

2026-10-03: Frame-tail guard programmed and measured for30 seconds. Both
CAM5 and CAM6 DDR tag rates29.7837277fps, compared with prior29.8/14.9fps.
Both raw captures614400bytes/307200pixels; last8 columns have no gray-edge
signature. Continuous diagnostics pass; no new short/overflow faults.

Original workflow failed in viewer restore SSH timeout. Viewer was in fact
running(pid17096). Recovery captured and visually reviewed actual1920x1080
X11 screenshot. Six images visible; CAM5/6 full scenes without obvious
edge/row defects. Recovery evidence log/50k_fps_guard_review.json preserves
the original failure separately. On-screen fresh-upload rate remains~20fps.

Guard board bit6547be080a3701d1ded0c66f021dfdaec201d57bcff77b9f6514bfe60a7f78fd.

40fps candidate build launched:
ov5640_sfp480p_test/ov5640_sfp480p_test/bitstream_final_50k_20261003_105717.
Changes relative to tested guard: VTS705->520, exposure ceiling684->499,
and wait for both real rows before transmitting1280 continuous pixels.
Accepted full output/window offsets retained. SCCB normal/colorbar and
merge pixel/phase/VTS520 simulations pass. No IP/constraint/100H changes.

Build runs through project/tools/build_50k_final.ps1. Do not change inputs
while running. On completion execute project/tools/flash_50k_fps40.py;
it requires complete audited build and exact candidate/baseline hashes,
programs PGL50H only, restores viewer, captures full frames/diagnostics and
actual X11 screenshot. Parent must inspect evidence and perform sustained
host actual-frame-read verification;40fps objective is not yet achieved.

Default desktop rendering still~20fps. Current user specifically requests
CAM5/6 capture40fps; do not claim display40fps from input/tag counts.
