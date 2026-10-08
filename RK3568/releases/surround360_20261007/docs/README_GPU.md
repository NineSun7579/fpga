# Direct GPU panorama

`PanoramaRenderer` projects six owned 640x480 capture images directly into the
current viewport. It never composes or uploads a full CPU panorama. The CPU bird
view remains a separate engine path. This renderer is a plain C++ class using
Qt 5 `QOpenGLFunctions` and `QOpenGLShaderProgram`, compatible with OpenGL ES 2.0.

Initialize with the widget's GL context current. For each panorama viewport,
select its framebuffer and viewport, then call:

```cpp
renderer.draw(snapshot, configuration, yawDeg, pitchDeg, hfovDeg,
              float(viewportWidth) / viewportHeight, captureMonotonicMs(), &error);
```

The viewport aspect is width/height. Positive yaw looks right and positive pitch
looks up. HFOV must be greater than zero and at most 175 degrees. Mouse movement
updates yaw/pitch in the caller; drawing another view of the same snapshot does
not upload its unchanged images again. Render the HUD after this call. Call
`release()` with the original context current before context destruction, and
initialize again after context recreation. Methods must run on the context's
thread. The renderer leaves texture unit zero active, unpack alignment four,
array buffer zero and its shader released; blending, depth testing and culling
are disabled. The caller owns framebuffer, viewport, scissor and HUD GL state.

The fragment shader constructs a perspective ray, applies the virtual view
rotation and each physical camera's inverse yaw/pitch/roll, then projects onto
the original sensor. Calibrated K includes skew. Pinhole distortion supports
OpenCV's 4/5/8 coefficient Brown-Conrady rational model; fisheye supports its
four-coefficient equidistant model. Uncalibrated inputs use configured HFOV and
zero distortion. Six explicit sampler calls avoid dynamic ES2 sampler indexing.
Initialization checks for at least six fragment texture units and 64 fragment
uniform vectors and reports shader compiler errors to the caller.

The final rig is four directional groups: C1/C2 same-direction forward stereo,
C3 left, C4 right, C5/C6 same-direction rear stereo. Both stereo eyes are
captured, but only the preferred fresh eye (C1 or C5) or its alternate (C2 or
C6) contributes at a time. An excluded eye contributes neither color nor
geometric weight; it does not artificially widen coverage. Stereo depth/fusion
requires real relative pose and synchronization, which are not supplied.

The application renders the projection into a640×480 framebuffer, then scales
one texture to the screen. Both camera feeds and the projection are480p; the
HUD is rasterized at the monitor width. Screen-size changes do not multiply
the expensive six-camera projection work.

Cross-camera blending uses the engine's 48-source-pixel smooth border feather.
Its denominator includes all cameras' geometric support. Missing, invalid,
future-dated and stale inputs contribute black; old exclusive coverage fades
toward black instead of remaining bright through normalization. Freshness uses
configuration `freshMs`/`staleMs` (defaults 250/1000 ms). Timestamp zero is valid.
Images must have the real 640x480 dimensions. Each source texture is allocated
and initialized black once, then updated only when its sequence or QImage cache
key changes. Normal CaptureSource RGB888 rows upload in one call with unpack
alignment one. Non-RGB888 inputs convert only when changed; unusual external
row strides use row uploads. No time-based reupload occurs.

Optional exposure balancing samples corresponding rays in circular yaw-neighbor
overlaps, including the rear wrap seam. Probe projections rebuild only when
camera geometry changes. At most every 100 ms on a changed snapshot, a small
CPU graph solve compares bilinear grayscale samples, rejecting dark/saturated
values, nonfresh inputs and capture pairs more than 100 ms apart. Age and sample
count reduce confidence. Gains approach the overlap estimates slowly and remain
within 0.85–1.15. This does not match unrelated whole-frame brightness across
different directions. Disabling `exposureBalance` applies unity gains, and a
geometry/freshness/exposure-policy change resets the balancing state.

`uploadBytes()` reports bytes submitted in the latest draw;
`totalUploadBytes()` accumulates upload submissions since GL
initialization (excluding the initial black texture allocation). Six changed
RGB888 images submit 5,529,600 bytes; another yaw/pitch draw of the same snapshot
submits zero. These counters measure submitted bytes, not GPU completion.

The prior RK3568 CPU figures (about 235 ms for 1536x480 panorama composition,
about 50 ms for 512x512 bird view) motivate this path; they are not GPU results.
Validate shader compilation and actual capture-to-display performance on the
board. Compare unchanged-snapshot upload counts, yaw wrap, pitched views,
calibrated distortion, feather seams, and source loss/recovery. This module does
not assert a measured frame rate, calibrated geometry or camera synchronization.

Initial renderer verification: C++17 compilation against Qt 5.15 headers passed with
`-Wall -Wextra`. The generated GLSL ES 1.00 shaders compiled and linked in a
surfaceless Mesa GLES context. Drawing six coincident white sources with 6, 3,
1 and 0 fresh inputs produced grayscale values 255, 128, 42 and 0, respectively,
confirming that stale support remains in the denominator for the original
ungrouped shader fixture. The final stereo-group selection additionally
excludes one eye per front/rear group; use the corrected binocular tests and
final application run for current acceptance. Software GL checks do not measure
Mali performance or validate physical camera calibration.
