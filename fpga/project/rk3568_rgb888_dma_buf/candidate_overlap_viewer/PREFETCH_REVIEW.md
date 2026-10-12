# Experimental bounded input prefetch

Only this new candidate was changed. It is copied from candidate_short_hold_viewer;
main.cpp, worker serialization, transport protocol, revision and retirement locks
are byte-identical. No board access, ARM build, deployment, commit or RTL changes.

## Source findings

Original baseline and short-hold both refresh `now = monotonicMs()` inside
VisionPipeline::Impl::request after frame processing and reply replay. They set
Pending::sentMs and lastRequestMs to that actual submission time, then emit
inferenceRequested. Neither tree contains a lastInferenceStart variable.
Pending begins here, not at arm, capture, FPGA READY, GUI submission or RKNN start;
the 2-second reply timeout starts at sentMs. Normal tracking uses max(detection,
minimum,1), urgent tracking uses max(minimum,1), lane/no-tracking bypasses cadence.

Short-hold adds Admission::arm **after** the interval test. On an ordinary camera
frame it returns without pending, lastRequestMs or requests-count updates. CameraWorker
claims admission before its next read; cameraReadFpga validates the selected RAW
bank/tag/epoch, reads that RAW, waits for conversion READY (status 0x0b and job count),
releases the camera hold, then publishes an Input and owned RGB image of the RAW.
The next vision iteration processes that admitted frame and submits it. Therefore
acquisition/READY/vision wake latency after the interval check can recur each cycle.

Observed stored summary: 3.1667 completed/s, lease mean 45.39 ms. A 250 ms interval
plus about 66 ms of repeated preparation/wake delay predicts about 3.17/s. This is
a plausible explanation, not a measured decomposition: per-stage timestamps and
board comparison are absent. A 45 ms synchronous inference does not inherently
make this a 250+45 ms completion-cooldown policy: the baseline clock is submission
to submission, and pending blocks overlap only while the reply remains outstanding.

Backdating lastRequestMs to acquisition/request-generation time is rejected:
it permits actual submissions less than the original configured interval apart.
Arming only just before runOnce is too late to overlap camera preparation with
that interval. Admission readiness and FPGA READY are separate stages; neither
means an inference has been requested.

## Candidate change

While the original interval is still closed, arm at most 120 ms before its deadline,
only for camera acquisition, with no pending request, a current config epoch and
no already undispatched Input. Admission's occupied slot prevents another claim.
Repeated arm calls cannot create a conversion queue. Actual requests still use
the full original interval and actual submission timestamp. The 120 ms lead is
a host design allowance for a busy camera read, subsequent acquisition/conversion
and worker wake, not a proven latency bound. Delays exceeding it still reduce rate.

No normal prefetched input is cancelled or replaced when the deadline arrives.
The existing ingress pin protects its exact frame; FPGA frames bypass the tracking
frame throttle. The existing 1000 ms source-age bound, generation/epoch checks,
model-path/revision/height checks and final worker revision lock remain in force.
The chosen frame can be older than baseline's freshest frame, within that bound.
Model/source changes and stale inputs still require the existing cancellation paths;
"no cancellations" applies to healthy steady cadence, not invalidated work.
Stopping now also disarms an unclaimed early arm, under the pipeline mutex.

RAW analytics remains sourced from camera RAW pixels, independently of display
preprocessing. The input's model selection is captured at claim. Rotation happens
only after synchronous inference; old retirement cannot restore a newer revision.
RAW acquisition and conversion retain the transport's fair serialization. BEGIN/F2H
consumption is delayed until inference, so early preparation does not lengthen the
RKNN consumer lease. Input and cached imports retain shared backing until release.

## Host evidence and limits

Run `bash local_prefetch_check.sh` on a Linux host with g++, Qt5 and pkg-config.
The virtual clock uses the production cadence helper and Admission. At 250 ms
interval/45 ms run, preparation delays 40,60,100,120 ms add to every cycle without
prefetch, but fit inside the cooldown with prefetch; submission spacing remains
250 ms. Conversion count is submissions plus at most one future input. Boundary,
urgent/bypass, unclaimed model reload, source generation/camera mismatch, occupied
model reload, stale retirement, queued backing lifetime, cached-import lifetime
and concurrent exactly-once completion assertions pass.

The copied actual PangoDev syscall fixtures pass feature-off, feature-on and verify
modes; fair DMA, native output fixtures and extracted main-class syntax checks pass.
main.cpp SHA-256 matches short-hold. These protocol tests retain the actual conversion
and release sequence, but mock device syscalls. The new clock fixture does not run
Qt VisionPipeline end to end. Full vision_pipeline compilation/selftest is not run:
this host lacks OpenCV development headers. No board throughput, physical latency,
RAW correctness on hardware or deployment readiness is claimed. The fixed lead
needs measured readiness/wake timestamps before adoption; parent restoration of
the original remains independent of this experimental candidate.
