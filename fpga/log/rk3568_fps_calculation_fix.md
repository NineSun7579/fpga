# RK3568 FPS reporting fix

Final validation complete. RK3568 PID18743 runs the corrected candidate;
remote and local main.cpp SHA256 both
4740f42146c783b23bb78a8d7b47fbdbca0edbe16ad4961f9f052267bb1a0566.
Final build/35-second run passed. X11 pause test passed: all six upload
rates report0.000 during pause. Test resumes the viewer in finally.
Recovery runtime confirms upload~20fps and CAM5/6 full reads~40.4fps;
unstable0. Actual X11 screenshot fpsfixfinal_screen.png reviewed: new
Upload FPS/Cx up labels visible and six images present after recovery.
First pause-test attempt selected the Qt1x1 helper and failed focus;
test now targets the full camview window, and the rerun passes.

Physical sensor disconnection was not performed; capture idle/error zero
publication was reviewed in the worker no-frame/error paths.

Worker monotonic measurement windows now start before reading frames. Rate
publication runs on every worker iteration, including no-frame/error paths,
so0.5-second capture windows and5-second audit windows include idle periods
and report zero without dividing by zero. Nanosecond elapsed time replaces
millisecond quantization for capture/upload statistics.

Upload statistics use an independent GUI timer rather than refreshing only
after successful uploads. Five-second empty windows report zero. The timer
requests HUD repaint; paused submissions no longer mutate displayed frames,
so timer repaints preserve paused images.

HUD cache keys use one decimal, matching text. HUD labels are Upload FPS
and C1..C6 up fps. Logs use submit_fps and upload camera instead of ambiguous
camview_fps and present camera. Existing analysis scripts accept old and new
log labels; zero-frame capture windows avoid division by zero.

Original candidate binary/source backed up on RK3568 as camview.before_fpsfix
and main.before_fpsfix.cpp. FPGA bitstream/sensor configuration unchanged.
First build and35-second six-worker runtime check passed, with CAM5/6
complete reads~40.4fps and steady upload~20fps. Final pause behavior change
is built/tested separately; see fpsfixfinal_runtime.txt and fpsfix_pause.txt
in log/camview_fps_audit_20261003 for final evidence.
