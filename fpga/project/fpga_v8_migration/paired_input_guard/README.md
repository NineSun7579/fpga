# Owned RAW/input certification

`paired_input_guard.hpp` accepts the existing helpers' owned frame types and an
externally established generation. It checks complete payloads, full matching
source identities, the fixed camera/bank allocation profile, and every prepared
RGB byte against the independent C++ RAW reference. Tokens remain opaque.
It does not access transport, ACK leases, reset hardware or run inference.

This utility is for certification before paired inference comparison. Its CPU
preparation and byte comparison must be outside timing or explicitly included in
both measured profiles. Passing it does not establish physical RAW provenance,
transport retirement, runtime reservations or installed endpoint support.

Run `python run_tests.py` once in a fresh artifacts directory. Tests consume the
five full retained capture/core/DDR pairs, supplying descriptors from their
checker metadata, and reject changed generations, source identities, partial
copies, wrong allocations, and corrupted padding/content bytes. They do not
exercise live helpers or retrieve descriptors through a physical transport.

Validation passed with MSVC C++17 `/W4 /WX`: five pairs, 6,144,000 certified
RGB bytes and 80 negative checks. Exact commands, hashes and output are in
`artifacts_02/results.json`. The initial compilation failed for a missing
standard `<string>` include; its log remains in `artifacts/build.txt`.
