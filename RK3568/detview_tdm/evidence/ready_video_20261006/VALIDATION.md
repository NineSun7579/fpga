# Existing driving functions: local-video demonstration — 2026-10-06

Scope: retain the existing person/vehicle/crosswalk and 16-class traffic-light
models, three simulated lanes, Auto/Stop/ForcedGo behavior, arrows and alarm.
Lane-marking classification, navigation and new model training were not added.

At first inspection another camera-delay test owned the PCIe device. It was
left untouched. After that test completed the existing HDMI viewer was started,
but its real screenshot showed camera imagery with C5 stale and C6 about41fps.
This cannot be claimed as a valid HDMI intersection input. At the user's request,
the final demonstration uses an existing local road video instead.

Input: `/userdata/linaro/ready_video_samples/trafficlight_demo.mp4`, existing
20-second 640x480,30fps asset. Despite its filename it shows road vehicles; the
observed segment has no applicable traffic-light detections. Its source content
occupies y60..420; explicit `--driving-video-padded480` removes the known gray
padding before normalizing to640x360. Model analysis receives640x480 with60 gray
rows each side; the canonical model input adds80 more rows. Screen detection
mapping subtracts140, matching the existing HDMI geometry.

Build/checks:

- Native make succeeded;128 state checks and the full vision selftest passed.
- Earlier unchanged traffic-light decoder and overlay selftests passed.
- Real local-video GL screenshots show Chinese vehicle boxes aligned with
  vehicle bodies across the image. Video source is labeled in the UI and logs.
- Manual Stop and left/right ForcedGo actions were sent through existing XTest
  keyboard input. Screenshots show the selected green arrow/LED-equivalent dot
  in forced motion, manual stop with dots off, and unknown-signal Auto stop.
- Video loops across its20-second boundary, with advancing video source indices
  and both models completing inference. About29 video frames/s and19 displayed
  new frames/s were observed; model inference about36-40ms in recorded samples.
- `/dev/pango_pci_driver` is not owned by the video viewer.
- Actual video red-stop/green-go/red-alarm are NOT claimed from this asset.
  These branches retain the prior128-check logic validation and labeled synthetic
  overlay evidence. The earlier HDMI green-go screenshots remain valid historical
  evidence, not fresh testing of the current video.

Deployment: `/userdata/detview-driving-demo/detview-driving-demo`.
Launcher: `/userdata/detview-driving-demo/run_driving_demo.sh`.
Final observed PID5136, supervisor5102; default laneStraight, modeAuto.

Launcher native `bash -n` passed. Actual supervised restart was exercised twice:
viewer4225→4987→5136. The second restart had no input arguments and retained
the video path, loop and padding flag. `video_after_restart.png` records the new
process. Supervisor has bounded app-only recovery, exclusive launcher lock and
exact recorded PID/executable/start-time shutdown. No driver/FPGA reload or
boot-time service was installed. Previous executable retained as backup.

Input-loss protection: a missing/stale/asynchronous C5/C6 pair disables both
automatic and forced motion; locally decoded video uses its own freshness check.
Fresh input must re-establish green confirmation. State tests cover lost input,
late reply rejection, forced-go inhibition and recovery.

Commands:

```sh
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh status
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh restart
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh stop
```

Keyboard: Left/Up/Right lane selection; A Auto; X Stop; B ForcedGo; S screenshot.
F switches HDMI/six-view only in FPGA capture mode, not in local-video mode.
