# Retained GPU monitor HUD candidate

Only `overlay/src` and this document were changed. `overlay/src` was copied from
the current `host/src`; capture, RAW NPU input, six-model scheduling, tracking,
stereo computation, video input, controller generation rejection, and settings
logic remain unchanged. Baseline `main.cpp` SHA256:
`e244405ac8a22030891c22809a24c106caa75d52b5246fd59b4b25c05d6cc367`.

Enable with `DETVIEW_GPU_HUD=1`. Unset it or use `0` to run the original
synchronous monitor HUD. Settings always use the original synchronous canvas.
Shader compilation/link failure also selects the original renderer and logs it.
This is a GPU HUD optimization, not an asynchronous worker implementation.

## What changed

- Monitor backgrounds, selected-pane borders (2 logical pixels), and detection
  borders (3 logical pixels, matching the source) use solid triangle quads.
  Four non-overlapping strips form each rectangle; GLES line-width limits are
  irrelevant. Full boxes, class/score/track/depth labels, all six camera labels,
  header/footer, video labels, and lane masks remain present.
- Text uses the existing cached QPainter glyph images. These small images become
  cached RGBA premultiplied textures, uploaded only on a cache miss. The monitor
  no longer creates/rasterizes a window-sized image, packs HUD regions, or clears
  and uploads previous box pixels. Geometry is drawn over the latest camera
  framebuffer each paint, so old pixels cannot persist.
- Stereo preview has its own reusable texture and updates independently of HUD
  detection revisions. Preview upload uses `glTexSubImage2D` when dimensions stay
  fixed; null preview is omitted immediately. It is drawn last in its original
  rectangle, over both camera and footer as before.
- All texture uploads and a single orphaned geometry-buffer upload precede camera
  drawing. The camera VBO remains separate; no per-quad buffer overwrite occurs
  while the GPU is drawing. Cached image textures are pruned above 128 entries,
  retaining textures referenced by the current commands.
- The original camera/overlay shader is unchanged. The optional HUD has its own
  shader with solid-color and textured modes, supporting desktop GL and GLES.

## Freshness and invalidation

Commands rebuild on detection/lane revision, camera or layout change, content
geometry/size change, settings return, existing explicit UI invalidation, every
300 ms for rate labels, and the earliest detection/depth deadline. Preview-only
updates do not rebuild commands. The existing controller clears detections,
lane masks and previews on source/model changes and rejects mismatched source
generations; those paths are byte-identical to the baseline.

Each detection border and label carries its deadline. The renderer checks the
current monotonic time immediately before issuing each command, so a texture
upload stall cannot expose expired detector output. Depth labels expire at
`depthCapturedMs + 300`; the next rebuild restores the ordinary label while
keeping a still-valid box. There are no worker jobs, queued snapshots, or delayed
generation completions to accept. Camera, video and inference pixels/data are
never cadence-throttled by this option.

The original monitor QPainter did not enable antialiasing. Solid quads preserve
its colors and logical pen widths, but fractional border edges may round
differently by a pixel. This is not claimed as complete framebuffer pixel parity.
Depth age text retains the original revision/300 ms refresh cadence.

## Verification performed

`python overlay/src/overlay_source_audit.py` passed: all 36 other copied files
are identical; capture/inference prefix, controller suffix, original HUD body,
upload/draw/settings/glyph methods remain unchanged.

`gpu_hud_test_generate.py` extracts the actual production GPU methods, glyph
method, shader initialization, and member declarations into a Qt-only executable
without RKNN/RGA/OpenCV dependencies. MSVC x64 + Qt 5.15.2 compilation passed.
The resulting test passed on both Intel desktop OpenGL and ANGLE GLES via
Direct3D11, with GL error checking and framebuffer pixel checks covering:

- box color/placement, camera interior, selected border, six label backgrounds,
  chrome, and cached glyph conversion/orientation/premultiplied blending;
- independent preview changes/removal, color and vertical orientation, with no
  HUD rebuild;
- expiry during the draw callback, expired box removal, depth expiry retaining
  the box and reverting its label, and clipping oversized boxes to the pane;
- clearing old output/selection, switching selected camera, video mode,
  settings-return invalidation, and lane-mask alpha blending.

Reproduce the portable harness:

```text
python project/per_camera_fps/overlay/src/gpu_hud_test_generate.py <build-dir>
cd <build-dir>
qmake gpu_hud_test.pro
make                         # nmake in an MSVC developer shell on Windows
./gpu_hud_test                # release/gpu_hud_test.exe on Windows
```

Windows ANGLE verification used `QT_OPENGL=angle` for the second run.
Generated binaries/build files are in the system temporary directory, outside
the candidate tree. The production binary was not built against target RKNN/RGA
libraries. No SSH, FPGA build, deployment, or board test was performed.

## Board validation still required

Build `overlay/src/detview.pro` using the parent's normal target toolchain, then
run the same 120-second benchmark with `DETVIEW_GPU_HUD=1 DETVIEW_PERF=1` and the
same source/model/stereo options. Compare with the option unset. Inspect all six
panes, camera/model switches, settings, video, lane mode, depth expiry, preview,
and screenshot output.

The GPU path's `hud_raster` metric now measures command preparation plus glyph
cache misses; `hud_pack` receives no samples. `hud_upload` includes cache-miss
image uploads, preview updates, and the single small geometry-buffer upload;
`hud_draw`, `camera_draw` and paint/new-frame rates remain measured. Rebuild reason
counters remain populated. Camera upload code and its timing remain unchanged.

The previous reported fresh rate (20–21 fps) and HUD raster/upload/packing costs
motivate this change; they are not a measured result for this candidate. Actual
fresh CAM1/2/5/6 >=40 fps and CAM3/4 >=30 fps remain unverified until the parent
runs the board benchmark. The GPU path structurally removes the large CPU HUD
canvas and region packing, but Mali draw/driver cost and camera upload bottlenecks
must be measured before claiming that target.
