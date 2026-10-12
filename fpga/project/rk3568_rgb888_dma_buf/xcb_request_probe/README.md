# XCB request classification probe

Isolated diagnostic fork of the adjacent `xcb_reply_probe` (the requested
`smallxcb_reply_probe` name does not exist in this workspace). The baseline was
copied without `host_build`; its old binary was removed. All changes and local
build artifacts are confined to this new directory. No board calls, deployment,
viewer changes, or performance optimizations were performed.

The probe answers which core opcode or extension/minor opcode was associated
with a timed `xcb_request_check`, when the originating send is visible on the
same thread. It performs no extension lookup, query, flush, or other XCB calls.
Extension names come directly from `xcb_protocol_request_t.ext->name`; core
requests use `core`. The extension opcode is the request's minor opcode, not a
queried server-assigned extension major opcode. No opcode-family guess is made.

## Build and local verification

Linux or local WSL, with a C11 compiler, Python 3, libxcb development files:

```sh
make
make test
```

`make` produces `libxcb_request_probe.so`. `make test` creates its own local
`host_build`, including `test_results.txt`. The host suite explicitly builds both
official `<xcb/xcb.h>` / `<xcb/xcbext.h>` and header-free ABI variants. The
fallback definitions preserve `size_t count; xcb_extension_t *ext; uint8_t
opcode; uint8_t isvoid`, and extension `const char *name; int global_id`.

The final local run passed 40 enabled dynamic fixture cases (20 per ABI), six
disabled forwarding cases, missing-symbol checks, real-libxcb disconnected
connection smoke checks, and the dynamic symbol audit. Fixtures cover exact
32/64-bit cookies and arguments, all four send variants, vector and reserved
prefix preservation, FD array identity, errno and error-pointer identity,
low-32 wrap, simultaneous equal cookies on different connections, eviction,
duplicate low-32 ambiguity, cross-thread unknown, metadata snapshots, nested
send forwarding without duplicate tracking, nested checks without duplicate
profiling, repeated checks, multiple aggregation windows, and clock failure.

Real libxcb smoke tests use an invalid display and its failed connection; they
verify forwarding, zero cookie, and untouched vectors. They do not test a live
server, successful FD transport, or hardware latency. FD ABI/forwarding is
verified by the dynamic fixtures against official signatures; descriptors are
never consumed by the probe.

## Activation and output

For an already authorized Linux run, put the new library in startup
`LD_PRELOAD` and set `DETVIEW_XCB_REQUEST_PROBE=1`. Other values disable capture
and timing. No runtime run or deployment is part of this implementation.

Each active thread emits aggregate lines at the first check completion at least
five seconds after its window began, one line per populated class. There is no
per-slow-check logging and no exit-time or idle flush. Classes distinguish exact
extension, opcode, flags and isvoid; TID identifies the thread. `sum_ns` is total
check wall time, `max_ns` the maximum, and `slow_ge20ms` counts checks at least
20 ms. `wall_ns` describes the reporting interval. `timed` excludes invalid
clock samples, reported separately as `invalid_clock`. Example fields:

```text
xcb_request_probe tid=123 unknown=0 extension=DRI3 opcode=7 flags=1 isvoid=1 checked=1 wall_ns=... calls=... timed=... invalid_clock=0 sum_ns=... max_ns=... slow_ge20ms=...
```

`checked` reflects only `flags & 1`. All sends are captured, including flags 0
and 4; these may still be followed by checks. Unknown entries print
`unknown=1 extension=unknown opcode=unknown flags=unknown isvoid=unknown
checked=unknown`; the probe never invents flags or an opcode for them.

## Forwarding and bounded matching

The wrappers exactly match `xcb_send_request` (unsigned int),
`xcb_send_request64` (uint64_t), `xcb_send_request_with_fds` (unsigned int), and
`xcb_send_request_with_fds64` (uint64_t). They pass the original connection,
flags, vector, request pointer, FD count and FD array pointer unchanged, once
to the corresponding original. They never read or write the vector, including
its reserved `[-2]` and `[-1]` slots, payloads, or FDs. Original errno, cookies,
and check error pointers are preserved; errors are not inspected or freed.

An initial-exec TLS guard permits internal calls to other wrapped functions to
forward once without recursively profiling. Only the outer send records its
returned cookie; check-internal sends cannot replace the check's classification.
The 64-entry TLS ring holds connection, low 32 sequence bits, and a bounded
snapshot of request metadata. Lookups require one exact connection/sequence
match on the current thread and consume that entry. Multiple matches invalidate
all matches and report unknown. Evicted, cross-thread, unmatched, repeated,
zero/failure, null metadata, and overlong extension-name cases are unknown.
Successful 64-bit sequences whose low 32 bits are zero remain matchable;
32-bit zero returns are conservatively treated as failures. Names must fit in
63 bytes without truncation. No allocations or locks occur on probe call paths.

Each thread has at most 64 exact aggregate classes plus an unknown bucket.
Additional classes in a window go to unknown rather than borrowing a label.
Like the XCB cookie API, this cannot distinguish a stale cookie after a full
2^32 sequence reuse, or a reused connection address after its lifetime ends;
metadata matching is bounded diagnostic evidence, not lifetime tracking.

Resolution happens in the constructor with `RTLD_NEXT`. Missing original
`xcb_request_check` or `xcb_send_request` terminates with `_exit(127)`, even when
disabled. The 64-bit and FD originals are optional at startup; invoking a
wrapper whose original is absent terminates with 127, never a fabricated cookie.
The library is intended for startup preload, not late `dlopen`.

Prior supplied observations were 805 backend checks averaging 19.2 ms and 806
swaps averaging 25.8 ms. Roughly 50% wall time in XCB and 69% in EGL are
correlated measurements of potentially nested work and must not be added.
This host-only implementation supplies no new board performance evidence.
