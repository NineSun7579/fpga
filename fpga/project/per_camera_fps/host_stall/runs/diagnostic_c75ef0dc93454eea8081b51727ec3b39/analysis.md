Diagnostic receipt status: success.

HDMI restoration verified: True.

Retained 6893 diagnostic lines, 186 camera windows, 372 ioctl windows and 112 proc samples.

Whole-log completed ioctl counts: 141517 attempts; 0 application failures. These are completion-assigned counters.

Whole-log slow records: 5964; 491 have low thread CPU. This alone cannot identify the cause of the missing CPU time.

Receipt measurement: 120.000245 seconds; observer thread CPU 18.306885 seconds. Endpoint precedes final verification: True.

Within measurement timestamps: 134 complete camera windows, 268 complete ioctl windows; 107810 ioctl attempts, 0 application failures. Excluded 2176 records, including 61 boundary-crossing records.

Measured camera 1: 22 complete windows, 110.187271 covered seconds; 4479 delivered, 0 error, 635 no_new, 0 unstable; 40.649 delivered/s over covered windows.

Measured camera 2: 22 complete windows, 110.188071 covered seconds; 4493 delivered, 0 error, 619 no_new, 0 unstable; 40.776 delivered/s over covered windows.

Measured camera 3: 23 complete windows, 115.123227 covered seconds; 2960 delivered, 0 error, 6917 no_new, 0 unstable; 25.712 delivered/s over covered windows.

Measured camera 4: 23 complete windows, 115.109718 covered seconds; 2961 delivered, 0 error, 6788 no_new, 0 unstable; 25.723 delivered/s over covered windows.

Measured camera 5: 22 complete windows, 110.140952 covered seconds; 5358 delivered, 0 error, 287 no_new, 0 unstable; 48.647 delivered/s over covered windows.

Measured camera 6: 22 complete windows, 110.144544 covered seconds; 5321 delivered, 0 error, 300 no_new, 0 unstable; 48.309 delivered/s over covered windows.

Total observer cost: 19.944279 CPU seconds, 121.922873 wall seconds. Scope: observe_trial setup, measurement, endpoint verification, trace cleanup/artifact metadata and stream close; excludes viewer startup/restoration and this summary emission.

Maximum observer iteration CPU: 1023.833 ms; maximum paired interval CPU: 1024.160 ms over 2140.977 wall ms. Global guards: 12; maximum start-to-start gap 11.021013 seconds.

Maximum CPU interval between proc sample clocks: 1024.457 CPU ms paired with 2142.237 wall ms.

Phase totals below use complete measurement windows.

Outcome success, phase alloc: 34544 scopes, mean wall 0.025 ms, mean CPU 0.018 ms, maximum wall 9.678 ms.

Outcome success, phase attempt: 25572 scopes, mean wall 14.212 ms, mean CPU 7.479 ms, maximum wall 79.266 ms.

Outcome success, phase convert: 8972 scopes, mean wall 3.210 ms, mean CPU 2.217 ms, maximum wall 31.657 ms.

Outcome success, phase copy: 25572 scopes, mean wall 8.870 ms, mean CPU 6.369 ms, maximum wall 66.722 ms.

Outcome success, phase dma_hold: 25572 scopes, mean wall 1.942 ms, mean CPU 0.191 ms, maximum wall 21.711 ms.

Outcome success, phase dma_wait: 25572 scopes, mean wall 2.033 ms, mean CPU 0.028 ms, maximum wall 63.929 ms.

Outcome success, phase publish_hold: 25572 scopes, mean wall 0.025 ms, mean CPU 0.020 ms, maximum wall 13.403 ms.

Outcome success, phase publish_wait: 25572 scopes, mean wall 0.008 ms, mean CPU 0.003 ms, maximum wall 8.505 ms.

Outcome success, phase read: 25572 scopes, mean wall 12.900 ms, mean CPU 6.618 ms, maximum wall 79.225 ms.

Outcome success, phase sink: 8972 scopes, mean wall 0.216 ms, mean CPU 0.065 ms, maximum wall 19.580 ms.

Outcome no_new, phase alloc: 15546 scopes, mean wall 0.009 ms, mean CPU 0.008 ms, maximum wall 3.565 ms.

Outcome no_new, phase attempt: 15546 scopes, mean wall 1.433 ms, mean CPU 0.141 ms, maximum wall 21.675 ms.

Outcome no_new, phase dma_hold: 15546 scopes, mean wall 0.402 ms, mean CPU 0.097 ms, maximum wall 15.154 ms.

Outcome no_new, phase dma_wait: 15546 scopes, mean wall 0.995 ms, mean CPU 0.021 ms, maximum wall 21.559 ms.

Outcome no_new, phase read: 15546 scopes, mean wall 1.419 ms, mean CPU 0.133 ms, maximum wall 21.666 ms.

Statistics use exactly the immutable header field names; units are not inferred.

Viewer records include startup and normal shutdown; proc intervals cover only bounded observation.

Bounded analysis includes only complete windows/attempts inside receipt timestamps; its camera coverage can be shorter than the measured duration.

Older receipts record their measured endpoint after final verification; that legacy endpoint cannot be separated retroactively.

Disabled schedstats means unknown scheduler wait. A sampled R state does not prove continuous runnable time.

Wall minus thread CPU alone does not separate blocking, descheduling and process group stop.

Trace is bounded and filters sampled TIDs; absence of an event is not proof of absence.

Five-second windows assign complete attempts at completion, including spans crossing the window.

All-completed windows count failures; slow lines are a thresholded subset. Immediate exit can lose deferred records.

Read/hold/ioctl/copy scopes are nested; their sums are not additive. Logger totals repeated across ioctl roles are not additive.
