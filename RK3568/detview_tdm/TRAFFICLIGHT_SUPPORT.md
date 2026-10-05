# Trafficlight integration in the isolated source snapshot

The new model is `det-yolov8n-trafficlight-16cls-640x480-rk3568-raw-dfl6-int8.rknn`.
The scanner includes `/root/npu/trafficlight`. Install the package's `names.json`
beside the model as **`<modelPath>.names.json`** (including the `.rknn` suffix).
The scanner reads that sidecar before the generic `yolov8n` classification.
Trafficlight sidecars must match the package's exact 16 strings and order;
invalid or reordered metadata rejects the model. Missing metadata uses the
same exact built-in names. An exact names sidecar also identifies renamed models.

## Input and output contract

RKNN input attributes are queried once at load and cached with each model,
including models in rotation. Supported inputs have batch 1, 3 channels, width
640, and height 640 or 480, with declared NCHW or NHWC layout. The runtime feed
uses RGB uint8 NHWC and `pass_through=0`. Trafficlight requires height 480;
lane models require height 640. Unsupported input sizes fail closed.
`DET_INT8_IN` does not override trafficlight's required uint8 feed.

The production capture/video inference contract remains 640x640. The new
network receives the **central rows `[80,560)`**, exactly 640x480 (921600 bytes),
without resizing. A raw 640x480 fallback is pixel-identical to adding 80 gray
rows at each end and then cropping them. External QImage row stride is respected.
Square models still receive 640x640 (1228800 bytes), retaining the shared-buffer
RGB fast path and the lane mask contract.

Trafficlight outputs are validated at load: six NCHW tensors, exactly one
box64 and one cls16 at each grid 60x80, 30x40, and 15x20. Head index order is
irrelevant. `want_float=1` requests RKNN's real dequantized output values.
DFL has 16 bins; stride is 640/grid-width (8, 16, 32). Class heads always use
sigmoid, including when the first class's sampled values look like probabilities.
NMS is class-aware only for trafficlight, using the UI confidence threshold and
existing IoU threshold 0.45. Trafficlight limits detections to 300 **after** NMS;
other models retain their previous candidate cap and class-agnostic NMS.

Before emitting detections, network boxes return to canonical coordinates:
`x` unchanged, `y += 80`. No second resize or coordinate restoration occurs.

* Camera/video: content originally occupies canonical y=80..560. The existing
  viewer subtracts 80, recovering the original capture coordinates.
* HDMI: content occupies canonical y=140..500 (640x360). Cropping leaves 60 gray
  rows at the top and bottom of the 640x480 network input. Emission adds 80, and
  the existing HDMI viewer subtracts 140. For a 1280x480 display/transport pane,
  `screen_x = network_x*2`, `screen_y = (network_y-60)*(480/360)`.
  The viewer also scales correctly to its 16:9 display pane dimensions.

This decoder is included in the deployed driving demo. See evidence/driving_demo_20261005/VALIDATION.md for native build and runtime verification.

## Stable metadata IDs and UI text

The internal class list, model sidecar, and diagnostic logs retain these raw IDs.
The UI translates only these exact strings:

| ID | Raw package name | UI label |
|---:|---|---|
| 0 | tlr_motor_red | 机动车红灯 |
| 1 | tly_motor_amber | 机动车黄灯 |
| 2 | tlg_motor_green | 机动车绿灯 |
| 3 | tlra_left_red | 左转红灯 |
| 4 | tlya_left_amber | 左转黄灯 |
| 5 | tlga_left_green | 左转绿灯 |
| 6 | tsra_straight_red | 直行红灯 |
| 7 | tsya_straight_amber | 直行黄灯 |
| 8 | tsga_straight_green | 直行绿灯 |
| 9 | trra_right_red | 右转红灯 |
| 10 | trya_right_amber | 右转黄灯 |
| 11 | trga_right_green | 右转绿灯 |
| 12 | tura_uturn_red | 掉头红灯 |
| 13 | tuya_uturn_amber | 掉头黄灯 |
| 14 | tuga_uturn_green | 掉头绿灯 |
| 15 | tln_lamp_off | 信号灯熄灭 |

## Validation

Host check (no Qt/RKNN runtime needed; extracts production decoder methods
verbatim, compiles them with small Qt container adapters, and runs the production
synthetic selftests):

```powershell
python .\trafficlight_decode_hostcheck.py --package 'E:\build\50k_hdmi_switch\trafficlight_import_20261005'
```

The host check verifies metadata equality, exact input byte counts/restoration,
six shuffled output heads, fail-closed shape checks, all three grid strides,
class 15, forced sigmoid, class-aware/same-class suppression, dense duplicate
clusters, and legacy DFL with regmax16/nc1 and regmax8/nc29.

Parent session should compile and run these from its isolated board work directory:

```sh
qmake detview.pro
make -j4
QT_QPA_PLATFORM=offscreen ./detview --trafficlight-selftest
QT_QPA_PLATFORM=offscreen ./detview --dfl-selftest
QT_QPA_PLATFORM=offscreen ./detview --lane-selftest
QT_QPA_PLATFORM=offscreen ./detview --hdmi-selftest
```

`--trafficlight-selftest` additionally uses real QImage preprocessing, stride-aware
raw fallback, every RGB pixel of a patterned crop, square fast-path identity,
non-RGB conversion, camera restoration, and both HDMI halves with 60 network
padding rows and the 1280x480 box transform. It does not initialize RKNN or use
capture hardware. Local Windows validation cannot run these Qt tests because
this host has no Qt SDK; actual NPU/GL acceptance belongs to the parent session.

Load logs report each tensor's dimensions/layout/type/quantization. Trafficlight
logs the input geometry and canonical detection boxes (up to 10) on the first
successful inference and every 20 completed inferences.
