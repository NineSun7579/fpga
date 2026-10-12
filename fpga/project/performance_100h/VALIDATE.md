The optimization goal remains incomplete. The user chose to preserve the
calibration viewer and continue local work. Do not switch that viewer or run
target jobs during this phase. These steps describe the remaining validation
when board resources become available.

Run the local input check from the workspace root:

```powershell
python project/performance_100h/preflight_local.py
```

The preferred candidate source is `direct_ingress/src`: it combines reusable
preprocessing, conditional tracking history, paced capture, cached RKNN output
attributes, direct result delivery and generation-gated direct requests. Its
main SHA256 is
`fb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04`.
Local extracted-code concurrency tests passed. The complete Qt5 controller
and RKNN application have not been compiled or exercised for this variant.

When target work is available, build the pinned source privately:

```powershell
python project/performance_100h/build_host.py --source project/performance_100h/direct_ingress/src
```

Use that build's receipt and binary hash for all subsequent tests. Run its
preprocessing parity test and existing vision, DFL, lane, camera-DMA and
frame-metric selftests. The current cache-only target build and image parity
do not establish direct-ingress controller safety.

Before switching the display, capture the current viewer's actual process
identity, executable/settings/model hashes, arguments and private environment.
Do not reuse a receipt for an absent process or overwrite the retained original
baseline. Resolve ownership with the calibration task. Stop only the verified
owner through its associated window, and retain a concrete restoration path.

Exercise the actual direct-ingress controller with camera/model changes,
confidence changes, pause/resume, format selection and model rotation while
requests are in flight. Check generation increments, stale result rejection,
paused request suppression and capture -> vision -> inference shutdown joins.
Verify displayed detections still correspond to the selected configuration.
Run the final image parity harness as well; image parity alone bypasses the
controller and cannot establish these transition invariants.

Measure the instrumented original build `5ad75c7b2e51e76a` and the final
candidate with the same source, model, fullscreen/no-tracking configuration,
stereo settings and pinned assets. For the candidate start with texture ring1
and capture cap30. Preserve all six live streams. Collect at least120 seconds
per version without compiler or extra inference jobs. Observe receipts now
contain source monotonic bounds; retain only fully contained metric windows.

Compare the exact original and final observe receipts:

```powershell
python project/performance_100h/audit_performance.py <candidate-observe.json> --baseline <original-observe.json> --output <comparison.json>
```

Require higher fresh video FPS, higher successful completed inference FPS,
lower successful DMA read payload, zero inference/read failures and overlapping
delivery for all six cameras. Repeat matched observations if the differences
are small or scene/load changes confound the result. Capture and directly
inspect the six-camera screen, retain final identity/configuration evidence,
and restore the agreed viewer after testing.

DMA payload counters measure completed requested FPGA DDR reads; they exclude
camera writes, failed partial transfers and memory-controller overhead.
Reduced requested reads are evidence of reduced read pressure, not a direct
measurement of total physical DDR bandwidth. Earlier23–26 FPS display results
and estimated payload comparisons do not complete the inference requirement.
