# Open-source references for the six-camera RK3568 surround viewer

Verified against GitHub repository metadata, documentation, source files and license texts during this research. This note contains recommendations, not board measurements or a claim that calibration is available. No third-party implementation or assets were copied into the application by this research task.

## Recommendation

Implement the independent C++/Qt5/OpenCV application with two distinct projections: (1) a mouse-drag panorama viewer with yaw/pitch and continuous transitions across adjacent camera sectors; (2) a ground-plane bird's-eye compositor. Start with precomputed inverse sampling maps, valid-pixel masks and narrow feathered seams. Render using the available Mali OpenGL ES context, with a CPU OpenCV remap fallback. No neural network is needed.

Calibration is currently unavailable. The initial modes must display `UNCALIBRATED / APPROXIMATE` when showing live images with assumed geometry, or `DEMO` when showing generated samples. Smooth sector blending is achievable; verified geometric continuity and metric ground distances require actual camera data and calibration. Do not label synthetic geometry or borrowed calibration as calibrated.

## Four verified references

| Reference | Verified license | Relevant techniques | RK3568 applicability |
| --- | --- | --- | --- |
| [neozhaoliang/surround-view-system-introduction](https://github.com/neozhaoliang/surround-view-system-introduction) | [MIT, copyright Zhao Liang](https://github.com/neozhaoliang/surround-view-system-introduction/blob/master/LICENSE) | Fisheye calibration, undistortion, four manually selected ground points per camera, homography, spatial feathering, overlap brightness compensation, processing threads | Best clear reference for the bird's-eye workflow. Python/OpenCV/PyQt5 implementation; independently implement its mathematical pipeline in C++. Four-camera geometry must become six-camera geometry. |
| [SokratG/Surround-View](https://github.com/SokratG/Surround-View) | [MIT, copyright Sokrat Gasparyan](https://github.com/SokratG/Surround-View/blob/master/LICENSE) | C++14/OpenCV, intrinsic and rotation estimation, seam masks, precomputed warp maps, CUDA multiband blending, gain compensation, 3D bowl mesh, GLSL rendering | Useful architecture and 3D-view reference. Jetson TX2 CUDA and GLES 3.2 implementation is not a direct Mali/ES2 port; rewrite remapping/blending and shader interfaces for the actual context. |
| [opencv/opencv, 4.x](https://github.com/opencv/opencv/tree/4.x) | [Apache-2.0 on current 4.x](https://github.com/opencv/opencv/blob/4.x/LICENSE) | Fisheye models, homographies, remap, spherical/cylindrical warpers, feather and multiband blending, seam finding, exposure compensation | Primary C++ algorithm dependency/reference. Check the license of the precise board OpenCV release; versions before 4.5 use the older BSD license. CPU APIs are portable; CUDA APIs are not available on Mali. |
| [facebookarchive/Surround360](https://github.com/facebookarchive/Surround360) | [Rendering software: BSD three-clause text](https://github.com/facebookarchive/Surround360/blob/master/surround360_render/LICENSE_render.md); repository components have different licenses | Calibrated camera-rig representation, intrinsic/extrinsic calibration, color/vignetting correction, stereo 360 rendering | Archived research reference for calibrated panorama/VR geometry. Its large capture/render workflow is unsuitable as the small real-time board tool. Reference the rendering component specifically, rather than describing every repository component as BSD. |

### 1. Zhao Liang: practical bird's-eye calibration

Read [English documentation](https://github.com/neozhaoliang/surround-view-system-introduction/blob/master/doc/en.md), [projection-point tool](https://github.com/neozhaoliang/surround-view-system-introduction/blob/master/run_get_projection_maps.py), and [birdview compositor](https://github.com/neozhaoliang/surround-view-system-introduction/blob/master/surround_view/birdview.py).

The documented sequence is intrinsic fisheye calibration -> undistortion -> four corresponding ground points -> perspective transform -> overlap weight masks -> brightness/color adjustment -> live composition. The documentation describes a 640x480 four-USB-camera example and a different CSI setup on AGX Xavier. Reported performance belongs to those setups, not RK3568. Its notes explicitly discuss ghosting and lookup-map optimization. Preserve bilinear interpolation when combining maps; do not discard OpenCV's fractional interpolation map if using fixed-point remap.

### 2. Sokrat Gasparyan: panorama plus bowl rendering

Read [README and related paper citation](https://github.com/SokratG/Surround-View/blob/master/README.md), [SVStitcher.cpp](https://github.com/SokratG/Surround-View/blob/master/src/SVStitcher.cpp), and [surround fragment shader](https://github.com/SokratG/Surround-View/blob/master/shaders/surroundfrag.glsl).

The inspected stitcher estimates or loads camera intrinsics/rotations, derives seam masks and warp maps, feeds a multiband blender and applies gain compensation. The shader is explicitly `#version 320 es`. The README reports approximately 20 fps on its Jetson TX2 setup; this is not an RK3568 benchmark. Its cited paper is **Gasparyan and Vasilianov (2022), “Real-Time 3D Surround View System for Vehicle Based on Panoramic Stitching Image,” Networked Control Systems for Connected and Automated Vehicles, Volume 1, pp. 85-93**. The citation is evidence of the intended architecture, not independent validation of the current source on this board.

A bowl mesh makes a stitched texture inspectable from different virtual viewpoints. It assumes a surface shape; it does not reconstruct the scene's actual 3D geometry. Third-party vehicle models and CUDA-blender dependencies need their own license review if imported. An independently drawn vehicle silhouette avoids asset dependencies.

### 3. OpenCV: portable implementation primitives

Useful actual source links:

- [Fisheye calibration and projection](https://github.com/opencv/opencv/blob/4.x/modules/calib3d/src/fisheye.cpp).
- [Detailed stitching sample](https://github.com/opencv/opencv/blob/4.x/samples/cpp/stitching_detailed.cpp).
- [Feather and multiband blenders](https://github.com/opencv/opencv/blob/4.x/modules/stitching/src/blenders.cpp).
- [Spherical/cylindrical and other warpers](https://github.com/opencv/opencv/blob/4.x/modules/stitching/src/warpers.cpp).

Use `cv::fisheye::calibrate` and `initUndistortRectifyMap` only when the lens is appropriately modeled as fisheye; use the conventional camera/distortion model for conventional lenses. Do not infer the optical model from the 640x480 resolution. Use `getPerspectiveTransform` for exactly four valid correspondences, or `findHomography` with more measured points and outlier handling. A general scene panorama stitcher is not a substitute for ground calibration: vehicle cameras are separated, scenes contain multiple depths, and nearby objects produce parallax.

### 4. Surround360: camera rig and calibration limitations

Read [calibration documentation](https://github.com/facebookarchive/Surround360/blob/master/surround360_render/CALIBRATION.md) and [render workflow](https://github.com/facebookarchive/Surround360/blob/master/surround360_render/RENDER.md). These explicitly require a calibrated camera rig and camera-specific correction data. The repository is archived. Study its separation of rig geometry from color correction; do not import its raw ISP, stereo-render pipeline, sample calibration or hardware assumptions into this tool.

## Six-camera calibration and projection plan

### Ground-plane bird's-eye mode

1. Preserve physical identities: C1/C2 form a same-direction forward stereo module, C3 left, C4 right, C5/C6 a same-direction rear stereo module. These are four directional groups, not six differently oriented cameras. Use one eye per stereo module with a fresh alternate-eye fallback until stereo calibration exists; do not widen angular coverage by assigning opposite yaw offsets to the two eyes. Those labels still do not establish actual FOV, lens distortion or relative stereo R/T.
2. Calibrate each camera's intrinsic matrix and lens distortion from multiple checkerboard/ChArUco captures covering the image at varied poses. Save calibration resolution and crop/resize information; scale intrinsics consistently when the stream resolution changes.
3. Undistort each image. Select at least four non-collinear, well-spread ground landmarks per camera with known coordinates in the **same vehicle ground coordinate system**. For each camera solve the undistorted-image-to-ground homography. Four arbitrary image corners mapped onto a rectangle provide a visual warp, not measured calibration. Four ground points alone do not solve an unknown fisheye distortion model.
4. Define a common ground canvas, vehicle footprint and ground scale. For every destination pixel, inverse-project through the camera homography, then through its lens model to the original distorted image. Precompute this compound map so runtime samples the source once rather than resampling an undistorted intermediate.
5. Build support masks geometrically from map validity, not from image brightness: valid black road pixels must remain valid. Mark unobserved regions as unavailable. Within actual overlap, normalize smooth weights so their sum is one. Weight toward well-resolved image regions and use a narrow feather around a chosen seam.
6. Fit modest gain corrections from valid static overlap samples and smooth gains over time. Avoid saturated pixels and moving objects. Ground-plane geometry aligns the road, while pedestrians, poles and other elevated objects can stretch or double; that is inherent to the plane assumption.

Full metric 3D camera extrinsics are optional for a planar bird's-eye implementation if each camera has an accurate ground homography. A common plane coordinate system and lens calibration are still required. To derive the homographies from a 3D model instead, use calibrated intrinsics plus each camera's rotation/translation and the measured ground plane.

### Mouse-drag 360 mode: angular panorama versus 3D orbit

A panorama viewer can use spherical/equirectangular or cylindrical coordinates. For a virtual view pixel, derive its viewing ray from the virtual camera field of view, apply mouse-controlled yaw/pitch, rotate that ray into each physical camera, project it with the correct lens model, and sample valid sources. Blend neighboring cameras only where their angular coverage overlaps, including the 0/360-degree seam. The actual mounting angles and FOV are required; assumed evenly spaced yaw/FOV is explicitly approximate.

Rotation-only panorama reprojection assumes a common optical center or sufficiently distant scenery. The six cameras are at different positions: camera rotation calibration alone cannot eliminate nearby parallax. For a finite assumed surface, intersect the virtual ray with a ground plane, cylinder, sphere or bowl, then project the intersection point with each camera's **rotation and translation**. This makes the surface geometrically consistent, but objects away from that surface still misalign. Arbitrary 3D orbit requires measured depth or a reconstruction for physically correct novel views; a flat panorama or bowl texture does not supply depth.

For the first live uncalibrated release, provide configurable sector yaw/FOV/crop/mirroring and continuous wraparound feathering as an approximate inspection view. A crossfade between unrelated cameras is a smooth transition, not proof of continuous coverage. Clearly mark coverage gaps and unavailable frames rather than fabricating camera content.

## Blending and RK3568 rendering choices

- **First choice: feathering.** Use static smoothstep/cosine or distance-based weights over valid overlaps; divide the weighted color sum by the valid weight sum. This is inexpensive and works with C++ CPU remap or texture/mesh rendering on GLES2. Invalid/stale cameras contribute zero weight. Guard a zero denominator.
- **Optional upgrade: multiband/Laplacian blending.** Combine Laplacian image pyramids using Gaussian weight pyramids and reconstruct. This helps exposure/low-frequency seam differences, but consumes additional memory and passes and does not fix parallax or moving-object ghosting. Profile first; do not assume Jetson CUDA performance applies to Mali.
- **Use cached maps or meshes.** Fixed bird's-eye geometry is ideal for precomputed inverse maps. On GLES2, mesh UVs or supported packed maps avoid assuming float texture support. Check fragment precision and extensions. Use ES2-compatible shaders (`attribute`/`varying`, `texture2D`, `gl_FragColor`) when the actual context is GLES2; Sokrat's ES3.2 shader is not directly compatible.
- **Limit simultaneous texture samples.** ES2 guarantees at least eight fragment texture units; six camera textures plus six independent map textures exceed that minimum. Use camera meshes in passes, atlases or a precomposed panorama rather than assuming all maps/textures fit in one pass. Query the real context limits.
- **RGB565 input.** Validate stride, byte order and channel order from capture. ES2 supports RGB565 upload through `GL_RGB`/`GL_UNSIGNED_SHORT_5_6_5`; set appropriate unpack alignment and handle padded rows. An RGB888 CPU conversion is a simpler fallback with additional bandwidth. Six tightly packed 640x480 RGB565 frames are 3,686,400 bytes per frame set (about 110.6 MB/s at 30 sets/s before conversion/copy/render overhead); this is a data-volume estimate, not measured throughput.
- **Timestamp-aware capture.** Keep bounded latest-frame buffers, frame timestamps and per-camera age. Selecting temporally close frames improves moving seams; a software thread barrier does not synchronize sensor exposures. Avoid blocking the entire HUD indefinitely on a failed camera.

## Evidence expected from the parent implementation

This research task does not build, deploy, capture or modify the board. The implementation should provide actual build/deploy commands and self-tests, followed by a separate live-capture verification on the target.

Meaningful algorithm self-tests can verify yaw periodicity at 0/360 degrees, known identity/homography sampling, mask/weight normalization, degenerate calibration rejection, RGB565 primary-color conversion, missing-frame behavior and six-source identity routing. Synthetic self-tests verify implementation arithmetic, not real camera calibration.

Live verification should record all six frame dimensions/formats/strides, source identities, timestamps and frame ages; actual GL renderer/version; mode switching and drag continuity; processing/render frame times; and screenshots of both modes with calibration status visible. Metric alignment should be assessed against measured ground landmarks and held-out points after calibration. Keep `SELF-TEST`, `DEMO`, `LIVE`, and `CALIBRATED` as separate facts rather than treating a successful demo as a successful board or geometry test.

## Reuse policy

The recommended implementation can be independently written from documented mathematics and public APIs, with these projects credited as references. If code is copied or adapted, retain the applicable MIT/BSD copyright notices and license text, and comply with the precise OpenCV release's license and dependency notices. Repository-level licenses do not automatically cover third-party models, images, calibration datasets or bundled dependencies. These references support design decisions; none supplies valid calibration for this six-camera vehicle.
