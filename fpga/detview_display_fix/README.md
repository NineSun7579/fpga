# Complete detview display scheduling fix

The installed RK3568 application is `/userdata/detview-hdmifull/detview-hdmifull`.
Its original SHA256 is `3d315e77913fb651b884b817480284d1ad17ad5e794866f4db5c7c50db69cf0b`.
The matching complete source was downloaded from `/userdata/linaro/detview-temporal-work`
into `src/`; original `main.cpp` SHA256 is
`491c72626f5e0fb737cde78583c472c0d6876cf2095ea4a92304d704e4c0c160`.
This preserves the deployed model contracts, temporal filtering, tracking, stereo,
calibration, and existing user interface.

## Change

Set `QT_QPA_UPDATE_IDLE_TIME=0` before constructing `QApplication`, unless the
launcher explicitly provides a value. This removes the additional Qt deferred
update delay from the live camera presentation path. Log the effective update
delay and texture ring at startup. The capture and inference settings are unchanged.

The final candidate also refreshes monitoring rate labels once per second rather
than every 300 ms. Detection/lane/preview revisions, layout changes, and expiration
deadlines still invalidate the overlay immediately. The settings view keeps its
original refresh cadence. `DETVIEW_HUD_STATS_MS=300` restores the earlier periodic
monitoring cadence for comparisons.

Partial RGBA HUD uploads now pack rows into the existing reusable upload buffer,
instead of allocating a separate QImage per region. Both source row stride and
tightly packed GLES2 upload stride are respected.

Display-snapshot publication defaults to a 24 ms minimum interval (formerly
16 ms). This is a shallow owned-frame mailbox operation; capture and the raw
analytics sink remain independent. `DETVIEW_MIN_MS=16` restores the earlier
publication cadence. A faster 8 ms cadence produced more replacements and lower
per-camera update rates, so it was not retained.

Qt 5.15's `QWindow::requestUpdate()` documentation specifies a default 5 ms
deferred-update delay where presentation cannot be driven directly by vsync,
with `QT_QPA_UPDATE_IDLE_TIME` as its override:
https://github.com/qt/qtbase/blob/5.15/src/gui/kernel/qwindow.cpp
The board's installed `libQt5Gui.so.5` contains that environment-variable name.

Model and control changes still invalidate the visible HUD through `setSettings()`;
help visibility now explicitly invalidates it as well.

## Experiments

All experiments use six live cameras and `--model MVP_accuracy_round1 --fullscreen`.
`DET_BENCH=1` records inference and display counters. Actual fresh updates are
counted per camera; window swaps alone do not establish per-camera frame rate.

| Configuration | Measured interval | Average swap fps | C1/C2/C5/C6 fresh update fps |
| --- | ---: | ---: | --- |
| Installed application defaults | 100.915 s | 26.49 | 26.14 / 26.10 / 26.04 / 26.11 |
| Same binary, Qt update idle 0 | 75.803 s | 33.59 | 30.55 / 30.04 / 29.55 / 29.52 |
| Same binary, idle 0, texture ring 3 | 111.203 s | 33.70 | 30.57 / 30.20 / 29.66 / 29.77 |
| Idle 0, HUD 1000 ms, reusable RGBA packing, publish 24 ms (first 16 windows, before screenshot) | 80.601 s | 35.63 | 33.28 / 33.28 / 30.19 / 30.26 |

The scheduling change gives the substantial improvement. The extra texture slots
do not show a meaningful further gain over this sample, so the source retains the
original one-slot default and its existing environment override.

All experimental logs report zero camera instability and zero DMA errors.
These are static indoor scene measurements: motion-triggered inference workload
can differ. The original sample includes an application screenshot; the two
environment experiments do not. Their screenshot-free results should not be
used to claim the whole measured difference is exclusively scheduling overhead.

## Build

On the RK3568, in a separate directory containing `src/`:

```sh
qmake detview.pro
make -j2
```

Requires the installed Qt5, OpenCV4, RKNN runtime, and RGA development libraries.
Raw logs and JSON measurement summaries are stored in `idle0/`, `idle0_ring3/`,
and the neighboring `../detview_full_fps/` directory.

The final binary is installed at the original application path, so existing
launchers receive the fix without extra environment variables. Original backup:
`/userdata/detview-hdmifull/detview-hdmifull.before-display-fix-20261008`.
Final binary SHA256:
`73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100`.
Final main.cpp SHA256:
`08b239abbc02a8f5da6526b9f27d04ce1d3ddf5974f339148850dc0dda5c5c95`.

Final build succeeds without compiler warnings. Board self-tests pass:
vision (including display mailbox/refresh, tracker, DMA, frame metrics and HDMI),
MVP round1 metadata/decoder, and temporal filter (118 checks, zero failures).

## Final installed-binary acceptance

`acceptance/results.json` covers the first 18 full measurement windows after
startup: 90.987 seconds, before the scheduled screenshot at 110 seconds. No
environment performance overrides were supplied; the startup log confirms the
new defaults: idle 0, texture ring 1, publication 24 ms, HUD statistics 1000 ms.

Average actual window swaps: **34.17 fps**. Per-camera fresh upload averages:
C1 31.81, C2 31.63, C3 23.40, C4 23.67, C5 29.74, C6 29.37 fps.
C5/C6 five-second windows still vary (minimum 27.27/26.88); this establishes a
significant improvement over ~26 fps, not guaranteed 30 fps in every window.
The earlier 80-second comparison reached C5/C6 averages 30.19/30.26, which
illustrates workload and timing variation rather than a strict lower bound.

Capture remains approximately 45/45/26/26/40/40 fps. Six-camera errors and
instability remain zero, inference completion averages 3.89/s in this mostly
static scene, maximum logged inference failures are zero, and NPU load at
collection is 10%. No recovery exit or decode error appears in the log.

`acceptance/detview_full.png` is the installed application's own GL screenshot,
taken after the measurement interval. It shows all six correctly separated views;
its instantaneous rate labels are not the averages above. The application remains
running at the original installed path. All local changes are uncommitted.
