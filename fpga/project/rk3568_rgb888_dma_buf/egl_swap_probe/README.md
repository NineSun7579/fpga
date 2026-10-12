# Isolated EGL swap diagnostic

This startup `LD_PRELOAD` probe observes `eglSwapBuffers` duration and application
`eglSwapInterval` requests. It does not change intervals, query EGL configuration,
call `eglGetError`, or modify the viewer. All files and host artifacts belong to
this directory. No board access, deployment, or production rebuild is part of
this work; the reported production PID 9992 is left untouched.

## Build

No Qt headers or Qt libraries are required, including the board's Qt5 headers.
Installed official `<EGL/egl.h>` is used automatically when available. Otherwise
`egl_abi.h` declares only opaque display/surface pointers, unsigned-int
`EGLBoolean`, int `EGLint`, and the EGL function-pointer type. These use the normal
Linux ARM C calling convention. `-DPROBE_NO_EGL_HEADERS` forces this fallback.
Use a compiler and libc sysroot matching the application's ELF architecture.

For an ARM64 Linux toolchain (build command only; not executed here):

```sh
cd egl_swap_probe
aarch64-linux-gnu-gcc --sysroot=/path/to/target/sysroot \
  -O2 -std=c11 -Wall -Wextra -Werror -fPIC -shared \
  egl_swap_probe.c -o libegl_swap_probe.so -ldl -pthread
```

For a 32-bit ARM hard-float application, substitute its matching
`arm-linux-gnueabihf-gcc` toolchain/sysroot. Do not infer userspace bitness from
the RK3568 chip alone. Alternatively, `make CC=/path/to/matching/compiler` with
the toolchain's usual sysroot configuration builds the same library. A runtime
EGL implementation must already be loaded by the application; no `-lEGL` link
dependency is added.

## Use in a separately authorized diagnostic launch

```sh
DETVIEW_EGL_SWAP_PROBE=1 LD_PRELOAD=/absolute/path/libegl_swap_probe.so \
  /path/to/viewer [existing arguments] 2>egl_swap_probe.log
```

This is a launch example, not a deployment instruction. Only the exact value
`1` enables observation; unset, `0`, and other values forward without logs,
clock reads, or statistics locking. The setting is sampled at library startup.
The probe resolves the next functions once in its constructor via
`dlsym(RTLD_NEXT, ...)`, with no lazy loader lookup in wrappers. It requires
startup preload and uses initial-exec thread-local storage, not late `dlopen`.

Each interval call records its exact requested signed value, original unsigned
return value, and success (`return != 0`). It forwards exactly once. Success
does not establish the effective driver interval or display mode. No min/max
configuration query is attempted because EGL errors cannot be saved/restored.

`eglGetProcAddress` first delegates to the implementation. When enabled, supported
swap/interval pointers equal to the resolved next symbol are replaced with the
corresponding wrapper. Unsupported NULL results, other functions, and alternate
implementation pointers remain untouched. The latter may bypass timing;
changing them would break exact forwarding. Disabled mode preserves every
returned pointer. EGL errors are never read, consumed, or synthesized. `errno`
on entry to the real call and on return to the caller is preserved despite
clock/logging operations. Return values are not normalized.

Constructor-time loader reentry before resolution, or a missing next symbol,
cannot be faithfully forwarded: wrappers return zero/NULL with unchanged
`errno`, without resolving recursively or synthesizing an EGL error. This is
an unsupported preload setup, not a normal EGL call path. Once initialized,
thread-local reentry forwards directly and omits nested diagnostics.

## Reading the log

One swap summary is emitted on the first completing swap reaching at least
five seconds of monotonic window time. There is no timer thread, exit flush,
or output while idle; a partial final window remains unreported. All threads,
displays, and surfaces share the summary. The first window starts at the first
usable clock sample; later windows start at the previous report's completion
sample. Counters are protected by a short mutex; formatting/write occurs after
unlock. Concurrent calls are attributed when their statistics acquire the mutex,
so windows are approximate completion windows, not frame-presentation boundaries.

- `calls`, `success`: all observed swap calls and nonzero returns, including
  calls without a valid timing pair.
- `timed`, `invalid_clock`: usable timing pairs versus failed/invalid/backward
  clock pairs. Failed clocks never become zero-duration samples.
- `sum_ms`, `max_ms`, `mean_ms`: valid call durations only; mean denominator is
  `timed`. Timed unsuccessful swaps also contribute.
- `buckets_lt1_lt5_lt10_lt20_ge20`: disjoint durations `[0,1)`, `[1,5)`, `[5,10)`,
  `[10,20)`, `[20,infinity)` milliseconds; their sum equals `timed`.
  `longswap_ge20ms` repeats the final bucket.
- `wall_s`: measured window duration, not a fixed assumed five seconds.
  `calls_per_wall_s = calls / wall_s`; this is swap-call rate, not display FPS.
  `swap_time_per_wall = sum_duration / wall_duration`; concurrent threads can
  make this exceed one. It is not CPU utilization or exclusive GUI wall time.

The probe has no explicit heap allocation in the call path; it uses static
statistics, thread-local guard, and stack log buffers. Clocks, mutex contention,
formatting, libc behavior, and stderr writes still add overhead. A blocked stderr
sink can perturb the application; bounded single writes are best effort, without
retry on short writes/errors. Interval requests produce individual lines, while
swaps produce aggregate summaries. No signal-handler use is supported.

## Host verification and evidence limits

```sh
python3 tests/run_host.py
```

Linux host tests compile a real stub EGL shared library and the preload DSO,
then exercise actual ELF symbol forwarding and `eglGetProcAddress`. A test-only
clock seam provides deterministic boundaries/failures. Tests cover exact
arguments/returns, unsuccessful calls, per-call errno, untouched/unsupported/
alternate proc pointers, disabled mode without timing/logging, both clock
failures, bucket boundaries, nested reentry, and four threads with 401 total
observed calls. All report denominators and aggregate counts are checked.
Production builds use `clock_gettime(CLOCK_MONOTONIC)` directly. Artifacts and
captured output are under `host_build/`; test durations are synthetic assertions,
not board performance measurements. Both fallback and automatically selected
EGL declarations are compiled on the host. No ARM cross build is claimed.

Prior evidence supplied with this task: GUI strace showed 106 futex waits
totaling 2.6629 seconds over five seconds; two ON/OFF gdb stacks showed
libc -> libmali `eglSwapBuffers` -> Qt xcb EGL. ON/OFF/ON rates of 25/29/31 FPS
were not a reversible result and do not establish causality or a performance
gain. This probe is intended to collect swap-duration and requested-interval
evidence in a future authorized run. None of that prior evidence was remeasured
by these host tests.

Parent ARM build `../egl_probe_build_1791618116956610000` uses an explicit
`--no-as-needed /lib/aarch64-linux-gnu/libmali.so.1` dependency: the viewer's
initial dependency list does not include EGL, so constructor-only RTLD_NEXT
resolution would otherwise miss functions loaded later by Qt. Readelf confirms
the Mali dependency. A separate native smoke process resolved eglSwapBuffers
and forwarded an invalid-display interval request, returning failure as expected.
This establishes loading/forwarding availability, not valid-surface performance.
The added early Mali load can itself affect initialization/timing; compare only
as diagnostic evidence and restore the original launch environment afterward.
