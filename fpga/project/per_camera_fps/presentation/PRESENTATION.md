# Presentation timing candidate

`src/` is a complete copy of `../direct_display/` (that directory is itself the
source root). Only presentation instrumentation is added. Build with the same
RK3568 Qt 5, OpenCV, RKNN and RGA SDK/toolchain as direct_display:

```sh
mkdir -p build
cd build
qmake ../src/detview.pro
make -j4
```

Enable with `DETVIEW_PRESENTATION_TRACE=1` using the parent's existing launch
command and configuration. The default is off. `DETVIEW_PERF=0` does not disable
this trace. There is no additional repaint timer, swap interval change, GL
flush/finish, texture change or capture change. The existing five-second stats
callback calls the trace reporter; it prints only once at least ten seconds
have elapsed. Event-loop delays can make the window longer than ten seconds.

## Reason for measurement

The requested fresh display targets are 40 fps for CAM1/2/5/6 and 30 fps for
CAM3/4. Parent-provided direct-notification board evidence for `build_e86...`
was approximately 24 and 21.7 fresh fps respectively, capture 37 and 25.7 fps,
producer `[panes]` 60 fps, paint 9.625 ms, camera upload 6.748 ms and GUI queue
6.75 ms. Parent reported XRandR 1920x1080 at 60 Hz and requested swap interval
zero. Those are prior observations, not measurements of this candidate. The
window is a top-level `QOpenGLWindow`, so QOpenGLWidget composition signals do
not apply. This candidate does not claim to improve throughput or meet targets.

## Measurements

All event timestamps use one `QElapsedTimer` monotonic nanosecond clock in the
GUI thread. A local scope object starts at entry to `paintGL` and ends after
all other local destructors and existing paint accounting, including early
returns. Existing counts are not changed. New distributions occupy appended
`DisplayPerfWindow::time` stages in a separate trace window.

| Stage | Boundaries | Interpretation |
| --- | --- | --- |
| `swap_after_paint` | paintGL scope exit to entry of existing frameSwapped handler | CPU wall time outside application painting before Qt's swap-completion signal; includes Qt work and possible driver blocking/scheduling |
| `between_paints` | consecutive paintGL entries | Actual application paint cadence, including settings and exposure paints |
| `update_to_paint` | first pending application update request to next paintGL entry | Scheduling/coalescing delay after the earliest request |

The public, nonvirtual `DetView::update()` wrapper records the first pending
request then calls `QOpenGLWindow::update()` exactly once. Later requests before
paint are counted as coalesced without replacing the timestamp. All existing
DetView call sites resolve to this wrapper. Qt internal exposure/resize paints
may lack an application request and then do not produce an update-delay sample.
Calls explicitly through a base-class pointer or qualified base update bypass
the wrapper. Cold first paint does not fabricate a cadence interval; swap
without a completed paint does not fabricate a swap delay. Each completed
paint-end timestamp is consumed once. Anchors and pending state survive report
resets, so an event pair crossing a window boundary is counted in the window
containing its ending event. Quantiles are 0.5 ms bucket upper bounds, and the
overflow bucket uses observed maximum; counts, mean and maximum are also logged.

`[presentation]` prints elapsed time, total paint/swap fps (not fresh camera
fps), update/coalescing counts, unmatched swaps, visibility/exposure, screen
name, logical screen/window size, device pixel ratio and QScreen-reported
refresh rate. GUI CPU time uses `CLOCK_THREAD_CPUTIME_ID`, expressed as ms and
percent of one CPU over the wall-time window. `/proc/self/task/<tid>/status`
provides voluntary and involuntary context-switch deltas. The corresponding
`stat` supplies cumulative user/system CPU ticks and instantaneous thread
state, with `_SC_CLK_TCK` reported. Missing CPU/proc data use -1 or `?`.
CPU sampling/report work is included in the next CPU window; proc snapshots
are taken slightly after the wall-time boundary. These are thread-level
observations, not measurements attributing CPU/blocking to one stage.

`[presentation-context]` prints Qt/platform, native GUI tid, context thread
affinity, GL vendor/renderer/version and requested versus context-reported
GL version/swap interval. The requested format is saved before context
creation. The context interval is Qt's negotiated format metadata. EGL/GLX
driver swap interval is explicitly `unqueried`: neither this metadata nor
QScreen's nominal refresh proves actual vsync, physical scanout timing or
effective driver pacing. `frameSwapped` follows Qt's swapBuffers completion;
it is not a hardware presentation timestamp or a pure GPU-duration measure.

Collect the enabled trace together with existing `[display-perf]`, per-camera
upload/fresh counts and capture evidence in the same run. A large swap-after-
paint gap would justify investigating Qt/driver blocking; a large update delay
would justify investigating event scheduling. Neither finding alone proves a
cause. Preserve the same screen mode, driver environment, HUD and capture
configuration for comparison, and defer optimization until measured evidence
is available. Hardware execution and acceptance remain with the parent session.

## Validation

The portable timing-state selftest checks cold startup, timestamp zero,
coalescing retaining the first request, duplicate/unmatched swaps, paint-start
invalidation of old swap timestamps and event pairs spanning a report reset:

```sh
g++ -std=c++17 -Wall -Wextra -Werror src/presentation_timing_selftest.cpp -o presentation_timing_selftest
./presentation_timing_selftest
```

Local Windows validation with Qt's MinGW 13.1 compiler passed:
`PRESENTATION_TIMING_SELFTEST_PASS`. The full Linux/RK3568 application build and
board run have not been performed in this subagent session; they require the
parent's target SDK/runtime. No SSH or PDS operations were performed.
