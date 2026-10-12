Connect the deployed FPGA CAM1–4 motion records to RK3568 inference scheduling.
Retain full-image model inputs and six-camera display. Static scenes may defer
repeated inference only with valid fresh metadata, bounded periodic refresh,
and fallback on unsupported camera/source, lane mode, unavailable ABI, errors
or stale sequence. Motion records are latest-source hints, not DDR-frame tags.

| Requirement | Required evidence | Current state |
|---|---|---|
| Read frozen FPGA metadata safely | ABI identity, independent scratch, DMA mutex and stable generation | Target verified; sample888 polls/sequence advances, zero read errors, no disable |
| Consume motion in actual inference requests | VisionFrame propagation and scheduler decision counters | Target CAM1 sample182 motion completions,112 periodic completions,875 static frame deferrals |
| Bounded static refresh and motion response | Behavioral tests including sequence stalls, invalid metadata, source changes and model coverage | Local/target policy84 checks pass; actual worker vision suite passes |
| Preserve inference pixels | Unchanged worker/preprocessing/decoder bytes and meaningful model output comparison | Full37509-byte InferenceThread section identical; input helpers identical; target vision/DFL/lane/DMA/frame suites pass |
| Board build and deployment | Exact source/build/binary pins, verified sole DMA owner and visible window | Corrected buildde9f18c17a10da4c, binary610b0cd15ec346b57b314458e4e11a9384bb3bbb783f743af630f0965914ce3c; viewerPID55103 start16097277 |
| Live six-camera behavior | Bounded motion/periodic/fallback observations and screen inspection |121.606s identity-pinned observation passes; all6 panes present, camera read-error counters zero; screenshotmotion_scheduling_revised.png |
| Recoverable viewer switch | Save current camview identity/settings and graceful close; retain restoration snapshot | Current camview PID51952 receipt show_camview_ec0dadc39f9346a690b2df8f68470f31 |

No FPGA change, ROI transfer or physical DDR-bandwidth reduction is claimed.
Fewer static-scene inferences must be reported as avoided work, separately
from completed inferences per second and model service latency.

Read-only current camview log inspection confirms deployed metadata is live:
retained latest120 log lines contain13/13/14/14 records for CAM1–4, advancing
source sequences, maximum motion blocks7/8/6/0. This proves current ABI data
availability, not scheduler integration. `samples` counts changed samples,
not total sampled pixels; zero marked blocks can coexist with subthreshold
sample changes. The implementation must preserve that interpretation.

First deployment has been gracefully stopped and camview restored, confirmed
by `log/100h_motion/motion_viewer_candidate_stop_restore_8a5c4249077d45fd8011bf5e010f98ec.json`.
The initial3ms transaction budget is not compatible with the deployed driver.
Source correction and a new target build/live observation are required.

## Corrected deployment acceptance

The corrected250ms capture watchdog and transient retry version is now running.
Pinned source and target selftest evidence are in final_source_manifest.json
and target_selftest_result.json. Start receipt:
`log/100h_motion/motion_viewer_start_2c8fb49598c04003865a3d5cafb1d5c8.json`;
observation receipt:
`log/100h_motion/motion_viewer_observe_797bdc0e902a4dba812bfeb6edd0ddc9.json`.
Run audit_observation.py against this observation; live_acceptance.json records
the first-to-last counter sample deltas, which exclude window edges.

Live motion-gated inference was observed on selectedCAM1, not simultaneously
on all four supported cameras. CAM1–4 policy/source support and CAM5/6 fallback
are covered by policy/worker tests; future hardware camera switching and
fault injection are additional coverage, not evidence claimed here.
Observed sample:875 static frame deferrals,182 motion-triggered completions,
112 periodic completions and746 fallback completions. Metadata sample888
successful polls,326784 payload bytes,888 sequence changes, zeroerrors;
maximum capture16.822ms, maximum singleioctl13.953ms. Fallback can occur when
DMA mutex contention yields no hint; it does not imply a metadata read error.
All six camera capture counters continue, with zero read errors in the log.

This accepts functional FPGA-motion-to-YOLO scheduling integration. It does
not claim higher inference/display throughput or lower full-image DMA load.
The current one-model configuration and changing scene cannot validate a
four-model live refresh bound or missed-event detection guarantees. Observed
motion polling can miss transient changes; periodic full-frame refresh is retained.
Current detview has six-camera display and the original configured stereo work.
The private snapshot retains camview restoration through board_viewer.py.
