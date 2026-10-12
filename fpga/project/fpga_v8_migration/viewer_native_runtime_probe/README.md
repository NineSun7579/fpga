# Headless native viewer runtime probe

This directory contains an isolated RK3568 runtime integration probe for the
existing `viewer_native_candidate` headers. It uses QtCore only and does not
start, stop, attach to, or replace the live viewer. The remote stage was
`/userdata/linaro/viewer_native_runtime_probe_343c9ef99a3f4a95a98f1241b7347eae`;
the parent viewer build stage was not used.

The source snapshots, hashes, exact recovered production decoder binding, and
candidate QVector conversion binding are in `source_dependencies.json` and
`decoder_and_conversion_binding.json`. `compiler_link_commands.txt` retains
the commands derived from the recovered viewer Makefile: GCC 12.2, GNU C++17,
`-O2`, Qt 5.15.8 QtCore flags, and explicit `-fno-fast-math`. `binary_identity`
and `compiled_dependency_hashes_after.json` retain link and dependency identity.

The actual model was 4,142,230 bytes with SHA256
`be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9`. The
probe observed one mapped `/usr/lib/librknnrt.so`, verified its SHA256 as
`73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`, and
observed API `2.3.0 (c949ad889d@2024-11-07T11:35:33)` and driver `0.9.8`.
The actual input and six output attributes are retained in
`runtime_report.json` and `actual_guard_profile.txt`.

`runtime_report.json` contains 120 strict cases: 30 retained RGB prepared
inputs at confidence values 0.05, 0.25, 0.32, and 0.95. Each case compares
the candidate native decoder and QVector conversion with the production
decoder included from the exact recovered `board_production_decoder.inc`.
All counts, classes, order, scores, and coordinates passed; maximum score and
coordinate errors were both zero. Each inference obtained native and float
outputs from the same `rknn_run`, released each successful output lease once,
and recorded 30 runs, 60 gets, 60 release calls, and 360 released buffers in
the first certification invocation.

The opt-in cases cover missing `DET_V8_NATIVE`, another value, a one-byte bad
model copy, and present `DET_INT8_IN` values. The pinned profile enabled on
the actual context. `native_guard_selftest` passed all guard and release
negative cases.

The probe was accidentally invoked a second time while adding the guard-only
command, causing one duplicate 30-run workload. No further inference was run;
the retained certification report is the first successful 30-run invocation,
and this deviation is recorded here for audit completeness. The live viewer
identity before and after remained PID 2740, starttime 152164, executable
`/userdata/detview-driving-demo/detview-driving-demo`, with the same executable
hash and runtime mappings. This is runtime integration validation and contains
no FPS or completion-rate claim.
