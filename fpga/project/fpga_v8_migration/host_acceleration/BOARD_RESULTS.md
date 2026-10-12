# Pinned V8 RK3568 completed-inference results

The final paired benchmark passes strict runtime-production compatibility and
measures a **10.29% improvement in completed inference FPS** on the RK3568.
It remains a standalone experiment; the existing viewer is unchanged.

| Metric | Runtime float + retained production decoder | Direct quantized + pinned compatible decoder |
| --- | ---: | ---: |
| Completed FPS | 14.5684 | 16.0670 |
| Timed completions | 240 | 240 |
| Mean completion wall time | 68.633 ms | 62.233 ms |
| Mean calling-thread CPU time | 11.892 ms | 8.469 ms |
| Mean output-get wall time | 25.891 ms | 22.443 ms |
| Mean decoder/owned-copy wall time | 1.967 ms | 0.400 ms |

The same pinned RKNN model bytes and 30 byte-identical prepared inputs are used
for both profiles. Four paired rounds run AB/BA/AB/BA; every fresh context gets
30 warm completions before 60 timed completions. All four rounds improve FPS,
with candidate/baseline ratios 1.1334, 1.0781, 1.1447 and 1.0568. The aggregate
ratio uses total completed count divided by total timed wall duration.

The 30 images are decoded frames from the second half of one retained road
video. Migration calibration samples also span that video. Frame indices and
file hashes are disjoint, while scenes are not independent. Results describe
this repeated fixed-shape workload; they do not establish general camera/class
coverage. See `../evaluation_frames/PROVENANCE.md` for the checked manifests.

All 30 certification comparisons and 240 timed native/production comparisons
pass. Recorded maximum coordinate and score differences are both zero. The
selected scalar reference, actual runtime float production decoding and direct
native decoding agree. Tolerances stay at 0.001 pixel and 1e-6 score. Model
SHA256 is `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9`;
runtime SHA256 is
`73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`, API
`2.3.0 (c949ad889d@2024-11-07T11:35:33)`, driver 0.9.8.

The runtime-specific conversion profile is essential. Mathematical queried
affine conversion passed same-output scalar checks but failed runtime-float
compatibility in the first full-pipeline experiment. A separate same-run probe
identified P3/P4 FP16-rounded conversion scales and P5 fused multiply-add;
all 1,214 observed head/code mappings matched bit-for-bit. The opt-in profile
checks all six head metadata values, while the benchmark pins the model,
runtime library, API build and FP behavior. The general API keeps mathematical
affine conversion as its default. No acceptance tolerance was relaxed.

The timed window includes CPU letterbox/color preparation, input submission,
RKNN execution, packed-output acquisition/validation, decoding into owned
results, release and sample bookkeeping. Disk reads, hashes, context creation,
warmup, result comparisons and report writing are excluded. Camera/PCIe
acquisition and display are not measured. The unchanged viewer PID 132334
appears in both environment records, running its separate `wb_v4_combo` workload;
the benchmark pins V8 independently and shares board resources. These results
are not viewer FPS, FPGA preprocessing performance, or full FPGA NPU execution.

Evidence: `../pipeline_board_runtime_compatible/` contains compiled-source
hashes, binary/library identity, environment, full samples, per-frame input
hashes, detection tuples, parity and JSON provenance. Run
`../audit_pipeline_evidence.py` against that directory to verify counts and
pairing without repeating inference. Earlier failed measurements and same-run
conversion evidence remain intact in their separate directories.
