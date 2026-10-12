# Private motion host integration

Only this directory is changed. `main.cpp`, `dma_copy.h`, and `camview.pro`
started as copies of `project/host/camview`. The distinct binary name is
`camview_motion_private`. Production host sources, RTL, and deployment are untouched.

Build on the RK3568 later (parent session handles target compilation). Use a
separate build directory with Qt5 qmake and the existing Mali/GLES dependencies:

```sh
src=/absolute/path/project/motion_100h/host/camview
mkdir -p /tmp/camview-motion-private-build
cd /tmp/camview-motion-private-build
qmake "$src/camview.pro"
make -j2
c++ -std=c++17 -Wall -Wextra -pedantic "$src/test_motion_abi.cpp" -o test_motion_abi
./test_motion_abi
```

For a later authorized deployment, copy only the resulting binary to a new
private path, e.g. `/tmp/camview-motion-private/camview_motion_private`. Do not
replace `/usr/local/bin/camview`, modify autostart, or run a second viewer while
the production viewer owns the device. This task does not perform deployment,
connect to the board, or start/stop any viewer. For a separately authorized
exclusive viewer session, enable with `CAMVIEW_MOTION=1`; unset or any other
value keeps motion DMA off. Preserve the production viewer's Qt/display setup.

The same PangoDev and DMA mutex cover probe, capture, all selector writes, ten
single-word reads, and before/after generation verification. RX scratch is
`0x3FE000`, disjoint from six image slots ending at `0x38A000` and the tag scratch
at `0x3FF000`. Each selector write zeroes the entire 16-byte TX packet before
placing its little-endian low word. Register responses use only the low 32 bits
of a 16-byte transfer; no register burst is assumed. UI camera 1..4 maps to
selector camera 0..3. Host motion calls reject selectors >=4 before any I/O.
The six-slot ABI is retained; hardware slots 4/5 are reserved zero records.
All six cameras retain normal video; CAM5/6 have no motion polling or motion
HUD text, including unavailable/invalid status. Capture bit 31 is asserted once, then cleared for all
word selections. MAGIC and 640x480 geometry are probed once; absent/mismatched
registers disable the optional path for this process.

Each CAM1-4 worker polls at most once per second from completion, with initial
160 ms staggering. No DMA occurs on the GUI thread. Existing 2-second,
single-attempt ioctl handling is retained. A 2-second transaction budget is
checked before every ioctl; an in-flight ioctl can extend total lock hold by
one bounded attempt (about 4 seconds worst case plus existing retry delay).
Any I/O failure/budget exhaustion disables motion globally until restart;
generation mismatch rejects that record and allows the next 1 Hz poll. Image
buffers and previous good metadata survive failures. HUD reports unavailable
or stale metadata after failure.

HUD text is included in the existing cache key and changes only with displayed
metadata, not timestamps or every RGB frame. Four staggered 1 Hz updates can
cause up to four full HUD rasterizations/uploads per second, measurable in the
existing `hud_ms`/`paint_ms` logs. Existing per-pane HUD scissors are enlarged
for the second text line; no ROI/bbox graphics or redraw algorithm is added.
RGB565 texture allocation, uploads, shaders and image drawing remain unchanged.
This is Qt/Mali GLES code; there is no CUDA path.

`latest s...` is the motion frame sequence, independent of DDR commit tags; it
must not be interpreted as synchronized with the displayed image. Bbox values
are block coordinates (minX,minY-maxX,maxY), not pixels. Logs include
`motion camera=N seq=... valid=... blocks=... samples=... bbox=... error=... generation=... latest=1 bitmap=...`.
Bitmap is exactly 48 hexadecimal characters: words[9] through words[4], each
eight digits (most significant bitmap word first). Hardware verification can
compare popcount with blocks and bbox with the 16x12 row-major bitmap. Capture
rejects blocks above 192, samples above 19200, inverted valid bboxes, and valid
bbox rows above 11. Popcount/bbox consistency remains a parent hardware-verifier
check. Raw decode bit-mask boundary tests are separate from the valid capture
fixture (49 set bitmap bits, full-grid bbox, 19200 samples).
Reference validity and error are separate flags. The 192 bitmap bits are
retained in metadata but not drawn. Target compile, register reachability,
driver offset semantics, signal timeout behavior and performance remain to be
verified on RK3568 under a separately authorized session. The existing SIGALRM
watchdog is process-wide and remains an inherited limitation.

The standalone test uses the same helper as the viewer and verifies selector
ABI for cameras 0..3 and rejection of 4/5 (and 6) without I/O, all decoded
fields/reserved bits/bitmap ordering, exactly one capture,
10 frozen data reads, stable generation, and preservation of prior metadata
for each of the 23 failed transaction operations, malformed ranges and a torn generation.
