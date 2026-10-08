# Surround engine

The engine is an original C++17 implementation using Qt Core/Gui image and JSON
types and OpenCV Core/Imgproc. It requires neither a camera device nor a Qt
window. The application owns capture, the mouse-controlled panorama viewport,
HUD text, vehicle overlay, mode switches and presentation timing. All six
physical camera identities remain fixed:

| Camera | Position | Default yaw |
| --- | --- | ---: |
| C1 | Forward stereo eye1 | 0° |
| C2 | Forward stereo eye2 | 0° |
| C3 | Left | -90° |
| C4 | Right | +90° |
| C5 | Rear stereo eye1 | 180° |
| C6 | Rear stereo eye2 | 180° |

The two eyes in each stereo module share a direction. Physical FOV, pitch/roll,
relative stereo pose and ground quads still need measurement. Until stereo
calibration exists, one eye from each group contributes, with C1/C5 preferred
and C2/C6 used for fresh-frame fallback. Stereo images are not mixed as if they
had a common optical center, and do not artificially widen angular coverage.
Every calibration flag defaults to false. A configuration file does not itself
establish calibration. Without measured parameters, display `ProcessResult.status`
on the HUD, especially the **DEMO bird view: uncalibrated, approximate geometry**
message. Default bird output is useful for demonstrating the layout, but its
distances, object sizes and alignment are not measurements.

## API and integration

```cpp
surround::Configuration config;
QString error;
// Optional: keep the defaults and expose error if loading fails.
surround::Configuration loaded;
if (surround::Configuration::load(configPath, loaded, &error)) config = loaded;
surround::Engine engine(config);

surround::FrameInput input;
// Fill images[0..5] and capturedMs[0..5] from the corresponding C1..C6 devices.
// nowMs and capturedMs must use the SAME nonnegative monotonic clock.
auto result = engine.render(input, surround::ViewMode::Panorama, nowMs);
// result.output: owned RGB888 image. result.status: text for the UI HUD.
```

`composePanorama` and `composeBird` return the same status-bearing result.
`panorama(images, capturedMs, nowMs)` and `birdseye(...)` are image-only
convenience methods. `setConfig(config, &error)` validates and builds new maps
before replacing the previous configuration. Invalid construction throws
`std::invalid_argument`; failed `setConfig` preserves the previous engine.

Input is exactly 640×480 per camera. Other QImage formats are converted to
RGB888; wrong dimensions are excluded and reported. QImage scan-line strides
are honored. Results own their pixels, so rendering again cannot overwrite a
previous image. Engine methods require serial access; use one processing thread
or an external mutex, including around configuration changes. The optional
`sequence` and `generation` fields distinguish new captures/device restarts for
exposure filtering. They do not impose hardware synchronization or implement a
frame queue. The caller owns a coherent input snapshot.

## Panorama projection and transitions

The default 1536×480 panorama is equirectangular: columns run from -180° to
+180°, zero yaw is at the middle, and the top and bottom span +35° to -35°
elevation. This is a 360° horizontal surround strip, not a full spherical image.
For pixel center `(u,v)`:

```
yaw       = 2*pi*((u+0.5)/width - 0.5)
elevation = verticalFov*((0.5) - (v+0.5)/height)
worldRay  = (cos(elevation)*sin(yaw), -sin(elevation), cos(elevation)*cos(yaw))
cameraRay = transpose(Ryaw * Rpitch * Rroll) * worldRay
```

The camera has +X right, +Y down and +Z forward. Positive yaw points right;
positive pitch points upward; positive roll rotates the camera's image-right
axis toward world-down at zero yaw/pitch. Rays behind a camera are rejected.
Perspective projection uses measured intrinsics when `intrinsicCalibrated`
is true; otherwise focal length is estimated from `hfovDeg`. OpenCV's pinhole
Brown-Conrady distortion supports 4, 5 or 8 coefficients. The fisheye model uses
the OpenCV equidistant polynomial with four coefficients. An uncalibrated
fisheye uses an estimated equidistant focal length and zero distortion.

Per-camera source maps and smoothstep edge weights are calculated once.
Regions containing contributions become cropped, packed OpenCV bilinear remap
maps. Empty column runs split the rear seam into separate regions. Each frame
only remaps these regions and combines floating-point weighted RGB sums.
Adjacent views therefore blend through overlap as the UI rotates its viewport.
The UI must wrap texture coordinates across the rear seam and interpolate
its mouse yaw/camera selection to provide temporal viewport animation.

Feather blending is not a correspondence-based seam solver. Unmeasured camera
poses and parallax can cause ghosting, especially on nearby upright objects.
Intrinsic and yaw calibration reduce projection errors; they do not eliminate
parallax between physically separate cameras.

## Bird view

The uncalibrated four-direction preview uses slightly overlapping quadrants,
with local far points(-240,-210)/(240,-210) and near points(80,-65)/(-80,-65)
on the512px canvas. This avoids the large diagonal holes left by the earlier
six-sector preview. These values are illustrative, not measured coordinates;
groundCalibrated=true uses the camera's actual configured groundDst instead.

A ground homography maps four source points to four destination points.
Points are ordered TL, TR, BR, BL around the quadrilateral. The source points
refer to the **rectified pinhole image with the same K and 640×480 dimensions**,
even when the physical lens is fisheye. Destination points use actual bird
output pixels, normally 512×512, with the vehicle center at `(256,256)`.

For each output pixel, the inverse homography finds its rectified source pixel.
The lens model then converts that point to the original distorted sensor image.
This fuses rectification and the homography into a single cached remap; it does
not perform a second full-image undistortion on each frame. Only the interior
of each source quad contributes, with smoothstep feathering along the quad and
sensor boundaries. Both source and destination quads must be finite, convex,
ordered, nondegenerate and inside their respective images. Singular homographies
are rejected. A central footprint, scaled from 80×130 pixels at size 512, stays
black for the application's vehicle overlay.

Without `groundCalibrated`, each camera uses a lower-image trapezoid and a
rotated illustrative destination sector. Source points are `(128,280)`,
`(512,280)`, `(630,475)`, `(10,475)`. Destination offsets about the vehicle center
are `(-110,-220)`, `(110,-220)`, `(65,-65)`, `(-65,-65)`, rotated by camera yaw
and scaled with the bird size. They are used regardless of stored ground-point
values while the ground calibration flag is false. Ground warps assume a flat
plane; objects above the ground plane distort even with measured calibration.

## Frame health and brightness

Freshness is 1 through 250 ms by default, fades linearly to zero at 1000 ms,
and expires at or beyond 1000 ms. Missing images, wrong dimensions, negative
clock values and future capture timestamps are excluded. Zero milliseconds is
a valid monotonic timestamp. No historical image is retained inside the engine.
`active`, `ageMs`, status text and the maximum capture-time skew report what
actually participated. An age of -1 denotes missing/invalid input. Hardware
synchronization must be supplied by capture.

The compositor normalizes overlapping fresh samples and attenuates them by
the ratio of active freshness-weighted coverage to configured geometric
coverage. Thus a lone fading camera fades to black, and an excluded camera's
missing coverage also dims shared regions. Uncovered areas remain black.

Optional exposure balancing samples corresponding pixels in panorama overlaps,
rejects dark and saturated luminance, and solves regularized camera log-gains.
Scalar gains preserve color ratios, are clamped to 0.85–1.15, and advance with
a 0.15 low-pass factor only when a capture timestamp, sequence, generation or
active set changes. Panorama and bird output share these gains. It is bounded
brightness matching, not white-balance or photometric calibration. Disable
`exposureBalance` for diagnostic color patterns or exact intensity comparisons.

## JSON configuration

Version 1 accepts optional fields with defaults; present fields must have the
correct type. If present, `cameras` must contain exactly six objects in C1..C6
order. All calibration flags must be explicitly set to true to claim measured
parameters. A true intrinsic flag requires explicit K and D in loaded JSON;
a true ground flag requires explicit source and destination quads; a true yaw
flag requires an explicit yaw angle. Unknown fields are ignored.

The smallest valid file is `{"version":1}`. The following is a partial schema
example; the camera object shown must be repeated with the appropriate identity
and yaw for all six cameras when the `cameras` field is supplied:

```json
{
  "version": 1,
  "panoramaWidth": 1536,
  "panoramaHeight": 480,
  "birdSize": 512,
  "verticalFovDeg": 70,
  "freshMs": 250,
  "staleMs": 1000,
  "exposureBalance": true,
  "cameras": [
    {
      "id": 1,
      "yawDeg": 0,
      "pitchDeg": 0,
      "rollDeg": 0,
      "hfovDeg": 110,
      "lens": "pinhole",
      "intrinsicCalibrated": false,
      "yawCalibrated": false,
      "groundCalibrated": false
    }
  ]
}
```

`K` is a flat nine-number row-major intrinsic matrix, with positive focal lengths
and bottom row `[0,0,1]`. `D` always has eight numbers; `distortionCount` selects
the active 4/5/8 pinhole coefficients or four fisheye coefficients. Pinhole
coefficient order is `[k1,k2,p1,p2,k3,k4,k5,k6]`; fisheye order is
`[k1,k2,k3,k4,0,0,0,0]`. `groundSrc` and `groundDst` are four `[x,y]` pairs.
Saving writes every field through QSaveFile's atomic replacement. A failed
load leaves the caller's existing configuration unchanged, and a missing file
returns an error. It never substitutes or marks calibrated parameters.

Output limits are panorama width 480–3072, height 120–480, and bird size
128–512. These bounds limit allocations; 1536×480/512×512 are the intended
defaults. Maps rebuild on configuration changes, not during normal rendering.
Maps are cropped to camera coverage; output accumulation is proportional to
output size. This implementation makes no RK3568 frame-rate guarantee without
measurement on the deployed build. No GPU, NPU, multiband pyramid or optical
flow is required by the engine.

## CPU self-test

The parent application can invoke `surround::runEngineSelfTest()` for its
`--selftest` option. It returns 0 on success and 1 on failure, and writes PASS/FAIL
messages to stdout. A standalone Linux build with Qt5/OpenCV4 development
packages is:

```sh
g++ -std=c++17 -O2 -fPIC -DSURROUND_ENGINE_SELFTEST_MAIN \
  surround_engine.cpp surround_engine_selftest.cpp \
  $(pkg-config --cflags --libs Qt5Core Qt5Gui opencv4) \
  -o surround_engine_selftest
./surround_engine_selftest
```

Tests exercise four directional groups, same-direction stereo identity and
preferred-eye/fresh alternate-eye selection, default 110° adjacent-sector
overlap and rear wrap continuity, output ownership, exact stale-age fade, missing/expired/future
inputs, capture skew, JSON transactions and round trips, invalid intrinsics and
singular quads, ground projection against OpenCV's perspective reference,
vehicle masking, upward pitch, fisheye optical-center projection and bounded
exposure matching. They use generated color and coordinate-grid images and
temporary JSON files. No capture hardware, SSH or GUI display is involved.

Front C1/C2 both point at0°; rear C5/C6 both point at180°. Their independent
images must not produce wider FOV or simultaneous stereo-color blending. Tests
verify the preferred image at each optical axis and the alternate image when
the preferred eye is missing or old. Actual overlap transitions occur between
front/left/right/rear directional groups; the two eyes of a module do not
constitute adjacent panorama sectors.
