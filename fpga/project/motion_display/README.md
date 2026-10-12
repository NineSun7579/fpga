# Isolated HUD upload candidate

The entire `motion_scheduling/host/src` tree was copied once into `host/src`.
Only the copied `main.cpp` and `detview.pro` were changed; new helper/selftest
files were added. The target is `detview` in an isolated hash-pinned directory,
matching the existing build/deployment tooling. Target build and board
performance verification are being performed by the parent session.

The parent investigation reported old average display 26.21 fps versus current
approximately 24 fps, with instantaneous readings near 30. Its raw 5-second
windows showed roughly 304 HUD upload rectangles / 40 MB for old versus
1,249–1,980 rectangles / 95 MB for current, with six full camera frames and
stereo in both. These observations identify a candidate cost, not a proven
code regression: different moving boxes, labels or HUD revisions could account
for the activity difference. The synthetic fixtures below are not captures of
those historical dirty regions.

## Behavior and cost model

Default, unset or `DETVIEW_HUD_BATCH=0` uses the original upload loop, including
per-rectangle `QImage::copy()`. Only the exact string `DETVIEW_HUD_BATCH=1` enables
batching and a persistent `std::vector<unsigned char>` packing buffer. A startup
`[hud-upload]` line records the mode and cost threshold. Both paths remain in
the same application binary for the board A/B comparison.

Batching clips the dirty QRegion to the image bounds and starts with its exact
disjoint partition. It greedily merges the cheapest eligible bounding-box pair
among spatial neighbors, allowing at most `DETVIEW_HUD_CALL_BYTES` extra bytes
per saved upload call (default 2,048 bytes, rounded down to RGBA pixels; invalid
or negative values use the default). This threshold represents an assumed
call/transfer tradeoff, not a measured Mali cost. Zero allows only merges with
no increase in transferred bytes.

Across a rebuild, total tile area, including any duplicate overlapping uploads,
cannot exceed original dirty area plus 25%. This implies the newly covered
area is also bounded. No artificial timing or FPS changes are introduced.
Eight neighbors on each side in both x/y orderings bound candidate generation
to O(n); set/heap work is O(n log n). This is a spatial greedy heuristic, not
an exhaustive globally optimal rectangle cover. It does not merge a box's
entire sparse interior unless the cost and total budget permit it.

Packed rows use the QImage's actual stride and four bytes per RGBA pixel.
Every packed row is a multiple of four bytes, valid under GLES2 unpack alignment
1 (the viewer's existing state) or 4. No GLES3 row-length feature is required.
Buffer capacity is reused; it can grow when a larger tile is first encountered.
Full texture initialization/resize and the full-image upload path are unchanged.

Drawing still uses the original exact QRegion/scissors. Extra uploaded pixels
are copied from the current CPU raster; no assumption that they are transparent
is needed. Previous regions are still cleared and uploaded before drawing.
Camera/inference threads, frame freshness, pane selection, HUD rebuild cadence,
stereo scheduling, controller and raster drawing are unchanged. `HudPack`
measures packing; `HudUpload` includes coalescing and GL calls, so planning
overhead must be included in the performance assessment.

## Local validation

`hud_upload_selftest.cpp` calls the actual production `coalesce()` and
`packedTiles()` helpers. The Qt6 standalone project and the board application's
`--hud-upload-selftest` entry point share this source. The application selftest
returns before creating camera workers or opening DMA, although the application's
existing startup/OpenCV initialization still runs.

Tests cover clipped/outside/empty regions, dirty-pixel coverage, image bounds,
total transfer budget, explicit threshold/budget rejection, 300 seeded random
QRegions, old label and fragmented moving-box fixtures, byte-exact packing from
a padded source stride at nonzero offsets and image edges, and buffer reuse.
An offscreen OpenGL texture upload/readback test uses the production packed
callback, checks the entire texture against the full CPU raster, and verifies
removed-box transparency. It fails rather than skips if GL cannot be created.
The readback fixture must actually coalesce; it includes fragmented current
box/label regions and the previous removed box. Local desktop GL validates pixel
content; it does not establish GLES2/Mali performance or scissor visuals.

Local build: Qt 6.11.1 MinGW 64-bit, GCC 13.1, release `-O2 -Wall -Wextra`.
Renderer: Intel Graphics, desktop OpenGL 4.6. Actual output is recorded in
`local_selftest.log`; the final result is `HUD_UPLOAD_SELFTEST_PASS`.

| Synthetic fixture | Original calls | Batched calls | Original bytes | Batched bytes |
| --- | ---: | ---: | ---: | ---: |
| Labels | 8 | 8 | 930,432 | 930,432 |
| Moving boxes + labels + old boxes | 1,731 | 92 | 1,232,532 | 1,268,960 |

The moving-box fixture adds about 2.96% bytes and saves 94.7% of upload calls.
Its single local planning sample is logged; it is not a board benchmark.
The initial exhaustive-pair implementation cost about 30 ms locally on this
large fixture; the final bounded spatial search reduced that to about 7 ms.
No display FPS improvement is claimed yet.

Run the offline byte audit with `python project/motion_display/audit_source.py`.
`source_audit.json` records hashes for every baseline/candidate source file and
verifies exact camera/inference, controller, raster and overlay-scissor sections.
`source_changes.patch` is the main.cpp diff for review. The audit verifies that
all original main.cpp lines remain byte-identical and in their original order.

Windows helper build, from a new `motion_display/local_build` directory:

```powershell
$env:PATH = 'C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.11.1\mingw_64\bin;' + $env:PATH
qmake ..\host\src\hud_upload_selftest.pro
mingw32-make -j2
.\release\hud_upload_selftest.exe
```

## Remaining board validation (parent session)

Build the copied `host/src/detview.pro` with the board's Qt5/OpenCV/RKNN/RGA
toolchain in a new isolated directory; the output name is `allmotion_display`.
The standalone selftest `.pro` supports Qt5 too. Run
`allmotion_display --hud-upload-selftest` using the board's existing display/GL
environment before testing the viewer. Neither the full application nor Qt5
compatibility has been compiled locally because this machine lacks the board
dependencies. Existing inference/vision/motion selftests remain available.

Compare the same binary with batching off and on, keeping models, six camera
panes, stereo, dimensions, inference cadence and display settings identical.
Repeat comparable or alternating windows. Collect full `[display-perf]` records
and startup `[hud-upload]` mode lines; compare HUD rebuild/revision counts,
upload rectangles/bytes, `HudPack`, `HudUpload`, total paint timing and fresh
paint FPS, alongside camera upload/inference/stereo rates. The unchanged exact
draw region means draw_rects is expected to remain unchanged for identical HUD
activity. Check moving/expired boxes and screenshot appearance for both modes.

Adopt only if total display cost improves with comparable HUD activity and all
frame/inference/stereo and visual checks pass. A synthetic call-count reduction
alone is insufficient. Tune the call-byte estimate only with measured board
call/transfer costs; keep batching off if planning or extra transfer costs erase
the gain. This candidate deliberately makes no change to the deployed tree.
