# Live RAW prefetch candidate (review required)

Copied from `candidate_prefetch_viewer`, excluding local builds. No RTL, driver,
board commands, or source candidate edits. FPGA inference remains opt-in via the
inherited `DETVIEW_FPGA_INFER_RGB=1` gate; age telemetry separately requires
`DETVIEW_INFER_AGE=1` (exact value, default off).

## Behavior and ownership

`prefetchedInput` is a shared VisionFrame retained under the ingress mutex.
The existing two-entry per-camera mailbox continues receiving latest RAW.
The worker processes the exact prefetch source before latest RAW so its grayscale
and post-update tracker snapshots exist even if capture has already advanced.
Request selects the exact retained frame, while weak/lost-target cadence uses
the latest tracker state and capture time. Existing cadence helpers, minimum
intervals, pre-arm timing, converter admission and model rotation are unchanged.
No healthy prefetch is cancelled merely because another RAW frame arrives.
QImages retain implicit sharing; there is no new RGB deep copy.

History keeps the newest FPGA source and its replay suffix for the existing
1000ms source-age limit, up to 64 entries (ordinary non-FPGA history remains 8).
On overflow, retain the exact source snapshot plus the latest 63 entries; replay
then skips evicted intermediate frames. Normal tracking still processes admitted
latest RAW frames before eviction. This is a deliberate finite memory bound:
64 RGB/grayscale frames and deep tracker snapshots can cost substantially more
than the former eight entries. Independent review should assess ARM memory/cost.
The retained source receives correction at its original capture timestamp, then
replays newer retained RAW entries, preserving source-based detection TTL.

Unsubmitted inputs complete explicitly on configure, stop, invalid/stale ingress,
duplicate submissions of a different input, stale/model-revision rejection,
worker exception and failed emission. A duplicate of the healthy retained input
does not retire it. Admission revision validation catches model reload during
cooldown; GUI and pre-consume age checks reject queue delays over 1000ms.
Dispatched inputs remain with the existing GUI/RKNN ownership path. Imported
backing ownership and synchronous completion/quarantine policy are inherited.

## Telemetry

Events: `capture_RAW_DMA_complete`, `publish`, `request`, `GUI_submit`,
`RKNN_start`, `result_accepted`. Every line includes frame ID, generation,
camera, tag, original monotonic captured_ms, event_ms, and age_ms.
The capture event is written when the packet ID becomes available, but event_ms
is the existing timestamp sampled immediately after RAW DMA completes, before
conversion/release/copy. Other events sample CLOCK_MONOTONIC when they occur.
No runtime aggregation; group by generation/camera/ID to calculate percentiles.
RKNN_start is the primary production run; inherited verification-only extra runs
are not counted as additional production events. RAW publish means analytics
packet publication, not a display refresh.

## Validation and outstanding review

Host WSL: production cadence/admission clock, switch, lifetime fixtures pass;
wrapped actual PangoDev protocol tests pass off/on/verify; fair DMA fixtures,
actual main classes syntax and native output capture fixtures pass. These use
host wrappers and never access the board.
The standalone production telemetry helper also passes: unset and value 0 emit
no events; value 1 emits the supplied same-ID capture/request timestamps with
ages 0/120ms. `bash local_prefetch_check.sh` passes the updated preservation audit
and inherited host checks.

The updated `VisionPipeline::selfTest()` adds real-worker fixtures for RAW during
cooldown, exact camera/tag/generation/input/QImage identity, correction replay
beyond eight frames, latest-RAW target loss with minimum urgent interval, and
unsubmitted input retirement/lifetime on switch/stop/empty models. Synthetic Input
cases run with FPGA feature off, requiring no board. Existing pipeline tests stay.
Host has Qt 5.15.13 but no OpenCV development package: FULL PIPELINE COMPILE AND
SELFTEST EXECUTION PENDING parent ARM compilation/tests. Do not interpret the
main classes syntax check or modeled cadence tests as full pipeline validation.
Independent review and ARM full-pipeline/vision selftest remain required.
