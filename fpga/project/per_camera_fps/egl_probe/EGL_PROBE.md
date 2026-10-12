# EGL call probe

This isolated Linux LD_PRELOAD shim measures forwarded EGL calls. It requires no application rebuild, EGL headers, or EGL link dependency. The existing `swap/src` and active application remain untouched. This revised source is locally validated only; it is not authorized or validated for another board experiment.

## Failed run and next diagnostic candidate

The available `failed_target.log` contains only 100 tail lines, starting with `QEGLPlatformContext: eglSwapBuffers failed: 3000`. It contains no startup resolver evidence. `target_receipt.json` identifies the old shim source as `20b17b7afca7c147e7722a35f8ea042194dfca1c713a1c24a02efd998b4244c2` and library as `9b895aab656b97612cee31ed3558aa50d06a577623cea85d6a57412b3bf9f91b`. The parent reports that the launched process quit before observation began and that the baseline was restored; this source change does not alter that baseline.

The old constructor permanently cached `dlsym(RTLD_NEXT, ...)` before a later Qt `dlopen` could occur. Missing functions silently returned EGL_FALSE without setting an EGL error. This is a verified code defect, reproduced locally, and is consistent with failure plus `0x3000` (EGL_SUCCESS). The tail alone does not prove whether the board hit this defect, used RTLD_LOCAL, or resolved a different dispatch stack. Obtain the entire failed launch log and any existing loader/library-map evidence before deciding the board root cause; no new hardware connection is needed for this local fix.

Resolution now occurs on the first intercepted call. By default it uses RTLD_NEXT. If Qt uses RTLD_LOCAL, set `DETVIEW_EGL_PROVIDER` to the exact EGL provider already loaded by the application, established from its loader evidence. The shim uses `dlopen(path, RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD)` and keeps the handle, resolving forwarding and metadata functions from the same handle. It does not guess `libEGL.so.1`, load a new library, or substitute GLVND/Mesa dispatch for a Mali-owned context. An explicit handle searches that object's dependency scope; it is not proof that every function is implemented in the named object. Enabled resolver logs report the actual swap/interval object paths via `dladdr`.

Missing forwarding symbols, an unloaded selected provider, self-resolution, or resolver reentry produce a fatal diagnostic and `abort()` before issuing an EGL call. This intentionally terminates an unusable probe setup rather than impersonating a driver failure, even when tracing is disabled. The locally tested candidate is therefore for diagnostics only. Do not resume a board experiment until hardware is free, the parent has selected an authoritative provider, and launch evidence can be retained from startup.

The target is fresh display at 40 fps for CAM1/2/5/6 and 30 fps for CAM3/4, with all six videos, correct inference, and stereo retained. Actual capture is about 36/25.7 fps. The latest swap-before-map run did not improve performance: composite about 28.8 fps, per-camera about 26/23 fps, paint about 11 ms, swap-after-paint about 22.3 ms, update about 0.55 ms, GPU at its 800 MHz maximum. These are parent observations, not measurements made by this probe. A Qt context reporting swap interval 0 does not establish the driver's effective presentation behavior.

Build on the target, or with a Linux aarch64 cross compiler:

```sh
gcc -std=c11 -shared -fPIC -O2 -Wall -Wextra -Werror \
  -o libegl_probe.so src/egl_probe.c -ldl -lpthread
# Cross-build alternative: replace gcc with aarch64-linux-gnu-gcc.
sha256sum src/egl_probe.c libegl_probe.so
```

Use the already identified candidate binary and its existing launch environment/arguments. Set these variables in the parent's launcher environment (replace the example absolute path):

```sh
DETVIEW_EGL_TRACE=1
# Only if needed, after confirming Qt's actual loaded EGL provider:
DETVIEW_EGL_PROVIDER=/absolute/path/to/confirmed/provider.so
# Optional, separately opt in to metadata queries:
DETVIEW_EGL_METADATA=1
LD_PRELOAD=/absolute/path/libegl_probe.so
```

For a direct shell launch:

```sh
DETVIEW_EGL_TRACE=1 LD_PRELOAD=/absolute/path/libegl_probe.so \
  /absolute/path/existing_candidate_binary [existing arguments] 2>egl_probe.log
```

If other preloads are required, preserve their paths after the probe, separated by colons. Record the existing binary hash and shim source/library hashes with results. This probe performs no SSH, PDS work, board setup, or launch itself.

Only the exact value `DETVIEW_EGL_TRACE=1` enables tracing. Unset/0 forwards resolved calls without timing, queries, mutexes, or normal output; resolution failure still terminates with a diagnostic. Symbol resolution and the wrapper branch impose a small preload cost. Remove LD_PRELOAD for a completely uninstrumented baseline. Trace alone performs no metadata queries; additionally set `DETVIEW_EGL_METADATA=1` to enable them.

With metadata enabled, the first successful swap reports current display/draw surface/context and skips further queries unless all match the intercepted call. It queries version/vendor/extensions (extensions capped at 512 characters), surface render buffer, swap behavior, width, height, and config ID. It enumerates configurations with `eglGetConfigs`, matches that ID, and reports minimum/maximum swap interval, alpha size, buffer size, native visual ID, and renderable type. It does not choose or replace a config. No metadata runs after a failed swap. Query failures are logged without reading EGL error state. Resolver object paths are printed; no addresses or credentials are printed.

`[egl-call] interval=N success=R` records the first interval call and changes in its argument or result. Repeated identical calls are counted without per-frame output. A nonzero result means the next implementation accepted that call; zero means failure. EGL has no general query for the effective current swap interval. Configuration minimum/maximum values and accepted calls cannot establish actual pacing. RTLD_NEXT follows the loader's next implementation (possibly another interposer); this does not prove the resolved function belongs directly to Mali. Explicit handle-based `dlsym` inside Qt or a driver may bypass LD_PRELOAD. Missing call logs mean interception has not been established.

Every roughly 10 seconds of call activity, a process-wide aggregate reports swaps and interval calls, successes/failures, and mean/maximum monotonic wall duration in milliseconds. The measured interval brackets only the forwarded call; it includes blocking/scheduling time, not just CPU execution, and does not measure GPU execution or display scanout. Reporting and startup metadata run after forwarding and outside that timing interval, but add caller latency. The first window therefore deserves separate treatment. There is no timer thread, sleep, per-frame logging, or final partial-window report. Multiple threads are aggregated under a mutex; recursive calls forward without instrumentation.

With forwarding established, the shim forwards original arguments once and returns the exact result. It never calls `eglGetError`, requests a swap interval, changes a surface/context, inserts GPU work, or retries failed rendering calls. As with any EGL metadata probe, a failing query can itself set the EGL error flag; preserving that flag perfectly while inspecting it is not possible without consuming it. This probe deliberately leaves error reads to the application and does not claim error-state transparency for failed metadata queries. Use trace without metadata for the initial forwarding diagnostic.

Local validation uses separate fake EGL libraries and executables in `src/`: exact 0/1 forwarding, independent metadata opt-in, config ID matching, query failures, nested calls, and aggregation are checked with a synthetic monotonic clock. An executable with no EGL link dependency loads its provider after preload initialization using RTLD_GLOBAL or RTLD_LOCAL. A separate global core-dispatch fake has no current display and aborts on rendering; selecting the local provider must forward and query exclusively through that provider. This models core/vendor dispatch separation, not real GLVND/Mesa/Mali compatibility. Missing local forwarding and an unloaded explicit provider must terminate diagnostically. No 10-second sleep or actual EGL/GPU is needed. These tests establish shim behavior, not board interception or performance.

```sh
sh src/run_selftest.sh
```

Validated successfully on local WSL Ubuntu 24.04 with GCC, including `-Wall -Wextra -Werror`. The production shared object and fake library are compiled separately; test libraries must never be preloaded on the board. Test artifacts use a temporary directory and are removed automatically. No application build or hardware validation was performed.
