# Detection box temporal confirmation

The current full-rate `--no-tracking` preview uses a180ms grace. When template
tracking is enabled and detector requests are intentionally spaced farther
apart, grace covers the configured per-model detection cadence plus80ms
(capped at1500ms), always bounded by the original source expiry. Confirmation
still requires three real detector observations; predictions never count.

Default display policy: three consecutive detector observations of the same
class with spatial overlap before showing a new box. A confirmed box can
bridge a 180 ms detection gap. Every retained box has a display expiry;
repaints and tracking predictions cannot turn one observation into three.

The filter is downstream from the model's sigmoid/NMS/class threshold policy.
It does not change raw RKNN outputs or the MVP-R1 calibration profile.
Class-dependent confidence limits still apply before temporal confirmation.

At 20 inference FPS the usual extra appearance delay is about 100 ms. A fast
target seen only once or twice will also be hidden. Stable false detections
can still pass; temporal confirmation is a display filter, not a new accuracy
claim. Brief retained boxes use the last observed position without trajectory
extrapolation.

Only accepted detector replies count, once per source frame and model. Source,
camera, model, confidence, coordinate format and pause changes clear confirmation
state. The video preview limits observation gaps to 600 ms; low-rate tracking
uses a gap bound that also covers its configured detection cadence.
Tracking predictions keep their geometry and depth metadata after confirmation;
their expiry is capped by the detector filter and the original source deadline.
Lane masks and independent UFLD output are unchanged.

Algorithm tests: `QT_QPA_PLATFORM=offscreen ./detview --temporal-selftest`.
Use `--no-temporal-filter` for a display-only A/B comparison; it does not change
inference cadence or model thresholds. `--no-tracking` remains supported.
`--box-filter-debug` emits one `[box-filter]` JSON record per accepted detector
observation with source frame, raw/visible counts, geometry, scores and expiry.
Without that switch, counts are logged for the first three observations and
every twentieth observation per model.
