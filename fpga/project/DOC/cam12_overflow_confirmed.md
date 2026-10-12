# cam1/cam2 FIFO overflow confirmed on hardware

Diagnostic artifact: bitstream_frame_recovery_20260927_113853/top.sbit

SHA256: 630E314BEE819F2F0A897BD88D57B88B6A075371D5256D498D39D51C9A391074

This image adds read-only diagnostic counters to the recovery design. Camera PLL settings and capture-control behavior are unchanged: cam1/2 84 MHz, cam3 48 MHz.

The sampled interval is 20.436963 seconds (81 snapshots):

| Camera | Offered pixels per frame (all snapshots) | Overflow events | Short events | Successful frames |
|---|---:|---:|---:|---:|
| 1 | 307200 | 921 | 0 | 0 |
| 2 | 307200 | 921 | 0 | 0 |
| 3 | 307200 | 0 | 0 | 526 |

Retained fault records have the overflow flag set. Accepted pixel counts at failure range from 13442 to 27522 for cam1 and 13570 to 27522 for cam2. These observations identify capture FIFO overflow, not missing offered pixels or short-frame termination, as the cause of rejection during this interval. They do not yet identify which FIFO or the underlying throughput bottleneck.

cam3 succeeds at approximately 25.738 frames/s; its retained fault record is zero. A subsequent three-second window again yields zero cam1/2 success and approximately 25.655 cam3 successes/s.

Evidence: tp/rejection_diag_evidence/registers.json, session.log and capture.json. Driver/viewer restart completed (camview PID 2618 at verification). This is diagnostic progress, not a successful three-camera repair.

Next work: reproduce and repair buffering/service throughput at the real 84/84/48 MHz input rates while preserving error checks, safe AXI retirement and cam3 behavior. Do not lower camera clocks or publish overflowed frames as a workaround.
