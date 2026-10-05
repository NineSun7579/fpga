# HDMI intersection driving simulator validation — 2026-10-05

The running RK3568 viewer joins C5/C6 HDMI into one 16:9 image and rotates the
trafficlight-16cls and wb_v4_combo models. Signal color and direction come from
the signal model's exact class IDs. Keyboard controls only simulate ego lane
and movement. This version renders arrows, LED-equivalent indicators and alarm
borders; physical LEDs and real vehicle actuators are not driven.

Native build and deployed paths:

- Sources: `/userdata/linaro/detview-driving-demo-src`.
- Executable: `/userdata/detview-driving-demo/detview-driving-demo`.
- Final PID: 153014, left running in straight-lane Auto mode.
- Arguments: `--driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo`.
- Binary SHA256: `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4`.

Checks passed:

- Native qmake/make; `--driving-selftest` 120 checks.
- `--driving-overlay-selftest`: red stop, stable green straight/left,
  forced red right-turn alarm, and manual stop. The PNGs explicitly identify
  synthetic detection inputs and do not claim real-scene recognition.
- Trafficlight input/decode selftests, HDMI full-image selftest, and complete
  vision selftest passed.
- Actual HDMI screenshot `auto_green_072615.png` shows motor green detections
  (scores approximately 0.42 and 0.83), the simulated vehicle moving, green
  straight arrow and lit LED1.
- Keyboard actions X, Left/A, Right/B and Up/A were sent to the same viewer.
  Logs include all three lane IDs and Auto/Stop/ForcedGo modes. Screenshots
  document manual stop, lane selection and forced movement.
- The first live session recorded 58 green-go state events. No real-scene
  red-alarm event was observed during this session; that branch is verified
  by the state/renderer selftests, including `red_forced_alarm.png`.
- Later real frames show no applicable traffic light; the simulator correctly
  changes to Unknown and parks automatically. Final screenshot
  `final_073211.png` records the running final executable.
- Final observed C5/C6 capture about 57/58 fps, display submission 31.9 fps,
  all six capture error counters zero. Displayed image rate is lower than
  capture/submission rate and must not be reported as 60 fps.

Keyboard: Left/Up/Right selects lane; A Auto; X Stop; B ForcedGo; F HDMI/six
view; S actual GL framebuffer screenshot. Direction-specific signals override
ordinary motor signals. Red stops immediately; auto green requires distinct
captures spanning >=200ms. Confidence threshold 0.4, signal expiry 1200ms.
Unknown/off/amber/conflicting observations do not authorize automatic movement.
ForcedGo under unknown/amber/off shows a warning; under red it raises alarm.

Signal decisions use capture timestamps tied to raw inference replies, before
model-rotation class remapping. Source switches clear prior decisions. No new
PCIe capture owner ran alongside the viewer; FPGA and driver were unchanged.
