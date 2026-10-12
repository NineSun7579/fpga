MVP import source only
======================

Base main.cpp SHA256 was verified identical to the active remote copy:
0D203AAAFFA0CF58CC6BC17DAAB60DC1C0CEC39344D837BD289A4A398C7D78A6.
The directory contains source files copied from the traffic-light snapshot, with
generated moc files, objects, Makefiles and applications omitted.

Transfer this source tree to the isolated board work directory and run qmake /
make as usual. No build dependency uses a Windows absolute path. Install these
three model files under /root/npu/mvp:

* MVP_rk3568_int8.rknn — UI name MVP, detection only, six raw DFL tensors.
* MVP_plus_shared_rk3568_fp16.rknn — MVP+ UFLD, detection plus discrete lane points.
* lane_ufldv2_480x640_rk3568_fp16.rknn — UFLDv2, lane points only.

Copy the four files in sidecars/ alongside those model files. To regenerate them
from a delivery: python prepare_sidecars.py /path/to/mvp_import_20261007.
Names and lane sidecars are optional because the exact delivery metadata is
compiled in; an existing inconsistent sidecar rejects the model. Detection IDs
are always 0 person, 1 vehicle, 2 zebra, 3 traffic_light, 4 traffic_sign. These
are coarse detection classes, with no traffic-light colors or traffic16 IDs.

All inputs are RGB uint8 NHWC at 640x480, fed through RKNN mean 0 / std 255;
ImageNet normalization for independent UFLDv2 stays inside its model. The shared
P5 lane head uses the detector input normalization. All outputs request
want_float=1. Runtime logical outputs must be NCHW with the exact raw6/raw10/raw4
shapes; output contracts are checked before rknn_run. Detection heads are paired
by shape so the INT8 box-first/class-last and shared interleaved orders both work.
The last four shared outputs are never considered as detection heads. MVP always
applies class sigmoid and class-aware NMS, preserving the old decoder policy for
other models.

Lane decoding follows the actual delivered mvp_shared_postprocess.py and
train_mvp_lane.py decode_lane executable code: argmax/(grid-1)*(dimension-1).
Both use endpoints (64 row bins, 48 column bins), despite the independent
docstring saying grid centers. Existence ties select absent; localization ties
select the first bin. Rows/columns use the exact pipeline.json/dataset_summary.json
anchors, 24/32 anchors and 8 lane IDs. Rendered rows are circles and columns are
crosses, color by lane ID. No curve is fitted or inferred from boxes.

The transparent point mask is canonical 640x640. Network y is restored by +80;
the renderer reverses camera padding by -80 or HDMI padding by -140 and scales
HDMI's 360 active rows into the displayed pane. Pane clipping hides predictions
in the 60 network-padding rows at either HDMI edge. Both detections and lane
points from a shared inference arrive in one combined signal; raw detections
are immediately displayed with the mask, then pass through existing tracking.
Lane-only results release the scheduler slot without submitting detections.
Instrumentation reports input shape, detection count and lane point count on
the first and each twentieth successful NPU result.

Host checks (production methods extracted verbatim):
python mvp_decode_hostcheck.py --package /path/to/mvp_import_20261007
Includes new point/DFL tests, traffic16 decoding, legacy DFL bins16/bins8 and legacy
lane-mask tests. With --package, synthetic C++ points are compared directly with
both delivered Python reference function bodies (NumPy required, PyTorch not).
The host uses small Qt container/image adapters, not actual Qt rendering.

Board Qt checks before install:
QT_QPA_PLATFORM=offscreen ./detview --mvp-selftest
QT_QPA_PLATFORM=offscreen ./detview --trafficlight-selftest
QT_QPA_PLATFORM=offscreen ./detview --dfl-selftest
QT_QPA_PLATFORM=offscreen ./detview --lane-selftest
QT_QPA_PLATFORM=offscreen ./detview --hdmi-selftest
QT_QPA_PLATFORM=offscreen ./detview --vision-selftest
Retain existing inference-geometry and overlay-refresh checks as appropriate.
Board compilation, NPU execution and visual hardware checks belong to the parent
session; no device or FPGA operations were performed in this source task.
