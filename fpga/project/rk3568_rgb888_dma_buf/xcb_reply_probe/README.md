# xcb_reply_probe (isolated diagnostic)

Startup `LD_PRELOAD` interposer for Linux `xcb_request_check` only:

```c
xcb_generic_error_t *xcb_request_check(xcb_connection_t *, xcb_void_cookie_t);
/* xcb_void_cookie_t is a struct containing unsigned int sequence, passed by value. */
```

The connection pointer and entire cookie are passed unchanged, including unsigned
sequence wraparound. The returned allocated error pointer is returned unchanged;
the caller still owns it. NULL remains successful checking. The probe never frees,
copies, interprets, or replaces that error and sends no extra XCB requests. It
preserves incoming errno at the real call and outgoing errno after timing/logging.

## Build and local verification

```sh
make                         # Linux host shared library, not an RK3568 binary
make test                    # local shared-library fixtures; no board / X server
# For an offline target build, explicitly select your installed toolchain:
make CC=aarch64-linux-gnu-gcc
```

Headers use installed `<xcb/xcb.h>` when available; otherwise `xcb_abi.h` supplies
the public Linux XCB declarations. No link to libxcb is added to the probe.
Tests build actual shared libraries, preload into a host linked to an XCB stub,
and check exact pointers/cookies (UINT_MAX-1, UINT_MAX, 0, 1, 65536), NULL success,
caller-owned allocated errors, errno changes/preservation, reentry, all histogram
boundaries, window resets, three distinct Linux TIDs, failed/malformed/backwards
clocks, all-clocks-failed silence, and short writes without retry. They also smoke
test production-clock builds and require missing-symbol startup failure (127).
Evidence is written only to `host_build/test_results.txt`.

## Startup contract and output

For a separately authorized diagnostic launch, the invocation shape is:

```sh
DETVIEW_XCB_REPLY_PROBE=1 LD_PRELOAD=/absolute/path/libxcb_reply_probe.so viewer [args]
```

This directory provides code and local fixtures only; nothing here installs,
deploys, launches a viewer, or accesses a board. The intended Qt viewer already
has libxcb in its initial dependencies. `RTLD_NEXT` resolution occurs once in the
constructor, under a thread-local recursion guard. Loading libxcb later with
`dlopen` is unsupported, as is late loading this initial-exec TLS probe. Missing
resolution, or a loader callback entering the wrapper before construction has
completed, prints a bounded diagnostic and terminates with status 127, even when
disabled. This explicitly rejects the loader configuration instead of fabricating
a successful NULL reply. There is no call-path dlsym or lazy initialization.

Only the exact value `DETVIEW_XCB_REPLY_PROBE=1` enables timing. Otherwise the
initialized wrapper forwards directly: no clocks, TID lookup, counters, or logs.
Enabled calls use two monotonic clock reads, and thread-local integer aggregates;
there are no probe locks, hot-path allocations, asynchronous workers or extra
X queries. The first recorded call obtains its Linux TID once.

Each thread emits one line on a completed call once at least five seconds have
elapsed since that thread's first valid clock/window boundary:

```text
xcb_reply_probe tid=20421 wall_ns=... calls=... timed=... invalid_clock=... sum_ns=... max_ns=... buckets_lt1_lt5_lt10_lt20_ge20_ms=...
```

`calls` counts every outer intercepted call; `timed` and the buckets count only
valid, nondecreasing clock pairs. Invalid pairs contribute to `invalid_clock`,
not sum/max/buckets. Buckets are `<1`, `[1,5)`, `[5,10)`, `[10,20)`, `>=20` ms.
`sum_ns / timed` gives mean elapsed time; `sum_ns / wall_ns` gives the fraction of
that thread's reporting interval spent inside this function. Invalid timestamps
cannot trigger a report. Totals reset at the reporting end timestamp. Nested
reentry forwards without recursive timing and is included in its outer duration.

Output uses one bounded stack buffer and one write to stderr per interval; short
writes and EINTR are not retried. Logging can block and perturb subsequent
activity; keep the sink draining. There is no timer, exit flush or thread-exit
flush: inactive threads and partial intervals do not emit. A call blocked longer
than five seconds reports only after returning. Persistent clock failures produce
no report until a usable time boundary appears. Integer counters can overflow
under extreme run lengths. The timed span includes clock-call boundary overhead,
scheduling and waits inside the real function; it is not GPU execution time.

## Motivation and interpretation limits

The requesting session supplied this original-process evidence (not remeasured by
these local tests): PID 20413's main thread had 79 swap-related futex waits totaling
1.6735 s in a four-second window, matched by 79 backend TID 20421 wakes. A gdb
snapshot found that backend in `xcb_request_check`. Swap interval 0 succeeded,
yet mean swap remained about 19 ms; ring depth 3 did not improve it (about 21 ms).
These observations motivate measuring this backend function without changing the
production render path or adding asynchronous behavior.

A single stack snapshot does not establish that all backend waits occur in XCB.
This probe measures only calls routed through this interposed symbol; it misses
other XCB waits, noninterposable internal binding, and driver/GPU work elsewhere.
Use the emitted TID to distinguish the Mali backend from the main thread (Linux
main TID equals PID); do not merge their totals or assume every XCB call is from
Mali. Correlate backend reports with separately collected main-thread swap/futex
data over aligned windows. The historical TIDs above are identifiers from that
capture, not fixed IDs for a future launch. The probe supplies timing data from
whichever backend/main threads actually call the function; it does not identify
thread roles automatically or prove causality.
