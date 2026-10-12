# C3/C4 shared 640x480 recognition

This isolated executable defaults to the C3/C4 shared view. Press F to return to six-camera view; the original installed viewer is preserved.

C3 occupies x=0..319 and C4 x=320..639. All 480 rows and the full original horizontal field are retained. Adjacent source columns are converted from RGB565 by bit replication and rounded-mean filtered into one RGB888 pixel. This is spatial downsampling, not lossless video coding. Objects have half their original aspect ratio.

The first implementation runs on RK3568 after two RAW PCIe DMA transfers. It reduces two inference images to one input but does not halve camera DDR or PCIe traffic. Original RAW pixels are preserved for acquisition.

Pair publication requires both camera sequences to advance, age <=100 ms, skew <=40 ms, and equal current source generation. These checks refer to host DMA completion timestamps and do not establish exposure synchronization. Both camera threads own their latest buffers. Other cameras suspend DMA while the C3/C4 view is active.

The existing virtual-camera 6 inference queue uses one region. Canonical 640x640 padding remains internal for existing consumers; per-model geometry removes exactly 80 top/bottom rows before a rectangular 640x480 RKNN input. Model geometry is queried, not assumed. C3/C4 overlay coordinates use shared-input coordinates; optional detection logs restore x by a factor of two and remove canonical y padding. Seam-crossing boxes are marked and assigned by center; these are not two detections.

Build with the repository build_viewer.py --source <this-directory>. The target is detview_cam34_composite. Run --cam34-selftest and --trafficlight-selftest with QT_QPA_PLATFORM=offscreen. For the board use --model trafficlight --fullscreen --no-tracking --detect-interval-ms 50 --detect-min-ms 50, or the installed 640x480 model selected by name.

Set DETVIEW_CAM34_EVIDENCE_DIR to a writable userdata directory to save the paired RAW snapshots, composite and actual model feed. DETVIEW_CAM34_DETECTION_LOG=1 logs camera ownership and mapped boxes. [cam34-pair] logs monotonically increasing accepted pairs; [stats] reports inference completions; [display-upload] counts fresh per-camera uploads. FPS must exclude startup and use measured durations.
