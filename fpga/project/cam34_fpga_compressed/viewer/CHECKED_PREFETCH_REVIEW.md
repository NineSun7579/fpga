# Checked prefetch candidate — independent review required

This separate directory copies `candidate_prefetch_live_viewer`, excluding local
builds/outputs. The source candidate undergoing parent ARM compilation is untouched.
`main.cpp`, capture protocol, Input/admission, cadence helpers, age telemetry,
RTL and driver code match the live candidate. No board operations or commits.
Inherited `LIVE_PREFETCH_REVIEW.md` describes the baseline; this document replaces
its dispatch and overflow claims for the checked candidate.

## Exact processed-source gate

`request()` may re-read a retained Input that arrived after the worker copied
ingress. Before it can mark that Input dispatched, create Pending, change actual
submission cadence, or emit, it now requires processed history matching camera,
generation, frame ID, tag, capture timestamp, Input shared-pointer identity and
QImage pixel-pointer identity. Every active tracker must have a snapshot; grayscale
must exist when trackers exist. A newer unprocessed source stays owned and
undispatched for the next worker iteration, which processes the retained frame
before the newest RAW mailbox frame. An identity already passed/evicted is retired.
Existing stale/config/model revision rejection and cancellation paths remain.

Pending retains the exact Input identity. A retained-input reply is rejected before
accepted-result publication if that identity/snapshot is missing or overflow-invalid.
It cannot enter the history-missing fallback that clears vehicle trackers.

## Replay capacity

The source and every processed replay sample after it are retained, up to 64
entries and the existing 1000ms source TTL. Older prefix entries may be removed;
no intermediate sample inside the source replay suffix is removed. When a 65th
suffix entry would require a gap, the source is invalidated: complete it if still
unsubmitted, or drop its Pending/queued reply if already dispatched. An active
RKNN consumer remains owned by the inherited inference path and is never cancelled
or completed by the pipeline. Latest RAW tracker state is preserved; late replies
for the invalidated source cannot correct or clear it. History then returns to the
ordinary eight-entry bound. Healthy 25ms RAW cadence produces fewer than 64 samples
inside the 1000ms TTL and therefore does not trigger this capacity policy.

No new RGB deep copies or snapshot-memory optimizations. Steady retained history
is capped at 64 owned RGB/grayscale frames plus tracker snapshots; appending a new
sample transiently creates entry 65 before pruning. Expect roughly 75MiB plus
bounded tracker snapshots at that transient cap, depending on image strides and
allocator overhead. `[analysis-replay]` reports observed history_peak,
overflow_retirements, unprocessed-request rejections and replay_gap_count=0.
The existing default-off same-ID age telemetry is unchanged.

## Actual-worker test fixtures

Private selftest-only hook installation occurs before QThread start. The hook is
null in production and never blocks production or changes cadence. A race fixture
injects the exact input after the worker processed its copied ingress but before
request re-reads it. The post-request hook verifies no early emission and no
dispatch, then inserts newer RAW before the next iteration. The actual
inferenceRequested callback verifies both exact and newest processed history are
present; the detector reply must correct frame 2 and replay its target to frame 3.

Two overflow fixtures process and observe every source-suffix frame through the
65th entry before the 1000ms TTL. One holds an existing CPU Pending, proving the
unsubmitted Input retires at capacity. The other starts with healthy vehicle
tracks and a dispatched exact Input, proving an empty late overflow-source reply
is rejected without clearing latest RAW tracks. Both observe the real worker's
overflow counter and eight-entry history restoration. Existing live replay,
latest-RAW loss, switch/stop/lifetime and other full-pipeline cases remain.

Host wrapped protocol/cadence/admission/main-class checks are available, but the
host lacks OpenCV development files. FULL PIPELINE COMPILE AND UPDATED VISION
SELFTEST EXECUTION REMAIN PENDING parent ARM work. Neither helper syntax checks
nor modeled clock fixtures validate the full worker. Independent review remains
required; no hardware authorization is requested or implied by this change.

Host validation performed: `bash local_prefetch_check.sh` passes the copied-source
preservation audit, production cadence/admission clock and lifetime fixtures,
wrapped actual PangoDev protocol fixtures (off/on/verify), fair DMA fixtures,
main classes syntax compilation, and native output capture fixtures. These tests
use wrappers and do not access hardware. The audit confirms main.cpp is byte-identical
to the live candidate and that only the pipeline header/implementation/selftest
and preservation script differ among copied source files.
