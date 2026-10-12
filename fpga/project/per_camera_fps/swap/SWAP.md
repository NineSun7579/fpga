# Swap investigation: opt-in before-map bypass candidate

The parent has satisfied the gate and authorized `swap/src/`, copied from
`presentation/src/`. Parent-supplied evidence: the old PID 68396 window with hint
`1` was closed normally; the new presentation build `0297` window on experiment
`211cb` had the default property absent and swap interval `1`. These identifiers
are parent receipts, not independently queried here. The earlier manual late
hint did not reduce the approximately 24 ms swap gap; the compositor may have
cached its map-time decision. This candidate applies the hint before first map.

The supplied trace (about 24.5 paint fps, 10 ms painting, 24–26 ms from paint end
to `frameSwapped`, 6 ms update delay, GUI CPU about 21%) prioritizes swap/driver/
compositor investigation. These timings do not identify pure GPU duration or
prove physical presentation, effective vsync, or unredirecting. No target build,
hardware run, SSH, PDS operation, launcher change, or throughput claim is made.

## Verified source findings

- [Qt 5.15.8 QPlatformWindow::requestUpdate](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/gui/kernel/qplatformwindow.cpp#L761)
  reads `QT_QPA_UPDATE_IDLE_TIME` and defaults to a precise 5 ms timer. A valid
  value of `0` is accepted. Set it before process startup for a separate,
  single-variable scheduling experiment. Keep the bypass state constant and
  compare `update_to_paint`, paint fps, fresh-camera fps and CPU. This targets
  the update delay, not the measured 24–26 ms swap gap.
- [Qt XCB GL integration selection](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/plugins/platforms/xcb/qxcbconnection.cpp#L1128)
  recognizes `QT_XCB_GL_INTEGRATION=xcb_egl`; it changes plugin preference and
  can fall back. Confirm the actual selected plugin with Qt platform logging;
  requesting this value is not proof of selection or a queue-blocking fix.
- [QXcbEglContext](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/plugins/platforms/xcb/gl_integrations/xcb_egl/qxcbeglcontext.h#L50)
  derives from `QEGLPlatformContext` and delegates `makeCurrent` and swap to it.
  [The shared EGL implementation](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/platformsupport/eglconvenience/qeglplatformcontext.cpp#L399)
  reads **`QT_QPA_EGLFS_SWAPINTERVAL` even on this XCB/EGL path**. A valid
  nonnegative value overrides the surface format's interval before calling
  `eglSwapInterval`. Inspect the parent's launch environment for an inherited
  override before interpreting `context_swap_interval=0`; that log is Qt format
  metadata. Do not assume all EGLFS-named settings apply to X11: this particular
  one is verified in shared source. Interval zero does not guarantee a
  nonblocking `eglSwapBuffers` or eliminate driver queue limits.
- `QT_XCB_NO_SYNC_TO_VBLANK` and `QT_XCB_FORCE_SOFTWARE_OPENGL` were not verified
  as controls in the inspected Qt paths. Do not propose them as supported fixes.
- [xfwm4 4.16.1 map_win](https://github.com/xfce-mirror/xfwm4/blob/xfwm4-4.16.1/src/compositor.c#L3074)
  checks native opacity, damage support, lack of shape, and fullscreen/overlay
  eligibility before using bypass `1`. Its `unredirect_overlays` branch with
  bypass `0` additionally requires an override-redirect window: ordinary
  managed fullscreen alone does not meet that branch.
  [Its property-change handler](https://github.com/xfce-mirror/xfwm4/blob/xfwm4-4.16.1/src/compositor.c#L3855)
  only updates the cached bypass value. Thus a late `xprop` write is not proof
  of immediate unredirecting in that version. The installed xfwm4 version is
  not established here; verify it before applying this version-specific result.

## Implemented candidate

`src/compositor_bypass.cpp` contains the Xlib translation unit; its headers never
enter the renderer. Exact environment value `DETVIEW_BYPASS_COMPOSITOR=1` enables
the behavior; unset, `0`, and all other values preserve the original startup.
Only Linux with the `xcb` Qt platform opens an Xlib connection. Other platforms
compile a stub and report unsupported only when requested. `detview.pro` links
`-lX11` on Linux; the target SDK needs X11 development headers and library.
No global desktop settings, rendering formats, blend state, timers, capture or
swap interval are changed.

The controller prepares `_NET_WM_BYPASS_COMPOSITOR` as CARDINAL/32 with one value
`1` **before its first `show()`**. Qt's verified
[winId implementation](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/gui/kernel/qwindow.cpp#L668)
creates a missing native window. `QGuiApplication::sync()` flushes Qt's own
connection; an `XGetWindowAttributes` round trip then verifies server visibility.
Sync can process events, so a guard prevents reentry, and a vanished surface is
not recreated by the apply routine. The startup receipt reports XID,
`property_set=1`, readback, and `before_map`; an already exact CARDINAL/32 `1`
logs a no-op. These receipts verify a property request, not compositor
unredirecting or physical presentation.

The original property is saved with arbitrary type and valid 8/16/32 format,
including empty properties. Reads are bounded to 4096 protocol units (16 KiB);
any unread remainder refuses the change. Format-32 storage uses native
`unsigned long` elements as required by Xlib on both ILP32 and LP64. Cleanup
restores the exact original property, or deletes an originally absent property,
only if the current value is still our exact CARDINAL/32 `1`. A short X server
grab keeps that read/restore pair atomic against other clients. An independent
writer of the identical value `1` cannot be distinguished from our own hint.

`DetView` restores at the start of its destructor, before its context early
return or native teardown. A surface event filter restores on
`SurfaceAboutToBeDestroyed` and reapplies on `SurfaceCreated`, without recursively
creating a surface. The GUI thread owns the window lifetime; the implementation
does not install a process-global X error handler. A killed process destroys its
owned window and therefore its per-window hint.

Do not use `QObject::setProperty` as though it set an arbitrary X atom.
[QPlatformNativeInterface::setWindowProperty](https://github.com/qt/qtbase/blob/v5.15.8-lts-lgpl/src/gui/kernel/qplatformnativeinterface.cpp#L170)
is a base no-op, and the inspected XCB native interface does not override it;
its private header is not a reason to assume this API supports compositor bypass.

## Validation and parent handoff

Local byte audit `python src/bypass_source_audit.py` passes: 39 baseline files
are byte-identical; reversing only the documented lifecycle/build additions
recovers exact baseline `main.cpp` and `detview.pro`. Capture and renderer code
are unchanged. The portable C++17 property selftest passes under MSVC, covering
absence, arbitrary 8/16/32 data, type mismatch, multiple items, empty properties,
invalid data, and refusing unread remainder. The Windows helper stub passes
MSVC syntax compilation against local Qt 5.15.2. Local execution uses LLP64;
the test is also ready for LP64 execution on the parent target.

Build the candidate with the parent's existing presentation SDK recipe from
`swap/src/detview.pro`; no SSH, target build/run, PDS or launcher edits were
performed by this subagent. Launch with `DETVIEW_BYPASS_COMPOSITOR=1`, preserving
the presentation experiment's other environment and swap interval. Confirm
`readback=1 before_map=1` and independently observe compositor behavior.
Run the portable state test on target with
`c++ -std=c++17 bypass_property_selftest.cpp -o /tmp/bypass_property_selftest`
and `/tmp/bypass_property_selftest`.

Parent acceptance: establish property and actual compositor behavior first;
compare otherwise identical default-off and opt-in fullscreen launches with the
existing presentation trace. Preserve capture configuration and assess CAM1/2/5/6
40 fresh fps and CAM3/4 30 fresh fps independently. If bypass was already applied
and a controlled remap yields no improvement, do not duplicate the bypass test;
investigate the EGL override/driver swap path or run the separate idle-timer test.
