# HDMI full-image YOLO validation — 2026-10-04

RK3568 native build: `/userdata/linaro/detview-hdmifull-src`.
Deployed viewer: `/userdata/detview-hdmifull/detview-hdmifull`, PID 106193.
Command: `--model wb_v4_combo --fullscreen --no-tracking --prefer-hdmifull auto`.

F selects HDMI display and inference across the complete joined C5/C6 image.
The HDMI source is 1920x1080@60, transported as anamorphic 1280x480 RGB565.
Inference restores aspect to 640x360, with total model padding 140 rows above
and below. Detection overlays use the complete 16:9 display rectangle.
Workers for C1-C4 suspend acquisition in HDMI mode and resume after F exits.
The old C1-C4 freshness heuristic was removed: those cameras belong to 100H
and their frame activity cannot identify 50K HDMI/dual-camera selection.
`auto` waits for explicit F selection; `on` starts in HDMI mode.

Validation completed:

- Native `make -j2` succeeded; HDMI selftest and vision selftest passed.
- Screenshot 145457 shows vehicle boxes on the left car, a red SUV crossing
  the center join, and the bus on the right. It is an actual GL framebuffer
  captured by the running viewer's S shortcut, size 1920x1080.
- F exit: screenshot 145616 and capture rates 45/44/26/26/53/52 fps confirm
  the six-camera view and capture resumed; inference source generation 5.
- F re-entry: screenshot 145623, source generation 6, completed inference
  count 1000, per-inference time 45.66 ms, HDMI capture 60/60 fps,
  display submission 33.8 fps, C1-C4 0 fps, all six error counters zero.
- Viewer left running in HDMI mode. Original binary backed up before deployment.

Pairing limitation: latest halves must both advance, belong to the current
generation, have age <=100 ms, and have capture-time skew <=40 ms. Logs show
equal or adjacent C5/C6 tags; this is time-bounded pairing, not guaranteed
source-frame-exact pairing. A moving object at the seam may show temporal
discontinuity. PCIe driver, camview and FPGA images were not changed.

No physical Key1/Key2 automatic display switching is claimed. 50K source
selection and viewer F selection remain separate actions.
